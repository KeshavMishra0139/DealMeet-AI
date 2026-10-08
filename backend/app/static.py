"""Single-port mode: serve the built web app (frontend/dist) from the API.

Any path that isn't an API route gets the matching file from the build, or the
app's index.html so client-side routes like /creator/money load. The requested
path comes straight from the URL, so it is resolved and checked to stay inside
the build folder: "../", encoded "%2e%2e%2f", absolute paths and symlinks that
point elsewhere must never reach files outside it (for example backend/.env).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse


def static_file(root: Path, path: str) -> Path | None:
    """The file inside `root` that `path` names, or None if there isn't one."""
    if not path:
        return None
    base = root.resolve()
    try:
        target = (base / path).resolve()
    except (OSError, ValueError):  # null bytes, names Windows can't represent
        return None
    if not target.is_relative_to(base) or not target.is_file():
        return None
    return target


def mount_spa(app: FastAPI, dist: Path) -> None:
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    index = dist / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        return FileResponse(static_file(dist, path) or index)
