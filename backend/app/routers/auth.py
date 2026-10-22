"""Sign-up, sign-in and sign-out.

Accounts are creators or brands; admin is granted only from the server
(`python -m app.admin_cli grant <email>`). In demo mode (DEMO_MODE=1) the persona
picker signs you in to a seeded demo account instead.

Ways in: email and password, Firebase (Google, phone), and for creators "Continue
with Instagram" and "Continue with YouTube" (services/social_signin.py).

Account security: signed-in devices and signing them out, password change, reset and
email verification (services/credentials.py).
"""
from __future__ import annotations

import logging
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Path, Query, Request, Response
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import get_db
from ..services import auth as au
from ..seed.load import DEMO_ADMIN_ID
from ..services import credentials, firebase_auth, ratelimit, social_signin
from ..services import instagram as ig

router = APIRouter(prefix="/api/auth", tags=["auth"])
log = logging.getLogger("jodidar.auth")

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

PERSONAS = [
    {"id": "cr_a", "role": "creator", "title": "Creator A", "subtitle": "Anime-edit reels, Hindi and English, 21.3K followers", "tag": "Reference profile"},
    {"id": "cr_b", "role": "creator", "title": "Creator B", "subtitle": "Tamil home cooking, 2K followers, just starting", "tag": "Fictional"},
    {"id": "new_creator", "role": "creator", "title": "New creator", "subtitle": "Start from onboarding", "tag": "Onboarding"},
    {"id": "br_senpai", "role": "brand", "title": "Senpai Supply Co.", "subtitle": "Anime merch store", "tag": "Fictional brand"},
    {"id": "br_thalam", "role": "brand", "title": "Thalam Foods", "subtitle": "Regional masala and FMCG", "tag": "Fictional brand"},
    {"id": "new_brand", "role": "brand", "title": "New brand", "subtitle": "Start from brand onboarding", "tag": "Onboarding"},
]
# Only with DEMO_ADMIN=1 on a local demo (Settings.demo_admin): the admin console walkthrough.
ADMIN_PERSONA = {"id": "demo_admin", "role": "admin", "title": "Demo admin", "subtitle": "Admin console (local demo only)", "tag": "Admin"}
MAX_NEW_DEMO_USERS = 500


def _demo_only() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(404, "Demo sign-in is off. Sign in with your account.")


def _signed_in(request: Request, response: Response, user: dict, via: str, cookie: bool = True) -> dict:
    token = au.create_session(user["_id"], via, request.headers.get("user-agent"))
    if cookie:
        au.set_cookie(response, request, token)
    au.audit("signin", user["_id"], user["role"], via=via)
    out = {"user": au.public_user(user)}
    if not cookie:
        out["token"] = token  # Bearer use only: API clients and the demo's side-by-side frames
    return out


class SignupIn(BaseModel):
    email: str = Field(min_length=5, max_length=120, pattern=EMAIL)
    password: str = Field(min_length=8, max_length=128)
    name: str = Field(min_length=1, max_length=60)
    role: Literal["creator", "brand"]


@router.post("/signup")
def signup(body: SignupIn, request: Request, response: Response, background: BackgroundTasks):
    db = get_db()
    email = body.email.strip().lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = au.new_user(body.role, body.name.strip(), email=email, password_hash=au.hash_password(body.password), email_verified=False)
    au.audit("signup", user["_id"], user["role"], via="password")
    send = credentials.send_verification(user, str(request.base_url), quiet=True)
    if send:
        background.add_task(send)
    return _signed_in(request, response, user, "password")


class LoginIn(BaseModel):
    email: str = Field(min_length=3, max_length=120)
    password: str = Field(min_length=1, max_length=128)


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response):
    email = body.email.strip().lower()
    if au.login_throttled(email):
        raise HTTPException(429, "Too many wrong passwords. Wait 15 minutes and try again.")
    user = get_db().users.find_one({"email": email})
    if not user or not au.check_password(body.password, user.get("password_hash")):
        au.record_failed_login(email)
        au.audit("signin_failed", user["_id"] if user else None, None, via="password")
        raise HTTPException(401, "That email and password don't match an account.")
    if user.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    au.clear_failed_logins(email)
    return _signed_in(request, response, user, "password")


@router.post("/logout")
def logout(request: Request, response: Response):
    user = au.optional_user(request)
    token, _ = au.request_token(request)
    # Revoke what this request carries: the Bearer token and the cookie, if both are sent.
    for t in {token, request.cookies.get(au.SESSION_COOKIE)} - {None}:
        au.revoke_token(t)
    au.clear_cookie(response)
    if user:
        au.audit("signout", user["_id"], user["role"])
    return {"ok": True}


class DeleteAccountIn(BaseModel):
    confirm: Literal["DELETE"]  # typed by the person, so a stray click can't delete an account


@router.post("/delete-account")
def delete_account(body: DeleteAccountIn, response: Response, user: dict = Depends(au.current_user)):
    """Deletes the signed-in account and everything that is only its data (services/account.py)."""
    from ..services import account

    out = account.delete_account(user)
    au.clear_cookie(response)
    return {"deleted": out["deleted"]}


# ------------------------------------------------------------------ devices, passwords, email
@router.get("/sessions")
def sessions(request: Request, user: dict = Depends(au.current_user)):
    """The account's signed-in devices; `current` marks this one."""
    return {"items": au.list_sessions(user["_id"], getattr(request.state, "session_id", None))}


@router.post("/sessions/{sid}/revoke")
def revoke_session(request: Request, response: Response, sid: str = Path(pattern=r"^[0-9a-f]{16}$"), user: dict = Depends(au.current_user)):
    s = au.revoke_session(user["_id"], sid)
    if not s:
        raise HTTPException(404, "That device is already signed out.")
    if s["_id"] == getattr(request.state, "session_id", None):
        au.clear_cookie(response)
    au.audit("session_revoked", user["_id"], user["role"], device=s.get("device"))
    return {"ok": True}


@router.post("/sessions/revoke-others")
def revoke_other_sessions(request: Request, user: dict = Depends(au.current_user)):
    n = au.revoke_others(user["_id"], getattr(request.state, "session_id", None))
    au.audit("sessions_revoked", user["_id"], user["role"], count=n)
    return {"revoked": n}


class PasswordChangeIn(BaseModel):
    current: str = Field(min_length=1, max_length=128)
    new: str = Field(min_length=8, max_length=128)


@router.post("/password")
def change_password(body: PasswordChangeIn, request: Request, background: BackgroundTasks, user: dict = Depends(au.current_user)):
    ratelimit.enforce(f"pwchange:{user['_id']}", 10, 3600, "Too many tries. Wait an hour and try again.")
    send = credentials.change(user, body.current, body.new, getattr(request.state, "session_id", None))
    if send:
        background.add_task(send)
    return {"ok": True}


class ForgotIn(BaseModel):
    email: str = Field(min_length=3, max_length=120, pattern=EMAIL)


@router.post("/password/forgot")
def forgot_password(body: ForgotIn, request: Request, background: BackgroundTasks):
    email = body.email.strip().lower()
    ratelimit.enforce(f"pwforgot:{ratelimit.client_ip(request)}", 10, 3600, "Too many reset requests from here. Try again in an hour.")
    ratelimit.enforce(f"pwforgot:{au.hash_token(email)[:24]}", 3, 3600, "We've already sent a few links to this address. Check your inbox and spam, or try again in an hour.")
    send = credentials.request_reset(email, str(request.base_url))
    if send:
        background.add_task(send)
    return {"ok": True}


class ResetIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)
    password: str = Field(min_length=8, max_length=128)


@router.post("/password/reset")
def reset_password(body: ResetIn, request: Request, response: Response, background: BackgroundTasks):
    """Sets a new password from an emailed link, signs out every device, and signs this one in."""
    ratelimit.enforce(f"pwreset:{ratelimit.client_ip(request)}", 20, 3600, "Too many tries from here. Try again in an hour.")
    user, send = credentials.reset(body.token, body.password)
    if send:
        background.add_task(send)
    return _signed_in(request, response, user, "password_reset")


class VerifyIn(BaseModel):
    token: str = Field(min_length=20, max_length=100)


@router.post("/email/verify")
def verify_email(body: VerifyIn, request: Request):
    """The link from the verification email. Works without being signed in: the link is the proof."""
    ratelimit.enforce(f"emailverify:{ratelimit.client_ip(request)}", 30, 3600, "Too many tries from here. Try again in an hour.")
    user = credentials.verify(body.token)
    return {"email": user["email"], "role": user["role"]}


@router.post("/email/resend")
def resend_verification(request: Request, background: BackgroundTasks, user: dict = Depends(au.current_user)):
    if user.get("email_verified"):
        raise HTTPException(409, "Your email is already confirmed.")
    if not user.get("email"):
        raise HTTPException(409, "This account has no email address.")
    ratelimit.enforce(f"emailresend:{user['_id']}", 3, 3600, "We've sent a few links already. Check your inbox and spam, or try again in an hour.")
    send = credentials.send_verification(user, str(request.base_url))
    if not send:
        raise HTTPException(503, "Email isn't set up on this server yet.")
    background.add_task(send)
    return {"sent_to": user["email"]}


@router.get("/me")
def me(user: dict = Depends(au.current_user)):
    db = get_db()
    profile = None
    if user.get("creator_id"):
        c = db.creators.find_one({"_id": user["creator_id"]}, {"name": 1, "handle": 1})
        profile = {"id": c["_id"], "name": c["name"], "handle": c.get("handle")} if c else None
    elif user.get("brand_id"):
        b = db.brands.find_one({"_id": user["brand_id"]}, {"name": 1})
        profile = {"id": b["_id"], "name": b["name"]} if b else None
    return {"user": au.public_user(user), "profile": profile, "demo_mode": get_settings().demo_mode}


# ------------------------------------------------------------------ Firebase (Google, phone OTP)
class FirebaseIn(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)
    # Chosen once, at the first sign-in. Ignored for an existing account: a role never changes.
    role: Literal["creator", "brand"] | None = None
    name: str | None = Field(default=None, max_length=60)


def _firebase_account(claims: dict, role: str | None, name: str | None, via: str | None = None) -> tuple[dict, str | None]:
    """The account a verified Firebase token signs in to, created on the first sign-in.
    Returns it with a note when the requested side differs from the account's."""
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(401, "That sign-in couldn't be verified. Sign in again.")
    db = get_db()
    email = (claims.get("email") or "").strip().lower() or None
    verified_email = email if claims.get("email_verified") else None
    provider = via or (claims.get("firebase") or {}).get("sign_in_provider", "firebase")
    user = db.users.find_one({"firebase_uid": uid})
    if not user and verified_email:
        # An email-and-password account with the same verified email: link it, keep its role.
        user = db.users.find_one({"email": verified_email, "firebase_uid": {"$exists": False}})
        if user:
            # Google verified this address, so it counts as verified here too.
            db.users.update_one({"_id": user["_id"]}, {"$set": {"firebase_uid": uid, "email_verified": True}})
            user.update(firebase_uid=uid, email_verified=True)
            au.audit("link_firebase", user["_id"], user["role"], via=provider)
    note = None
    if user:
        if user.get("suspended"):
            raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
        if role and role != user["role"]:
            note = f"This account is a {user['role']} account. The side chosen at first sign-in can't change."
    else:
        if not role:
            raise HTTPException(409, "First sign-in: choose creator or brand.")
        name = (name or claims.get("name") or (email or "").split("@")[0] or claims.get("phone_number") or "New member").strip()[:60]
        fields = {"firebase_uid": uid, "phone": claims.get("phone_number")}
        if verified_email and not db.users.find_one({"email": verified_email}):
            fields.update(email=verified_email, email_verified=True)
        user = au.new_user(role, name, **fields)
        au.audit("signup", user["_id"], user["role"], via=provider)
    return user, note


@router.post("/firebase")
def firebase_signin(body: FirebaseIn, request: Request, response: Response):
    """Exchange a verified Firebase ID token for the app's own session."""
    claims = firebase_auth.verify(body.id_token)
    user, note = _firebase_account(claims, body.role, body.name)
    provider = (claims.get("firebase") or {}).get("sign_in_provider", "firebase")
    out = _signed_in(request, response, user, f"firebase:{provider}")
    if note:
        out["note"] = note
    return out


# ------------------------------------------------------------------ creators: Instagram and YouTube
SOCIAL_PER_HOUR = 30  # sign-in attempts per visitor IP


def _creator_next(path: str | None) -> str | None:
    """Where to land after an Instagram sign-in: only a page on the creator side."""
    return path if path and (path == "/creator" or path.startswith("/creator/")) and "//" not in path else None


@router.get("/instagram/start")
def instagram_start(request: Request, response: Response, next_path: str | None = Query(default=None, alias="next", max_length=300)):
    """"Continue with Instagram" (creators): the address of Instagram's official login.
    Instagram sends the browser back to /api/connect/instagram/callback. A short-lived
    cookie ties the sign-in to this browser; /oauth/complete checks it."""
    if not social_signin.instagram_configured():
        raise HTTPException(503, "Instagram sign-in isn't set up on this server (IG_APP_ID, IG_APP_SECRET, IG_REDIRECT_URI, TOKEN_ENC_KEY).")
    ratelimit.enforce(f"igsignin:{ratelimit.client_ip(request)}", SOCIAL_PER_HOUR, 3600, "Too many sign-in attempts from here. Try again in an hour.")
    cookie, binding = social_signin.new_binding()
    state = ig.new_state(None, None, purpose="signin", next_path=_creator_next(next_path), binding=binding)
    response.set_cookie(
        social_signin.BINDING_COOKIE,
        cookie,
        max_age=ig.STATE_TTL + social_signin.LOGIN_CODE_TTL,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/api/auth",
    )
    return {"url": ig.authorize_url(state)}


class CompleteIn(BaseModel):
    code: str = Field(min_length=20, max_length=200)


@router.post("/oauth/complete")
def oauth_complete(body: CompleteIn, request: Request, response: Response):
    """The second half of a redirect sign-in (Instagram): the one-time code the callback
    handed the browser becomes this browser's session, on the web app's own origin."""
    doc = social_signin.redeem_login_code(body.code, request.cookies.get(social_signin.BINDING_COOKIE))
    response.delete_cookie(social_signin.BINDING_COOKIE, path="/api/auth")
    user = get_db().users.find_one({"_id": doc["user_id"]})
    if not user:
        raise HTTPException(400, "That account no longer exists.")
    if user.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    out = _signed_in(request, response, user, doc["via"])
    out["next"] = doc.get("next")
    if doc.get("note"):
        out["note"] = doc["note"]
    return out


class YouTubeIn(BaseModel):
    id_token: str = Field(min_length=20, max_length=4096)
    # Google OAuth access token with youtube.readonly. Used once, never stored.
    access_token: str = Field(min_length=20, max_length=4096)
    name: str | None = Field(default=None, max_length=60)


@router.post("/youtube")
def youtube_signin(body: YouTubeIn, request: Request, response: Response):
    """"Continue with YouTube" (creators): a verified Google sign-in, plus the channel that
    Google account owns. A first sign-in creates a creator account."""
    if not social_signin.youtube_configured():
        raise HTTPException(503, "YouTube sign-in isn't set up on this server (Firebase and YOUTUBE_API_KEY).")
    ratelimit.enforce(f"ytsignin:{ratelimit.client_ip(request)}", SOCIAL_PER_HOUR, 3600, "Too many sign-in attempts from here. Try again in an hour.")
    claims = firebase_auth.verify(body.id_token)
    # Both checks run before any account is created or changed.
    channel = social_signin.owned_channel(body.access_token, social_signin.google_ids(claims))
    user, note = _firebase_account(claims, "creator", body.name or (channel or {}).get("title"), via="youtube")
    notes = [note] if note else []
    if channel:
        linked = social_signin.claim_channel(user, channel)
        if linked:
            notes.append(linked)
        if user.get("creator_id"):
            # The same Google consent covers YouTube Analytics: each sign-in refreshes it.
            from ..services import youtube_analytics as yta

            try:
                yta.connect(user["creator_id"], body.access_token)
            except Exception as e:  # Analytics is a bonus; sign-in goes ahead either way
                log.info("YouTube Analytics at sign-in skipped for %s (%s)", user["_id"], getattr(e, "detail", type(e).__name__))
    else:
        notes.append("This Google account doesn't have a YouTube channel, so no channel was linked.")
    out = _signed_in(request, response, user, "youtube")
    if notes:
        out["note"] = " ".join(notes)
    return out


# ------------------------------------------------------------------ demo mode
@router.get("/personas")
def personas():
    _demo_only()
    return PERSONAS + ([ADMIN_PERSONA] if get_settings().demo_admin else [])


class DemoLogin(BaseModel):
    persona: str = Field(min_length=2, max_length=40)
    # False: return a Bearer token instead of setting the cookie, so a creator phone
    # and a brand console can run side by side in one browser.
    cookie: bool = True


@router.post("/demo")
def demo_login(body: DemoLogin, request: Request, response: Response):
    _demo_only()
    db = get_db()
    p = next((p for p in PERSONAS if p["id"] == body.persona), None)
    if body.persona == ADMIN_PERSONA["id"]:
        user = db.users.find_one({"_id": DEMO_ADMIN_ID, "role": "admin", "demo": True}) if get_settings().demo_admin else None
        if not user:
            raise HTTPException(404, "The demo admin is off. Admins are granted on the server: python -m app.admin_cli grant <email>.")
        p = ADMIN_PERSONA
    elif p and p["id"].startswith("new_"):
        if db.users.count_documents({"demo": True, "seeded": {"$ne": True}}) >= MAX_NEW_DEMO_USERS:
            raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
        user = au.new_user(p["role"], p["title"], demo=True)
        au.audit("signup", user["_id"], user["role"], via="demo")
    else:
        # Any demo account by its profile id: seeded personas, onboarded demo creators and guest brands.
        user = db.users.find_one({"demo": True, "$or": [{"creator_id": body.persona}, {"brand_id": body.persona}]})
        if not user:
            raise HTTPException(404, "Persona data missing; reset the demo")
    if user.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    out = _signed_in(request, response, user, "demo", cookie=body.cookie)
    out["persona"] = p or {"id": body.persona, "role": user["role"], "title": user.get("name"), "subtitle": "", "tag": "Demo"}
    return out
