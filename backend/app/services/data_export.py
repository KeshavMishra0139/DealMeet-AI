"""Download my data: every record tied to an account, in one JSON file.

India's DPDP Act gives a person the right to a summary of the personal data held about
them; this is that summary, in a form they can keep or take elsewhere. It holds:

- the account (name, email, role, how it signs in, when it was made) and its signed-in
  devices;
- the creator or brand profile;
- every record that belongs to the account, by collection (see CREATOR, BRAND, ACCOUNT);
- the account's activity log (the audit entries for it, which are kept a year).

Left out on purpose:

- secrets: the password hash, sign-in and platform tokens and code hashes, wherever they
  sit in a record, are shown as "[redacted]".
- other people's private notes and choices: a brand's shortlist notes and offer drafts
  about a creator stay with the brand, and creators' saves of a brand stay with the
  creators (the brand sees them in the app only as creators allow).
"""
from __future__ import annotations

import json
import re
from collections.abc import Callable
from typing import Any

from ..config import now_iso
from ..db import get_db
from . import auth as au

MAX_PER_COLLECTION = 5000
# Field names that hold secrets: password, token(s), secrets, one-time codes (and the admins'
# two-step settings), and code hashes.
# Narrower than "anything with key or pass in it", so a person's own fields all come through.
SECRET = re.compile(r"(^|_)(password|token|secret|t?otp)(_|$)|(^|_)code_hash$")


def scrub(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: "[redacted]" if SECRET.search(k) else scrub(v) for k, v in value.items()}
    if isinstance(value, list):
        return [scrub(v) for v in value]
    return value

Query = Callable[[dict], dict | None]

# collection -> the query for this account's records in it, from its ids.
CREATOR: dict[str, Query] = {
    name: lambda ids: {"creator_id": ids["creator"]}
    for name in ("consents", "consent_audit", "deals", "plans", "invoices", "applications", "manual_metrics", "posts",
                 "metric_snapshots", "fan_proof", "coach_answers", "rate_cards", "kit_versions", "wishlists", "pitches")
}
BRAND: dict[str, Query] = {
    "listings": lambda ids: {"owner_id": ids["brand"]},
    "applications": lambda ids: {"$or": [{"lister_id": ids["brand"]}, {"listing_id": {"$in": ids["listings"]}}]},
    "deals": lambda ids: {"brand_id": ids["brand"]},
    "collectives": lambda ids: {"brand_id": ids["brand"]},
    "shortlists": lambda ids: {"brand_id": ids["brand"]},
    "offer_drafts": lambda ids: {"brand_id": ids["brand"]},
    "pitches": lambda ids: {"brand_id": ids["brand"]},
    "consents": lambda ids: {"lister_id": ids["brand"]},
    "payments": lambda ids: {"ref_id": {"$in": ids["deals"]}},
}
ACCOUNT: dict[str, Query] = {
    "connections": lambda ids: {"user_id": ids["user"]},
    "chats": lambda ids: {"user_id": ids["user"]},
    "assistant_proposals": lambda ids: {"user_id": ids["user"]},
    "reports": lambda ids: {"reporter_id": ids["user"]},
    "claim_requests": lambda ids: {"user_id": ids["user"]},
    "notifications": lambda ids: {"to": {"$in": [i for i in (ids["user"], ids["creator"], ids["brand"]) if i]}},
}


def _ids(user: dict) -> dict:
    db = get_db()
    bid = user.get("brand_id") if user.get("role") == "brand" else None
    return {
        "user": user["_id"],
        "creator": user.get("creator_id") if user.get("role") == "creator" else None,
        "brand": bid,
        "listings": [x["_id"] for x in db.listings.find({"owner_id": bid}, {"_id": 1})] if bid else [],
        "deals": [x["_id"] for x in db.deals.find({"brand_id": bid}, {"_id": 1})] + [x["_id"] for x in db.collectives.find({"brand_id": bid}, {"_id": 1})] if bid else [],
    }


def build(user: dict, current_session: str | None) -> dict:
    db = get_db()
    ids = _ids(user)
    queries = dict(ACCOUNT)
    if ids["creator"]:
        queries.update(CREATOR)
    if ids["brand"]:
        queries.update(BRAND)
    records, cut = {}, []
    for name in sorted(queries):
        rows = [scrub(d) for d in db[name].find(queries[name](ids)).limit(MAX_PER_COLLECTION + 1)]
        if len(rows) > MAX_PER_COLLECTION:
            cut.append(name)
            rows = rows[:MAX_PER_COLLECTION]
        if rows:
            records[name] = rows
    profile = None
    if ids["creator"]:
        profile = db.creators.find_one({"_id": ids["creator"]})
    elif ids["brand"]:
        profile = db.brands.find_one({"_id": ids["brand"]})
    activity = [scrub(e) for e in db.audit.find({"user_id": user["_id"]}).sort("ts", -1).limit(MAX_PER_COLLECTION)]
    au.audit("data_exported", user["_id"], user.get("role"), collections=len(records))
    return {
        "about": "Everything DealMeet AI holds that is tied to your account, as of exported_at. Secrets such as your password are never included.",
        "exported_at": now_iso(),
        "account": scrub(user) | {"sign_in_methods": au.public_user(user)["providers"]},
        "devices": au.list_sessions(user["_id"], current_session),
        "profile": scrub(profile) if profile else None,
        "records": records,
        "activity": activity,
        "truncated": cut,  # collections with more than MAX_PER_COLLECTION records, cut at that many
    }


def as_json(data: dict) -> bytes:
    return json.dumps(data, ensure_ascii=False, indent=2, default=str).encode()
