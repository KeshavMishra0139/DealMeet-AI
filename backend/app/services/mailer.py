"""Outgoing email over SMTP, so any provider works (Amazon SES, Postmark, Resend, Brevo,
Google Workspace and others all offer an SMTP endpoint).

Settings: SMTP_HOST, SMTP_PORT (587 with STARTTLS, or 465 with TLS from the start),
SMTP_USER, SMTP_PASSWORD and EMAIL_FROM. SMTP_STARTTLS=0 is for a local mail catcher only. Without a host and a sender nothing is sent:
`configured()` is False and callers tell the person email isn't set up.

- Every message is recorded in `email_log` (to, kind, subject, status, when), never its
  body, and never the SMTP password.
- Messages nobody asked for (kind "invite") carry a signed unsubscribe link and the
  List-Unsubscribe headers, and are never sent to an address in `email_optouts`.
  Messages a person asked for themselves (a verification code) are always sent.
- The unsubscribe signing key is random, made once and kept in the database
  (`app_secrets`), so links keep working across restarts.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import logging
import secrets
import smtplib
import ssl
import time
import uuid
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

from fastapi import HTTPException
from pymongo import ReturnDocument

from ..config import get_settings, now_iso
from ..db import get_db

log = logging.getLogger("jodidar.email")

UNSOLICITED = {"invite"}  # kinds that must respect opt-outs and carry an unsubscribe link
TIMEOUT = 15


class EmailNotConfigured(HTTPException):
    def __init__(self) -> None:
        super().__init__(503, "Email isn't set up on this server (SMTP_HOST and EMAIL_FROM).")


def configured() -> bool:
    s = get_settings()
    return bool(s.smtp_host and s.email_from)


def normalise(address: str) -> str:
    return parseaddr(address or "")[1].strip().lower()


def domain_of(address: str) -> str:
    return normalise(address).rpartition("@")[2]


# ------------------------------------------------------------------ opt-outs
def _signing_key() -> bytes:
    db = get_db()
    doc = db.app_secrets.find_one_and_update(
        {"_id": "email_unsubscribe"}, {"$setOnInsert": {"key": secrets.token_hex(32)}}, upsert=True, return_document=ReturnDocument.AFTER
    )
    return bytes.fromhex(doc["key"])


def unsubscribe_token(address: str) -> str:
    addr = normalise(address)
    sig = hmac.new(_signing_key(), addr.encode(), hashlib.sha256).hexdigest()[:32]
    return f"{base64.urlsafe_b64encode(addr.encode()).decode().rstrip('=')}.{sig}"


def address_from_token(token: str) -> str | None:
    """The address a valid token was made for, or None for a forged or broken one."""
    raw, _, sig = (token or "").partition(".")
    try:
        addr = base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4)).decode()
    except (ValueError, UnicodeDecodeError):
        return None
    good = hmac.new(_signing_key(), addr.encode(), hashlib.sha256).hexdigest()[:32]
    return addr if addr and hmac.compare_digest(good, sig) else None


def opted_out(address: str) -> bool:
    return bool(get_db().email_optouts.count_documents({"_id": normalise(address)}))


def opt_out(address: str, via: str) -> None:
    get_db().email_optouts.update_one({"_id": normalise(address)}, {"$setOnInsert": {"at": now_iso(), "via": via}}, upsert=True)


# ------------------------------------------------------------------ sending
def send(to: str, subject: str, text: str, kind: str, unsubscribe_url: str | None = None) -> dict:
    """Sends one plain-text message. Raises EmailNotConfigured (503) without SMTP settings,
    409 for an opted-out address on an unsolicited message, 502 when the provider fails."""
    if not configured():
        raise EmailNotConfigured()
    s = get_settings()
    addr = normalise(to)
    if "@" not in addr:
        raise HTTPException(422, "That isn't an email address.")
    if kind in UNSOLICITED:
        if opted_out(addr):
            raise HTTPException(409, "This address asked not to get these emails.")
        if not unsubscribe_url:
            raise ValueError("Unsolicited email needs an unsubscribe link")
    msg = EmailMessage()
    msg["From"] = s.email_from
    msg["To"] = addr
    msg["Subject"] = subject
    msg["Message-ID"] = make_msgid(domain=domain_of(parseaddr(s.email_from)[1]) or None)
    if unsubscribe_url:
        msg["List-Unsubscribe"] = f"<{unsubscribe_url}>"
        msg["List-Unsubscribe-Post"] = "List-Unsubscribe=One-Click"
    msg.set_content(text)
    entry = {"_id": f"em_{uuid.uuid4().hex[:12]}", "to": addr, "kind": kind, "subject": subject, "at": now_iso(), "ts": time.time()}
    try:
        context = ssl.create_default_context()
        if s.smtp_port == 465:
            server = smtplib.SMTP_SSL(s.smtp_host, s.smtp_port, timeout=TIMEOUT, context=context)
        else:
            server = smtplib.SMTP(s.smtp_host, s.smtp_port, timeout=TIMEOUT)
        with server:
            if s.smtp_port != 465 and s.smtp_starttls:
                server.starttls(context=context)
            if s.smtp_user:
                server.login(s.smtp_user, s.smtp_password or "")
            server.send_message(msg)
    except (smtplib.SMTPException, OSError) as e:
        log.warning("Email to %s failed: %s", domain_of(addr), type(e).__name__)  # never the address or password
        get_db().email_log.insert_one({**entry, "status": "failed", "error": type(e).__name__})
        raise HTTPException(502, "The email couldn't be sent. Try again in a few minutes.") from None
    get_db().email_log.insert_one({**entry, "status": "sent"})
    return {"status": "sent", "id": entry["_id"]}
