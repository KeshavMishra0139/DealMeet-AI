from html import escape

from fastapi import APIRouter, Query, Request, Response
from fastapi.responses import HTMLResponse

from ..ai import llm
from ..config import get_settings, now_iso, today
from ..db import db_mode, get_db, ping
from ..services import mailer, payments, social_signin, tee
from ..services.social import PROVIDERS
from ..seed.catalog import CITIES, FORMATS, city_group, INCOME_TYPES, LANGS, NICHES, STAGES

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
            "email": "smtp" if mailer.configured() else "not_configured",
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
        "cities": [{"name": k, "state": v[0], "region": v[1], "group": city_group(k)} for k, v in sorted(CITIES.items(), key=lambda kv: (city_group(kv[0]) != "Delhi NCR", city_group(kv[0]), kv[0]))],
    }


# ------------------------------------------------------------------ email opt-out
def _page(title: str, body: str, form: str = "") -> str:
    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
        f"<title>{escape(title)} · DealMeet AI</title><style>body{{margin:0;min-height:100vh;display:grid;place-items:center;background:#f9fafb;"
        "font:16px/1.5 system-ui,sans-serif;color:#0a1b33}main{max-width:440px;margin:24px;padding:28px;background:#fff;border:1px solid #e2e8f0;"
        "border-radius:20px}h1{font-size:20px;margin:0 0 8px}p{color:#334155;margin:0 0 16px}button{font:inherit;border:0;border-radius:999px;"
        "padding:10px 18px;background:#0a1b33;color:#fff;cursor:pointer}</style></head>"
        f"<body><main><h1>{escape(title)}</h1><p>{escape(body)}</p>{form}</main></body></html>"
    )


@router.get("/data-deletion", response_class=HTMLResponse)
def data_deletion_status(code: str = Query(default="", max_length=40)):
    """The status page for a data deletion request (Meta links people here with their code)."""
    doc = get_db().data_deletions.find_one({"_id": code}) if code else None
    if not doc:
        return HTMLResponse(_page("No deletion request with that code", "Check the code, or reply to us from the email linked to your account."), status_code=404)
    what = "Your Instagram data was deleted" if doc.get("found") else "We had no Instagram data for that account"
    body = (
        f"Request {code}, {doc['at'][:10]}: {what.lower()}. That's the connection and its token, posts, insights and audience "
        "numbers, and Instagram as a way to sign in. Deals keep the results of their post checks, which both sides rely on."
    )
    if doc.get("orphaned"):
        body += " Instagram was the only way into your DealMeet account, so it can't be signed in to now. Contact us to delete it or to add another way in."
    return HTMLResponse(_page(what, body))


@router.get("/email/unsubscribe", response_class=HTMLResponse)
def unsubscribe_page(t: str = Query(default="", max_length=400)):
    """Confirms before opting out: mail scanners open links on their own, so a visit alone
    never unsubscribes anyone."""
    addr = mailer.address_from_token(t)
    if not addr:
        return HTMLResponse(_page("That link isn't valid", "It may have been cut short. Reply to the email instead and we'll stop."), status_code=400)
    form = f"<form method='post'><input type='hidden' name='t' value='{escape(t)}'><button type='submit'>Stop these emails</button></form>"
    return HTMLResponse(_page("Stop emails from DealMeet AI?", f"We'll stop sending invitations to {addr}.", form))


@router.post("/email/unsubscribe", response_class=HTMLResponse)
async def unsubscribe(request: Request, t: str | None = Query(default=None, max_length=400)):
    """The button above, and one-click unsubscribe from mail apps (RFC 8058). The signed
    link is the proof; no session is needed."""
    token = t
    if not token:
        form = await request.form()
        token = str(form.get("t") or "")
    addr = mailer.address_from_token(token or "")
    if not addr:
        return HTMLResponse(_page("That link isn't valid", "It may have been cut short. Reply to the email instead and we'll stop."), status_code=400)
    mailer.opt_out(addr, "link")
    return HTMLResponse(_page("You're unsubscribed", f"We won't send invitations to {addr} again."))
