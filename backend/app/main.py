"""JodiDar AI API."""
from __future__ import annotations

import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from .config import ROOT
from .db import get_db
from .routers import auth, brands, creators, deals, demo, kit, market, meta, profiles
from .seed.load import seed_all

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def _warm_models():
    """Train the trust and price models in the background so the first page is fast."""
    try:
        from .engines import price_model, trust

        trust.model()
        price_model.model()
    except Exception:  # warming is best-effort
        logging.getLogger("jodidar").exception("Model warm-up failed")


@asynccontextmanager
async def lifespan(_: FastAPI):
    seed_all(get_db())
    threading.Thread(target=_warm_models, daemon=True).start()
    yield


app = FastAPI(title="JodiDar AI API", version="0.1.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

for r in (meta, auth, demo, profiles, creators, market, brands, deals, kit):
    app.include_router(r.router)

# Single-port mode: serve the built web app when it exists (npm run build).
DIST = ROOT / "frontend" / "dist"
if DIST.exists():
    from fastapi.staticfiles import StaticFiles

    app.mount("/assets", StaticFiles(directory=DIST / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        target = DIST / path
        if path and target.is_file():
            return FileResponse(target)
        return FileResponse(DIST / "index.html")
