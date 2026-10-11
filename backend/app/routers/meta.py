from fastapi import APIRouter

from ..config import get_settings, now_iso, today
from ..db import db_mode
from ..seed.catalog import CITIES, FORMATS, INCOME_TYPES, LANGS, NICHES, STAGES

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    s = get_settings()
    return {
        "status": "ok",
        "today": today().isoformat(),
        "now": now_iso(),
        "modes": {
            "db": db_mode(),
            "ai": "live" if s.has_ai else "templates",
            "payments": "razorpay-test" if s.has_razorpay else "simulated",
            "auth": ", ".join(["password"] + (["firebase"] if s.has_firebase else []) + (["demo"] if s.demo_mode else [])),
        },
        "demo_mode": s.demo_mode,
        "shared_demo": s.demo_mode and s.demo_reset_minutes > 0,
    }


@router.get("/meta")
def meta():
    return {
        "niches": [{"id": k, **v} for k, v in NICHES.items()],
        "languages": [{"id": k, **v} for k, v in LANGS.items()],
        "stages": STAGES,
        "income_types": [{"id": k, "label": v} for k, v in INCOME_TYPES.items()],
        "formats": [{"id": k, "label": v} for k, v in FORMATS.items()],
        "cities": [{"name": k, "state": v[0], "region": v[1]} for k, v in sorted(CITIES.items())],
    }
