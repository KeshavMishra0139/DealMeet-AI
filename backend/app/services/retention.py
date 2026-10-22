"""How long records are kept, and the sweep that removes them when that time is up.

Short-lived security records go as soon as they can't be used any more:

- sessions: once expired, or 30 days after being signed out (the audit log keeps the
  sign-in and sign-out events).
- login codes, brand-claim codes, Instagram sign-in states and rate-limit counters: once
  expired.
- failed sign-in attempts: after a day (the lock looks back 15 minutes).

Logs are kept for a year, then removed:

- the audit log (sign-ups, sign-ins, every change and every admin action). India's
  CERT-In directions (April 2022) ask service providers to keep such logs for at least
  180 days.
- the email log (who was emailed what kind of message; never the body).

Kept on purpose, with the reason:

- email opt-outs: to keep honouring an unsubscribe.
- the consent history: proof of what a creator agreed to and when; it stays even after
  the account is deleted (services/account.py).
- payments, invoices and payment webhooks: financial records; tax law sets how long.

main.py runs the sweep at start and then every 6 hours; it's safe to run at any time.
"""
from __future__ import annotations

import logging
import time

from ..db import get_db

log = logging.getLogger("jodidar.retention")

DAY = 86400
SIGNED_OUT_SESSION_DAYS = 30
LOGIN_FAILURE_DAYS = 1
AUDIT_DAYS = 365
EMAIL_LOG_DAYS = 365
EVERY_S = 6 * 3600


def sweep(now: float | None = None) -> dict[str, int]:
    """Removes what's past its time. Returns how many records went, per collection."""
    db = get_db()
    now = time.time() if now is None else now
    rules = {
        "sessions": {"$or": [{"expires_at": {"$lt": now}}, {"revoked_at": {"$ne": None, "$lt": now - SIGNED_OUT_SESSION_DAYS * DAY}}]},
        "login_codes": {"expires": {"$lt": now}},
        "claim_codes": {"expires": {"$lt": now}},
        "oauth_states": {"expires": {"$lt": now}},
        "rate_limits": {"expires": {"$lt": now}},
        "login_failures": {"at": {"$lt": now - LOGIN_FAILURE_DAYS * DAY}},
        "audit": {"ts": {"$lt": now - AUDIT_DAYS * DAY}},
        "email_log": {"ts": {"$lt": now - EMAIL_LOG_DAYS * DAY}},
    }
    removed = {}
    for name, q in rules.items():
        n = db[name].delete_many(q).deleted_count
        if n:
            removed[name] = n
    if removed:
        log.info("Retention sweep removed %s", removed)
    return removed


def run_forever() -> None:
    """The sweep every 6 hours, after the one at start."""
    while True:
        time.sleep(EVERY_S)
        try:
            sweep()
        except Exception:  # a failed sweep is retried on the next round
            log.exception("Retention sweep failed")
