from fastapi import APIRouter

from ..db import get_db
from ..seed.load import seed_all

router = APIRouter(prefix="/api/demo", tags=["demo"])


@router.post("/reset")
def reset():
    """Restore every seeded record. Used by the 'Reset demo' control."""
    from ..services import cache

    cache.clear_runtime()
    return seed_all(get_db(), force=True)
