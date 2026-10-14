from fastapi import APIRouter, Response

from ..ai import llm
from ..config import get_settings, now_iso, today
from ..db import db_mode, ping
from ..services import payments, social_signin, tee
from ..services.social import PROVIDERS
from ..seed.catalog import CITIES, FORMATS, INCOME_TYPES, LANGS, NICHES, STAGES

router = APIRouter(prefix="/api", tags=["meta"])


def social_mode() -> str:
    on = [k for k, (configured, _) in PROVIDERS.items() if configured()]
    return ", ".join(sorted(on)) if on else "not_connected"


@router.get("/health")
def health(response: Response):
    s = get_settings()
    db_ok = ping()
    if not db_ok:
        response.status_code = 503  # the host's health check sees the database is down
    return {
        "status": "ok" if db_ok else "database_unreachable",
        "today": today().isoformat(),
        "now": now_iso(),
        "modes": {
            "db": db_mode(),
            "db_ok": db_ok,
            "ai": "live" if s.has_ai else "templates",
            "ai_provider": s.ai_provider,  # anthropic, openrouter or None
            "ai_model": s.ai_model if s.has_ai else None,
            "ai_last_error": llm.last_error(),  # the last failed AI call in 24 hours, and what fixes it
            "payments": payments.mode(),
            "payouts": payments.payout_mode(),
            "social": social_mode(),
            "post_checks": "automatic when connected" if social_mode() != "not_connected" else "brand review (automatic checks not connected)",
            "auth": ", ".join(
                ["password"]
                + (["firebase"] if s.has_firebase else [])
                + (["instagram"] if social_signin.instagram_configured() else [])
                + (["youtube"] if social_signin.youtube_configured() else [])
                + (["demo"] if s.demo_mode else [])
            ),
            "tee": tee.status()["status"],  # not_configured, available or failed: never a container passed off as a TEE
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
