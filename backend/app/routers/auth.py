"""Sign-up, sign-in and sign-out.

Accounts are creators or brands; admin is granted only from the server
(`python -m app.admin_cli grant <email>`). In demo mode (DEMO_MODE=1) the persona
picker signs you in to a seeded demo account instead.
"""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import get_db
from ..services import auth as au
from ..services import firebase_auth

router = APIRouter(prefix="/api/auth", tags=["auth"])

EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"

PERSONAS = [
    {"id": "cr_a", "role": "creator", "title": "Creator A", "subtitle": "Anime-edit reels, Hindi and English, 21.3K followers", "tag": "Reference profile"},
    {"id": "cr_b", "role": "creator", "title": "Creator B", "subtitle": "Tamil home cooking, 2K followers, just starting", "tag": "Fictional"},
    {"id": "new_creator", "role": "creator", "title": "New creator", "subtitle": "Start from onboarding", "tag": "Onboarding"},
    {"id": "br_senpai", "role": "brand", "title": "Senpai Supply Co.", "subtitle": "Anime merch store", "tag": "Fictional brand"},
    {"id": "br_thalam", "role": "brand", "title": "Thalam Foods", "subtitle": "Regional masala and FMCG", "tag": "Fictional brand"},
    {"id": "new_brand", "role": "brand", "title": "New brand", "subtitle": "Start from brand onboarding", "tag": "Onboarding"},
]
MAX_NEW_DEMO_USERS = 500


def _demo_only() -> None:
    if not get_settings().demo_mode:
        raise HTTPException(404, "Demo sign-in is off. Sign in with your account.")


def _signed_in(request: Request, response: Response, user: dict, via: str, cookie: bool = True) -> dict:
    token = au.create_session(user["_id"], via)
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
def signup(body: SignupIn, request: Request, response: Response):
    db = get_db()
    email = body.email.strip().lower()
    if db.users.find_one({"email": email}):
        raise HTTPException(409, "An account with this email already exists. Sign in instead.")
    user = au.new_user(body.role, body.name.strip(), email=email, password_hash=au.hash_password(body.password))
    au.audit("signup", user["_id"], user["role"], via="password")
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


@router.post("/firebase")
def firebase_signin(body: FirebaseIn, request: Request, response: Response):
    """Exchange a verified Firebase ID token for the app's own session."""
    claims = firebase_auth.verify(body.id_token)
    uid = claims.get("uid") or claims.get("sub")
    if not uid:
        raise HTTPException(401, "That sign-in couldn't be verified. Sign in again.")
    db = get_db()
    email = (claims.get("email") or "").strip().lower() or None
    verified_email = email if claims.get("email_verified") else None
    provider = (claims.get("firebase") or {}).get("sign_in_provider", "firebase")
    user = db.users.find_one({"firebase_uid": uid})
    if not user and verified_email:
        # An email-and-password account with the same verified email: link it, keep its role.
        user = db.users.find_one({"email": verified_email, "firebase_uid": {"$exists": False}})
        if user:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"firebase_uid": uid}})
            user["firebase_uid"] = uid
            au.audit("link_firebase", user["_id"], user["role"], via=provider)
    note = None
    if user:
        if user.get("suspended"):
            raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
        if body.role and body.role != user["role"]:
            note = f"This account is a {user['role']} account. The side chosen at first sign-in can't change."
    else:
        if not body.role:
            raise HTTPException(409, "First sign-in: choose creator or brand.")
        name = (body.name or claims.get("name") or (email or "").split("@")[0] or claims.get("phone_number") or "New member").strip()[:60]
        fields = {"firebase_uid": uid, "phone": claims.get("phone_number")}
        if verified_email and not db.users.find_one({"email": verified_email}):
            fields["email"] = verified_email
        user = au.new_user(body.role, name, **fields)
        au.audit("signup", user["_id"], user["role"], via=provider)
    out = _signed_in(request, response, user, f"firebase:{provider}")
    if note:
        out["note"] = note
    return out


# ------------------------------------------------------------------ demo mode
@router.get("/personas")
def personas():
    _demo_only()
    return PERSONAS


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
    if p and p["id"].startswith("new_"):
        if db.users.count_documents({"demo": True, "seeded": {"$ne": True}}) >= MAX_NEW_DEMO_USERS:
            raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
        user = au.new_user(p["role"], p["title"], demo=True)
        au.audit("signup", user["_id"], user["role"], via="demo")
    else:
        # Any demo account by its profile id: seeded personas, onboarded demo creators and guest brands.
        user = db.users.find_one({"demo": True, "$or": [{"creator_id": body.persona}, {"brand_id": body.persona}]})
        if not user:
            raise HTTPException(404, "Persona data missing; reset the demo")
    out = _signed_in(request, response, user, "demo", cookie=body.cookie)
    out["persona"] = p or {"id": body.persona, "role": user["role"], "title": user.get("name"), "subtitle": "", "tag": "Demo"}
    return out
