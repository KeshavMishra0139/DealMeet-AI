"""DealMeet AI API."""
from __future__ import annotations

import logging
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from . import headers
from .config import ROOT, get_settings
from .db import get_db
from .routers import admin, assistant, auth, brands, connect, creators, deals, demo, directory, kit, market, meta, pitches, pricing, profiles, reports, shortlist, youtube
from .seed.load import seed_all
from .services.auth import audit
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


def _refresh_tokens():
    from .services import instagram

    time.sleep(60)
    while True:
        try:
            n = instagram.refresh_due()
            if n:
                log.info("Refreshed %d Instagram token(s)", n)
        except Exception:
            log.exception("Instagram token refresh failed")
        time.sleep(24 * 3600)


@asynccontextmanager
async def lifespan(_: FastAPI):
    settings = get_settings()
    # Connect (and create indexes) first: without USE_MOCK_DB=1, a missing or unreachable
    # MONGODB_URI stops startup here with a clear message.
    db = get_db()
    if settings.demo_mode:
        seed_all(db)
    elif os.getenv("REMOVE_SAMPLE_DATA", "").strip().lower() in ("1", "true", "yes", "on"):
        # A live site: sample creators, brands, campaigns and demo accounts left from demo
        # mode are removed at start. Real accounts stay. Safe to leave on.
        from .seed.load import remove_sample

        remove_sample(db)
    _warm_models()
    # Creators saved before brand search existed get their measured reach.
    from .services import reach

    reach.backfill(db)
    # Channels linked before linking updated the profile get their YouTube numbers.
    from .services import youtube_public

    youtube_public.backfill_profiles(db)
    # Instagram long-lived tokens: an in-process daily job refreshes those that expire within
    # 10 days (each sync also refreshes first, for hosts that sleep).
    from .services import instagram

    if instagram.configured():
        threading.Thread(target=_refresh_tokens, daemon=True).start()
    # The shared demo's timed reset never runs outside demo mode, so it can't touch real accounts.
    if settings.demo_mode and settings.demo_reset_minutes > 0:
        threading.Thread(target=_auto_reset, args=(settings.demo_reset_minutes,), daemon=True).start()
    yield


app = FastAPI(title="DealMeet AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(GZipMiddleware, minimum_size=1024)


# Writes that arrive without the app's header are refused unless they carry a Bearer
# token: a cross-site form can't add a custom header, so a session cookie alone is never
# enough to change anything (CSRF). Provider webhooks prove themselves with a signature.
CSRF_HEADER = "x-requested-with"
# The unsubscribe link proves itself with its signature (and mail apps' one-click POST
# can't send a custom header).
CSRF_EXEMPT = ("/api/payments/razorpay/webhook", "/api/email/unsubscribe")


@app.middleware("http")
async def guard(request: Request, call_next):
    response = await _guarded(request, call_next)
    headers.apply(response.headers, request.url.scheme == "https", INDEX)
    return response


async def _guarded(request: Request, call_next):
    path = request.url.path
    write = request.method not in ("GET", "HEAD", "OPTIONS") and path.startswith("/api/")
    if request.method not in ("GET", "HEAD", "OPTIONS"):
        size = request.headers.get("content-length")
        if size and size.isdigit() and int(size) > MAX_BODY:
            return JSONResponse({"detail": "Request too large"}, status_code=413)
        if write and path not in CSRF_EXEMPT and not request.headers.get(CSRF_HEADER):
            if not request.headers.get("authorization", "").lower().startswith("bearer "):
                return JSONResponse({"detail": "Missing the X-Requested-With header. Use the DealMeet app or send a Bearer token."}, status_code=403)
        if write and path != "/api/demo/reset":
            _last_write[0] = time.monotonic()
    response = await call_next(request)
    if write:
        # Every write is audited: who, what route, and how it ended. Bodies are never stored.
        try:
            audit(
                "write",
                getattr(request.state, "user_id", None),
                getattr(request.state, "role", None),
                method=request.method,
                path=path,
                status=response.status_code,
            )
        except Exception:  # auditing must never break the request
            log.exception("Audit write failed")
    if path.startswith("/assets/") and response.status_code == 200:
        # Built files have content hashes in their names, so they never change.
        response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
    elif not path.startswith("/api/") and response.headers.get("content-type", "").startswith("text/html"):
        response.headers["Cache-Control"] = "no-cache"  # pick up a new deploy straight away
    return response


for r in (meta, auth, demo, profiles, creators, market, brands, directory, admin, shortlist, pitches, deals, kit, pricing, youtube, connect, assistant, reports):
    app.include_router(r.router)

# Single-port mode: serve the built web app when it exists (npm run build).
DIST = ROOT / "frontend" / "dist"
INDEX = DIST / "index.html" if DIST.exists() else None  # its inline script's hash goes in the CSP
if DIST.exists():
    mount_spa(app, DIST)
