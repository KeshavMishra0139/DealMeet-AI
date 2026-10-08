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

import mimetypes
from pathlib import Path, PurePosixPath

from fastapi import FastAPI
from fastapi.responses import FileResponse

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


def mount_spa(app: FastAPI, dist: Path) -> None:
    from fastapi.staticfiles import StaticFiles

    pin_build_types()
    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(static_file(dist, path) or index)
