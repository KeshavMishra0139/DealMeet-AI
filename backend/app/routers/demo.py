from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..db import get_db
from ..seed.load import seed_all

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _demo_only() -> None:
    # Outside demo mode these routes don't exist: a reset would wipe real accounts' data.
    if not get_settings().demo_mode:
        raise HTTPException(404, "Not found")


@router.post("/reset")
def reset():
    """Restore every seeded record. Used by the 'Reset demo' control (demo mode only)."""
    from ..services import cache

    _demo_only()

    cache.clear_runtime()
    return seed_all(get_db(), force=True)

