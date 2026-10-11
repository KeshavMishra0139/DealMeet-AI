from fastapi import APIRouter

from ..config import get_settings, now_iso, today
from ..db import db_mode
from ..services import payments
from ..services.social import PROVIDERS
from ..seed.catalog import CITIES, FORMATS, INCOME_TYPES, LANGS, NICHES, STAGES

router = APIRouter(prefix="/api", tags=["meta"])


def social_mode() -> str:
    on = [k for k, (configured, _) in PROVIDERS.items() if configured()]
    return ", ".join(sorted(on)) if on else "not_connected"


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
            "payments": payments.mode(),
            "payouts": payments.payout_mode(),
            "social": social_mode(),
            "post_checks": "automatic when connected" if social_mode() != "not_connected" else "brand review (automatic checks not connected)",
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
