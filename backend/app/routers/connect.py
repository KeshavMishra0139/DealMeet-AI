"""Connecting Instagram with its official login (OAuth, read-only scopes)."""
from __future__ import annotations

from urllib.parse import quote

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse

from ..config import get_settings
from ..db import get_db
from ..services import auth as au
from ..services import instagram as ig
from ..services import ratelimit, social_signin
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["connect"])


def _creator_user(user: dict) -> str:
    au.require_role(user, "creator")
    if not user.get("creator_id"):
        raise HTTPException(409, "Finish onboarding before connecting Instagram.")
    return user["creator_id"]


def _frontend(request: Request) -> str:
    return get_settings().frontend_url or str(request.base_url).rstrip("/")


@router.get("/connect/instagram/consent")
def consent():
    """What connecting lets DealMeet see, shown before the Instagram login opens."""
    return {"text": ig.CONSENT_TEXT, "scopes": ig.SCOPES, "configured": ig.configured()}


@router.get("/connect/instagram/start")
def start(request: Request, json: bool = False, user: dict = Depends(au.current_user)):
    """Begins the official Instagram login. Redirects, or with ?json=1 returns the URL
    (the web app uses that, so it works with Bearer sessions too)."""
    creator_id = _creator_user(user)
    if not ig.configured():
        raise HTTPException(503, "Instagram connect isn't set up on this server (IG_APP_ID, IG_APP_SECRET, IG_REDIRECT_URI, TOKEN_ENC_KEY).")
    ratelimit.enforce(f"igstart:{user['_id']}", 10, 3600, "Too many connection attempts. Try again in an hour.")
    url = ig.authorize_url(ig.new_state(user, creator_id))
    return {"url": url} if json else RedirectResponse(url, status_code=302)


def _signin_callback(request: Request, code: str | None, state: str | None, error: str | None, error_reason: str | None) -> RedirectResponse:
    """"Continue with Instagram": find or create the creator account, then send the browser
    to the web app with a one-time code that becomes its session (POST /api/auth/oauth/complete)."""
    front = _frontend(request)

    def fail(msg: str) -> RedirectResponse:
        return RedirectResponse(f"{front}/login?role=creator&error={quote(msg)}", status_code=302)

    try:
        st = ig.consume_state(state or "", None, purpose="signin")
    except HTTPException as e:
        return fail(e.detail)
    if error or not code:
        cancelled = error_reason == "user_denied" or error == "access_denied"
        return fail("You cancelled the Instagram login. You're not signed in." if cancelled else "Instagram didn't complete the login.")
    try:
        user, note = social_signin.instagram_signin(code)
    except ig.IGError as e:
        return fail(e.message)
    login_code = social_signin.issue_login_code(user, "instagram", st.get("binding"), st.get("next"), note)
    return RedirectResponse(f"{front}/login/complete?code={quote(login_code)}", status_code=302)


@router.get("/connect/instagram/callback")
def callback(request: Request, code: str | None = None, state: str | None = None, error: str | None = None, error_reason: str | None = None):
    """Instagram sends the browser back here, for Connections and for "Continue with
    Instagram" on the sign-in page. The state proves which flow, and which account, started it."""
    if ig.state_purpose(state) == "signin":
        return _signin_callback(request, code, state, error, error_reason)
    back = f"{_frontend(request)}/creator/connections"
    session_user = au.optional_user(request)
    try:
        st = ig.consume_state(state or "", session_user)
    except HTTPException as e:
        return RedirectResponse(f"{back}?ig=error&msg={quote(e.detail)}", status_code=302)
    if error or not code:
        msg = "You cancelled the Instagram login. Nothing was connected." if (error_reason == "user_denied" or error == "access_denied") else "Instagram didn't complete the login."
        return RedirectResponse(f"{back}?ig=error&msg={quote(msg)}", status_code=302)
    user = get_db().users.find_one({"_id": st["user_id"]})
    if not user:
        return RedirectResponse(f"{back}?ig=error&msg={quote('That account no longer exists.')}", status_code=302)
    try:
        grant = ig.exchange_code(code)
        grant["ig_user_id"] = ig.identity(grant["token"])["ig_user_id"]
        ig.claim_identity(user, grant["ig_user_id"])  # one Instagram account, one DealMeet account
        ig.save_connection(user, st["creator_id"], grant)
        au.audit("connect_instagram", user["_id"], user["role"])
    except ig.IGError as e:
        return RedirectResponse(f"{back}?ig=error&msg={quote(e.message)}", status_code=302)
    try:
        ig.sync(st["creator_id"])
    except ig.IGError as e:
        return RedirectResponse(f"{back}?ig=connected&msg={quote(e.message)}", status_code=302)
    return RedirectResponse(f"{back}?ig=connected", status_code=302)


@router.post("/connect/instagram/sync")
def sync_now(user: dict = Depends(au.current_user)):
    creator_id = _creator_user(user)
    ratelimit.enforce(f"igsync:{user['_id']}", 6, 3600, "Instagram syncs are limited to 6 an hour. Try again later.")
    ig.refresh_due()
    try:
        ig.sync(creator_id)
    except ig.IGError as e:
        code = {"expired": 401, "rate_limit": 429, "network": 502, "not_connected": 409, "personal": 409, "permission": 403}.get(e.kind, 502)
        # 401 here would sign the user out of DealMeet; an expired Instagram token is a 409.
        raise HTTPException(409 if code == 401 else code, e.message) from None
    return instagram_data(creator_id, user)


@router.post("/connect/instagram/disconnect")
def disconnect(user: dict = Depends(au.current_user)):
    creator_id = _creator_user(user)
    ig.disconnect(user, creator_id)
    au.audit("disconnect_instagram", user["_id"], user["role"])
    return instagram_data(creator_id, user)


@router.get("/creators/{creator_id}/instagram")
def instagram_data(creator_id: str, user: dict = Depends(au.own_creator)):
    """The connected account's stored numbers. Never the token."""
    c = load_creator(creator_id)
    summary = (c.get("channels") or {}).get("instagram")
    posts = list(get_db().posts.find({"creator_id": creator_id, "platform": "instagram"}, {"_id": 0}).sort("published_at", -1).limit(12))
    return {"status": ig.status(c), "consent": ig.CONSENT_TEXT, "account": summary, "posts": posts}
