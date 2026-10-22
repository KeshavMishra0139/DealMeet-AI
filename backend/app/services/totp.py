"""Two-step sign-in for admins: one-time codes from an authenticator app (RFC 6238).

An admin can suspend accounts and read the audit log, so a stolen password alone must not
be enough. The rules:

- Every admin turns it on before the admin console opens. The demo admin (local demos
  only, DEMO_ADMIN=1) is exempt.
- The secret is 20 random bytes, encrypted at rest with TOKEN_ENC_KEY; without that key
  two-step sign-in can't be set up and the console says so.
- A code is 6 digits for a 30-second step. The step before and after are accepted for
  clock drift, and a step that was used once can't be used again.
- 8 recovery codes are shown once at set-up and stored only as hashes; each works once.
- Passing the check marks this session only (sessions.mfa_at): each new sign-in asks
  again. 5 wrong codes in 15 minutes pause the check for 15 minutes.
- Lost the phone and the recovery codes: `python -m app.admin_cli reset-2fa <email>` on the
  server turns it off and signs the account out; the next sign-in sets it up again.

The admin routes check all of this on every request (routers/admin.py `require_admin`).
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import struct
import time
from urllib.parse import quote

from fastapi import HTTPException, Request

from ..config import get_settings
from ..db import get_db
from . import auth as au
from . import crypto, ratelimit

STEP = 30
DIGITS = 6
DRIFT = 1  # steps either side
RECOVERY_CODES = 8
ISSUER = "DealMeet AI"
WRONG_LIMIT, WRONG_WINDOW = 5, 15 * 60


def new_secret() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode().rstrip("=")


def code_at(secret: str, step: int) -> str:
    key = base64.b32decode(secret + "=" * (-len(secret) % 8))
    digest = hmac.new(key, struct.pack(">Q", step), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    number = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(number % 10**DIGITS).zfill(DIGITS)


def matching_step(secret: str, code: str, now: float | None = None, after: int = -1) -> int | None:
    """The step the code belongs to (this one, or one either side), if it's later than `after`."""
    now_step = int((time.time() if now is None else now) // STEP)
    for step in range(now_step - DRIFT, now_step + DRIFT + 1):
        if step > after and hmac.compare_digest(code_at(secret, step), code):
            return step
    return None


def otpauth_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    return f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}&digits={DIGITS}&period={STEP}"


def _hash(code: str) -> str:
    return hashlib.sha256(code.replace("-", "").strip().lower().encode()).hexdigest()


def _recovery_codes() -> list[str]:
    return [f"{secrets.token_hex(2)}-{secrets.token_hex(2)}" for _ in range(RECOVERY_CODES)]


# ------------------------------------------------------------------ who needs it
def required(user: dict) -> bool:
    return user.get("role") == "admin" and not (user.get("demo") and get_settings().demo_mode)


def enabled(user: dict) -> bool:
    return bool((user.get("totp") or {}).get("enabled_at"))


def _session(request: Request) -> dict | None:
    sid = getattr(request.state, "session_id", None)
    return get_db().sessions.find_one({"_id": sid}) if sid else None


def passed(request: Request) -> bool:
    return bool((_session(request) or {}).get("mfa_at"))


def status(user: dict, request: Request) -> dict:
    return {
        "required": required(user),
        "enabled": enabled(user),
        "passed": passed(request),
        "can_set_up": crypto.configured(),
        "recovery_codes_left": len((user.get("totp") or {}).get("recovery") or []),
    }


def require(user: dict, request: Request) -> None:
    """Admin routes: 403 until this session has passed two-step sign-in."""
    if not required(user):
        return
    if not enabled(user):
        raise HTTPException(403, "Turn on two-step sign-in to open the admin console.")
    if not passed(request):
        raise HTTPException(403, "Enter the code from your authenticator app to open the admin console.")


# ------------------------------------------------------------------ set-up and checks
def _mark_session(request: Request) -> None:
    sid = getattr(request.state, "session_id", None)
    if sid:
        get_db().sessions.update_one({"_id": sid}, {"$set": {"mfa_at": int(time.time())}})


def start(user: dict) -> dict:
    """A new secret to scan. It's kept as pending until a code from it is entered."""
    if enabled(user):
        raise HTTPException(409, "Two-step sign-in is already on.")
    if not crypto.configured():
        raise HTTPException(503, "Two-step sign-in needs TOKEN_ENC_KEY set on the server, to keep the secret encrypted.")
    secret = new_secret()
    get_db().users.update_one({"_id": user["_id"]}, {"$set": {"totp_pending": {"secret_enc": crypto.encrypt(secret), "at": int(time.time())}}})
    return {"secret": secret, "uri": otpauth_uri(secret, user.get("email") or user["_id"])}


def enable(user: dict, code: str, request: Request) -> list[str]:
    """Turns it on with a code from the pending secret. Returns the recovery codes, once."""
    pending = user.get("totp_pending") or {}
    secret = crypto.decrypt(pending.get("secret_enc") or "")
    if enabled(user) or not secret:
        raise HTTPException(409, "Start the set-up again.")
    _not_locked(user)
    step = matching_step(secret, code)
    if step is None:
        _wrong(user)
        raise HTTPException(400, "That code doesn't match. Check the time on your phone, and enter the newest code.")
    codes = _recovery_codes()
    get_db().users.update_one(
        {"_id": user["_id"]},
        {"$set": {"totp": {"secret_enc": pending["secret_enc"], "enabled_at": int(time.time()), "last_step": step, "recovery": [_hash(c) for c in codes]}},
         "$unset": {"totp_pending": ""}},
    )
    _mark_session(request)
    au.audit("admin_2fa_enabled", user["_id"], user["role"])
    return codes


def verify(user: dict, code: str, request: Request) -> dict:
    """Checks a code from the app, or a recovery code, and marks this session."""
    totp = user.get("totp") or {}
    if not enabled(user):
        raise HTTPException(409, "Two-step sign-in isn't on for this account.")
    _not_locked(user)
    db = get_db()
    code = code.strip()
    if code.isdigit():
        secret = crypto.decrypt(totp.get("secret_enc") or "")
        if not secret:
            raise HTTPException(503, "The two-step secret can't be read (TOKEN_ENC_KEY changed?). Use a recovery code.")
        step = matching_step(secret, code, after=totp.get("last_step", -1))
        # Only a later step: the same code can't be used twice, even in its 30 seconds.
        if step is None or not db.users.update_one({"_id": user["_id"], "totp.last_step": totp.get("last_step")}, {"$set": {"totp.last_step": step}}).modified_count:
            _wrong(user)
            raise HTTPException(400, "That code doesn't match, or it was already used. Enter the newest code from your app.")
        used = "app"
    else:
        h = _hash(code)
        if not db.users.update_one({"_id": user["_id"], "totp.recovery": h}, {"$pull": {"totp.recovery": h}}).modified_count:
            _wrong(user)
            raise HTTPException(400, "That recovery code doesn't match, or it was already used.")
        used = "recovery_code"
    _mark_session(request)
    au.audit("admin_2fa_passed", user["_id"], user["role"], via=used)
    left = len((db.users.find_one({"_id": user["_id"]}, {"totp.recovery": 1}) or {}).get("totp", {}).get("recovery") or [])
    return {"ok": True, "recovery_codes_left": left}


def _not_locked(user: dict) -> None:
    if ratelimit.used(f"mfa:{user['_id']}", WRONG_WINDOW) >= WRONG_LIMIT:
        raise HTTPException(429, "Too many wrong codes. Wait 15 minutes and try again.")


def _wrong(user: dict) -> None:
    ratelimit.hit(f"mfa:{user['_id']}", WRONG_LIMIT, WRONG_WINDOW)
    au.audit("admin_2fa_failed", user["_id"], user.get("role"))


def reset(user_id: str) -> None:
    """Turns two-step sign-in off (admin_cli reset-2fa) and signs the account out everywhere."""
    get_db().users.update_one({"_id": user_id}, {"$unset": {"totp": "", "totp_pending": ""}})
    au.revoke_all(user_id)
