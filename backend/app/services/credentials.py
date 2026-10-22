"""Password reset, password change and email verification, by links sent through
services/mailer.py.

- **Forgot password**: always answers the same way, so it never tells anyone whether an
  email has an account. If it does, a link is emailed; it works once, for 30 minutes.
  Asking again replaces the earlier link. The email is sent after the response, so the
  answer takes the same time either way.
- **Reset**: the link's token is stored only as a SHA-256 hash. A reset signs the account
  out everywhere, clears failed sign-ins, and counts as proof of the email address.
- **Change password** (signed in): needs the current password, and signs out every other
  device.
- **Verify email**: password sign-ups get a link, valid 48 hours; Google sign-in's
  verified addresses count as verified already. An unverified address can still sign in.
- After a reset or change, the account's address gets a short "your password was changed"
  notice, so a change nobody asked for doesn't go unnoticed.

Links point at FRONTEND_URL. Outside demo mode they're never built from the request's Host
header, which a visitor controls (a "reset poisoning" attack would send the victim a link
to another site).
"""
from __future__ import annotations

import logging
import secrets
import time
from collections.abc import Callable

from fastapi import HTTPException

from ..config import get_settings
from ..db import get_db
from . import auth as au
from . import mailer

log = logging.getLogger("jodidar.credentials")

RESET_TTL = 30 * 60
VERIFY_TTL = 48 * 3600
EXPIRED = "That link has expired or was already used. Ask for a new one."

Send = Callable[[], None]


def _site(request_base: str) -> str:
    """This site's address for emailed links."""
    s = get_settings()
    base = s.frontend_url or (request_base if s.demo_mode else None)
    if not base:
        raise HTTPException(503, "Emailed links need FRONTEND_URL (this site's address) set on the server.")
    return base.rstrip("/")


def _later(to: str, subject: str, text: str, kind: str) -> Send:
    """A send to run after the response; a failure is logged, never shown to the visitor."""

    def run() -> None:
        try:
            mailer.send(to, subject, text, kind=kind)
        except Exception as e:
            log.warning("Couldn't send %s email: %s", kind, getattr(e, "detail", type(e).__name__))

    return run


# ------------------------------------------------------------------ forgot and reset
def request_reset(email: str, request_base: str) -> Send | None:
    """The send to run, or None when there's nothing to send. Same answer to the visitor either way."""
    if not mailer.configured():
        raise HTTPException(503, "Password reset by email isn't set up on this server yet. Contact support to get back into your account.")
    site = _site(request_base)  # fails the same way for every email when links can't be built
    db = get_db()
    user = db.users.find_one({"email": email})
    if not user or user.get("demo") or user.get("suspended"):
        return None
    token = secrets.token_urlsafe(32)
    db.password_resets.delete_many({"user_id": user["_id"]})
    db.password_resets.insert_one({"_id": au.hash_token(token), "user_id": user["_id"], "email": email, "expires": time.time() + RESET_TTL})
    au.audit("password_reset_requested", user["_id"], user["role"])
    link = f"{site}/login/reset?t={token}"
    text = (
        f"Someone asked to reset the password for your DealMeet AI account ({email}).\n\n"
        f"Choose a new password here. The link works once, for the next 30 minutes:\n{link}\n\n"
        "If it wasn't you, ignore this email. Your password stays the same.\n"
    )
    return _later(email, "Reset your DealMeet AI password", text, "password_reset")


def reset(token: str, password: str) -> tuple[dict, Send | None]:
    """Sets the new password from a reset link. Returns the account and the notice to send."""
    db = get_db()
    doc = db.password_resets.find_one_and_delete({"_id": au.hash_token(token)})
    if not doc or doc["expires"] < time.time():
        raise HTTPException(400, EXPIRED)
    user = db.users.find_one({"_id": doc["user_id"]})
    if not user or user.get("suspended") or user.get("email") != doc["email"]:
        raise HTTPException(400, EXPIRED)
    # The link reached this inbox, so the address is proven too.
    db.users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": au.hash_password(password), "email_verified": True}})
    au.revoke_all(user["_id"])
    au.clear_failed_logins(doc["email"])
    db.email_verifications.delete_many({"user_id": user["_id"]})
    au.audit("password_reset", user["_id"], user["role"])
    return {**user, "email_verified": True}, _changed_notice(user)


def change(user: dict, current: str, new: str, keep_session: str | None) -> Send | None:
    """A signed-in password change. Other devices are signed out."""
    if not user.get("password_hash"):
        raise HTTPException(409, "This account signs in with Google, phone, Instagram or YouTube, so it has no password to change.")
    if not au.check_password(current, user["password_hash"]):
        au.audit("password_change_failed", user["_id"], user["role"])
        raise HTTPException(403, "Your current password isn't right.")
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"password_hash": au.hash_password(new)}})
    au.revoke_others(user["_id"], keep_session)
    au.audit("password_changed", user["_id"], user["role"])
    return _changed_notice(user)


def _changed_notice(user: dict) -> Send | None:
    if not (mailer.configured() and user.get("email")):
        return None
    text = (
        "The password for your DealMeet AI account was just changed, and every other device was signed out.\n\n"
        "If you did this, there's nothing more to do. If you didn't, use \"Forgot password?\" on the sign-in page "
        "to choose a new one straight away, and reply to this email so we can help.\n"
    )
    return _later(user["email"], "Your DealMeet AI password was changed", text, "password_changed")


# ------------------------------------------------------------------ email verification
def send_verification(user: dict, request_base: str, quiet: bool = False) -> Send | None:
    """A verification link for the account's email, or None when there's nothing to verify
    or email isn't set up. `quiet` (at sign-up): skip instead of failing when links can't be
    built, so signing up never fails over email."""
    email = user.get("email")
    if not (mailer.configured() and email) or user.get("email_verified") or user.get("demo"):
        return None
    try:
        site = _site(request_base)
    except HTTPException:
        if quiet:
            log.warning("No verification email for %s: FRONTEND_URL isn't set", user["_id"])
            return None
        raise
    token = secrets.token_urlsafe(32)
    db = get_db()
    db.email_verifications.delete_many({"user_id": user["_id"]})
    db.email_verifications.insert_one({"_id": au.hash_token(token), "user_id": user["_id"], "email": email, "expires": time.time() + VERIFY_TTL})
    link = f"{site}/verify-email?t={token}"
    text = (
        f"Confirm that {email} is your email for DealMeet AI:\n{link}\n\n"
        "The link works for 48 hours. If you didn't sign up, ignore this email and nothing happens.\n"
    )
    return _later(email, "Confirm your email for DealMeet AI", text, "verify_email")


def verify(token: str) -> dict:
    db = get_db()
    doc = db.email_verifications.find_one_and_delete({"_id": au.hash_token(token)})
    if not doc or doc["expires"] < time.time():
        raise HTTPException(400, EXPIRED)
    user = db.users.find_one({"_id": doc["user_id"]})
    if not user or user.get("email") != doc["email"]:
        raise HTTPException(400, EXPIRED)
    db.users.update_one({"_id": user["_id"]}, {"$set": {"email_verified": True}})
    au.audit("email_verified", user["_id"], user["role"])
    return {**user, "email_verified": True}
