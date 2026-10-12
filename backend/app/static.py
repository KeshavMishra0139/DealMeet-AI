"""Single-port mode: serve the built web app (frontend/dist) from the API.

Any path that isn't an API route gets the matching file from the build, or the
app's index.html so client-side routes like /creator/money load. The requested
path comes straight from the URL, so it must never reach files outside the
build folder (for example backend/.env):

1. The path is checked as plain text first, before anything touches the disk.
   On Windows, even asking whether "\\\\host\\share\\x" is a file opens a network
   (SMB) connection to that host, so drive letters, backslashes, network paths,
   ".." segments and null bytes are refused up front.
2. What's left is resolved (following symlinks) and must stay inside the folder.
"""
from __future__ import annotations

import logging
import mimetypes
import re
from html import escape
from pathlib import Path, PurePosixPath

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, HTMLResponse

log = logging.getLogger("jodidar.static")

# Windows: Python reads MIME types from the registry, where some installers set
# .js to text/plain. Browsers refuse a module script served as text/plain, which
# leaves the app blank, so the types the build uses are pinned here.
BUILD_TYPES = (
    ("text/javascript", ".js"),
    ("text/javascript", ".mjs"),
    ("text/css", ".css"),
    ("text/html", ".html"),
    ("application/json", ".json"),
    ("image/svg+xml", ".svg"),
    ("font/woff2", ".woff2"),
    ("font/woff", ".woff"),
)


def pin_build_types() -> None:
    for media_type, ext in BUILD_TYPES:
        mimetypes.add_type(media_type, ext)


def _safe_relative(path: str) -> PurePosixPath | None:
    """The path as relative POSIX parts, or None if it could point anywhere else."""
    if not path or "\\" in path or ":" in path or "\x00" in path:
        return None
    rel = PurePosixPath(path)
    if rel.is_absolute() or ".." in rel.parts:
        return None
    return rel


def static_file(root: Path, path: str) -> Path | None:
    """The file inside `root` that `path` names, or None if there isn't one."""
    rel = _safe_relative(path)
    if rel is None:
        return None
    base = root.resolve()
    try:
        target = base.joinpath(*rel.parts).resolve()
    except (OSError, ValueError):  # names the OS can't represent
        return None
    if not target.is_relative_to(base) or not target.is_file():
        return None
    return target


# ------------------------------------------------------------------ link previews
CREATOR_PAGE = re.compile(r"^c/([A-Za-z0-9._-]{1,60})/?$")


def creator_preview(handle: str) -> dict | None:
    """Title and description for a creator's public page, or None if it isn't public."""
    from .db import get_db
    from .seed.catalog import LANGS, NICHES

    c = get_db().creators.find_one({"handle": handle}, {"name": 1, "niche": 1, "languages": 1, "branding": 1, "public_page": 1})
    if not c or c.get("public_page") is False:
        return None
    niche = NICHES.get(c.get("niche"), {}).get("label", "Creator")
    langs = " and ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS)
    branding = c.get("branding") or {}
    line = branding.get("positioning") if branding.get("show_on_page") else None
    return {
        "title": f"{c['name']} · {niche} creator on JodiDar AI",
        "description": line or f"{niche}{' in ' + langs if langs else ''}. See their media kit and book them with escrow on JodiDar AI.",
    }


def with_preview(index_html: str, preview: dict, url: str) -> str:
    """index.html with Open Graph and Twitter tags for one page. Every value is escaped."""
    tags = {
        "og:title": preview["title"],
        "og:description": preview["description"],
        "og:type": "profile",
        "og:url": url,
        "og:site_name": "JodiDar AI",
        "twitter:card": "summary",
        "twitter:title": preview["title"],
        "twitter:description": preview["description"],
    }
    meta = "".join(
        f'<meta {"name" if k.startswith("twitter:") else "property"}="{k}" content="{escape(v, quote=True)}" />' for k, v in tags.items()
    )
    meta += f'<meta name="description" content="{escape(preview["description"], quote=True)}" />'
    out = re.sub(r'<meta name="description"[^>]*>', "", index_html, count=1)
    out = re.sub(r"<title>.*?</title>", f"<title>{escape(preview['title'])}</title>", out, count=1, flags=re.S)
    return out.replace("</head>", meta + "</head>", 1) if "</head>" in out else meta + out


def mount_spa(app: FastAPI, dist: Path) -> None:
    from fastapi.staticfiles import StaticFiles

    pin_build_types()
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str, request: Request):
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not found")
        m = CREATOR_PAGE.match(path)
        if m:
            # A shared /c/:handle link gets its own preview: crawlers don't run the app.
            try:
                preview = creator_preview(m.group(1))
                if preview:
                    url = str(request.base_url).rstrip("/") + f"/c/{m.group(1)}"
                    return HTMLResponse(with_preview(index.read_text(encoding="utf-8"), preview, url))
            except Exception as e:  # the page still loads without a preview
                log.warning("No link preview for /c/%s: %s", m.group(1), type(e).__name__)
        return FileResponse(static_file(dist, path) or index)
