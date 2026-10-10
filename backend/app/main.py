"""JodiDar AI API."""
from __future__ import annotations

import logging
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from .config import ROOT, get_settings
from .db import get_db
from .routers import auth, brands, creators, deals, demo, kit, market, meta, profiles
from .seed.load import seed_all
from .static import mount_spa

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


log = logging.getLogger("jodidar")
MAX_BODY = 256 * 1024  # every form in the app is a few KB
_last_write = [0.0]  # monotonic time of the last change a visitor made


def _warm_models():
    """Train the trust and price models once, before the first request, so pages are fast."""
    try:
        from .engines import price_model, trust

        trust.model()
        price_model.model()
    except Exception:  # warming is best-effort
        logging.getLogger("jodidar").exception("Model warm-up failed")


def _auto_reset(minutes: int) -> None:
    """Shared URL: put the demo back to its seeded state every few minutes, skipping a
    round while someone has changed something in the last 5 minutes (mid-walkthrough)."""
    from .services import cache

    while True:
        time.sleep(minutes * 60)
        if time.monotonic() - _last_write[0] < 300:
            continue
        cache.clear_runtime()
        seed_all(get_db(), force=True)
        log.info("Shared demo reset to its seeded state")


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_all(get_db())
    _warm_models()
    minutes = get_settings().demo_reset_minutes
    if minutes > 0:
        threading.Thread(target=_auto_reset, args=(minutes,), daemon=True).start()
    yield


app = FastAPI(title="JodiDar AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)


@app.middleware("http")
async def guard(request: Request, call_next):
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        size = request.headers.get("content-length")
        if size and size.isdigit() and int(size) > MAX_BODY:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if request.url.path.startswith("/api/") and request.url.path != "/api/demo/reset":
            _last_write[0] = time.monotonic()
    response = await call_next(request)
    path = request.url.path
    if path.startswith("/assets/") and response.status_code == 200:
        # Built files have content hashes in their names, so they never change.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not path.startswith("/api/") and response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"  # pick up a new deploy straight away
    return response


for r in (meta, auth, demo, profiles, creators, market, brands, deals, kit):
    app.include_router(r.router)

# Single-port mode: serve the built web app when it exists (npm run build).
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    mount_spa(app, DIST)
