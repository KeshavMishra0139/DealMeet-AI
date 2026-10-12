"""Accounts, server-side sessions and ownership checks.

- A session is a random token. The browser keeps it in an HttpOnly, SameSite=Lax
  cookie; API clients (and the demo's side-by-side frames) send it as a Bearer
  header instead. Only its SHA-256 hash is stored, it expires after
  SESSION_HOURS (72 by default) and signing out revokes it.
- Every private route depends on `current_user`, then checks that the signed-in
  account owns the creator, brand, listing, deal, collective or invoice it touches.
  Roles and owner ids always come from the session, never from the request body.
- Passwords are hashed with scrypt (standard library) and never logged.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import time
import uuid
from typing import Any

from fastapi import Depends, HTTPException, Request, Response

from ..config import get_settings, now_iso
from ..db import get_db

SESSION_COOKIE = "jd_session"
ROLES = ("creator", "brand", "admin")
SIGNUP_ROLES = ("creator", "brand")  # admin is granted only from the server
MAX_FAILED_LOGINS = 5
FAILED_WINDOW = 15 * 60


# ------------------------------------------------------------------ passwords
def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 2**14, 8, 1
    digest = hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, dklen=32)
    return f"scrypt${n}${r}${p}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def check_password(password: str, stored: str | None) -> bool:
    try:
        algo, n, r, p, salt, digest = (stored or "").split("$")
        if algo != "scrypt":
            return False
        test = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(test, base64.b64decode(digest))
    except (ValueError, TypeError):
        return False


# ------------------------------------------------------------------ sessions
def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def create_session(user_id: str, via: str) -> str:
    token = secrets.token_urlsafe(32)
    now = int(time.time())
    get_db().sessions.insert_one(
        {
            "_id": hash_token(token),
            "user_id": user_id,
            "via": via,
            "created_at": now,
            "expires_at": now + get_settings().session_hours * 3600,
            "revoked_at": None,
        }
    )
    return token


def revoke_token(token: str) -> None:
    get_db().sessions.update_one({"_id": hash_token(token), "revoked_at": None}, {"$set": {"revoked_at": int(time.time())}})


def revoke_all(user_id: str) -> None:
    get_db().sessions.update_many({"user_id": user_id, "revoked_at": None}, {"$set": {"revoked_at": int(time.time())}})


def set_cookie(response: Response, request: Request, token: str) -> None:
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=get_settings().session_hours * 3600,
        httponly=True,
        samesite="lax",
        secure=request.url.scheme == "https",
        path="/",
    )


def clear_cookie(response: Response) -> None:
    response.delete_cookie(SESSION_COOKIE, path="/")


def request_token(request: Request) -> tuple[str | None, str]:
    """(token, how it was sent). A Bearer header wins over the cookie."""
    auth = request.headers.get("authorization", "")
    if auth[:7].lower() == "bearer ":
        return auth[7:].strip() or None, "bearer"
    return request.cookies.get(SESSION_COOKIE), "cookie"


def _resolve(request: Request) -> tuple[dict | None, str]:
    token, _ = request_token(request)
    if not token:
        return None, "Sign in to continue."
    db = get_db()
    s = db.sessions.find_one({"_id": hash_token(token)})
    if not s or s.get("revoked_at") or s["expires_at"] <= time.time():
        return None, "Your session has expired. Sign in again."
    user = db.users.find_one({"_id": s["user_id"]})
    if not user:
        return None, "Your session has expired. Sign in again."
    return user, ""


def _remember(request: Request, user: dict) -> None:
    # Read by the audit middleware after the response.
    request.state.user_id = user["_id"]
    request.state.role = user.get("role")


def current_user(request: Request) -> dict:
    user, reason = _resolve(request)
    if user is None:
        raise HTTPException(401, reason)
    if user.get("suspended"):
        raise HTTPException(403, "This account is suspended. Contact support if you think this is a mistake.")
    _remember(request, user)
    return user


def optional_user(request: Request) -> dict | None:
    user, _ = _resolve(request)
    if user is None or user.get("suspended"):
        return None
    _remember(request, user)
    return user


# ------------------------------------------------------------------ ownership
def require_creator(user: dict, creator_id: str) -> None:
    if user.get("role") != "creator" or not user.get("creator_id"):
        raise HTTPException(403, "Only the creator who owns this profile can do that.")
    if user["creator_id"] != creator_id:
        raise HTTPException(403, "That creator profile belongs to another account.")


def require_brand(user: dict, brand_id: str) -> None:
    if user.get("role") != "brand" or not user.get("brand_id"):
        raise HTTPException(403, "Only the brand that owns this account can do that.")
    if user["brand_id"] != brand_id:
        raise HTTPException(403, "That brand belongs to another account.")


def require_role(user: dict, role: str) -> None:
    if user.get("role") != role:
        raise HTTPException(403, f"Only {role} accounts can do that.")


def own_creator(creator_id: str, user: dict = Depends(current_user)) -> dict:
    """Dependency for routes with a {creator_id} path parameter."""
    require_creator(user, creator_id)
    return user


def own_brand(brand_id: str, user: dict = Depends(current_user)) -> dict:
    """Dependency for routes with a {brand_id} path parameter."""
    require_brand(user, brand_id)
    return user


def profile_id(user: dict) -> str | None:
    return user.get("creator_id") if user.get("role") == "creator" else user.get("brand_id")


def require_listing_owner(user: dict, listing: dict) -> None:
    if not profile_id(user) or listing.get("owner_id") != profile_id(user):
        raise HTTPException(403, "That campaign belongs to another account.")


def deal_side(user: dict, deal: dict) -> str:
    """'creator' or 'brand': which party of the deal this account is. Anyone else gets 403."""
    if user.get("role") == "creator" and user.get("creator_id") and deal.get("creator_id") == user["creator_id"]:
        return "creator"
    if user.get("role") == "brand" and user.get("brand_id") and deal.get("brand_id") == user["brand_id"]:
        return "brand"
    raise HTTPException(403, "Only the creator and the brand on this deal can see it.")


# ------------------------------------------------------------------ users
def public_user(user: dict) -> dict:
    """What the signed-in person sees about their own account. Never the password hash."""
    return {
        "id": user["_id"],
        "role": user.get("role"),
        "name": user.get("name"),
        "email": user.get("email"),
        "creator_id": user.get("creator_id"),
        "brand_id": user.get("brand_id"),
        "demo": bool(user.get("demo")),
        "providers": [k for k, present in (("password", user.get("password_hash")), ("firebase", user.get("firebase_uid"))) if present],
    }


def new_user(role: str, name: str, **fields: Any) -> dict:
    if role not in ROLES:
        raise ValueError(role)
    user = {
        "_id": f"us_{uuid.uuid4().hex[:12]}",
        "role": role,
        "name": name,
        "email": None,
        "creator_id": None,
        "brand_id": None,
        "demo": False,
        "suspended": False,
        "created_at": now_iso(),
        **fields,
    }
    get_db().users.insert_one(user)
    return user


def link_profile(user: dict, profile: str) -> None:
    key = "creator_id" if user["role"] == "creator" else "brand_id"
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {key: profile}})
    user[key] = profile


def login_throttled(email: str) -> bool:
    cutoff = time.time() - FAILED_WINDOW
    return get_db().login_failures.count_documents({"email": email, "at": {"$gt": cutoff}}) >= MAX_FAILED_LOGINS


def record_failed_login(email: str) -> None:
    get_db().login_failures.insert_one({"_id": uuid.uuid4().hex, "email": email, "at": time.time()})


def clear_failed_logins(email: str) -> None:
    get_db().login_failures.delete_many({"email": email})


# ------------------------------------------------------------------ audit
def audit(action: str, user_id: str | None = None, role: str | None = None, **detail: Any) -> None:
    """Append-only record of sign-ups, sign-ins and every write. Never pass secrets in `detail`."""
    get_db().audit.insert_one(
        {
            "_id": f"ev_{uuid.uuid4().hex[:14]}",
            "at": now_iso(),
            "ts": time.time(),
            "action": action,
            "user_id": user_id,
            "role": role,
            **detail,
        }
    )
