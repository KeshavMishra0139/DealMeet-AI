"""The administrator console: what needs attention, and actions that each need a reason
and are audited. The admin role is granted only on the server (app.admin_cli)."""
from __future__ import annotations

import re
import time
import uuid

from fastapi import HTTPException

from ..config import now_iso
from ..db import get_db
from . import auth as au
from . import campaigns as camp

SECRET_KEYS = re.compile(r"pass(word)?|token|secret|signature|hash|otp|key", re.I)
LOCK_WINDOW_S = 15 * 60
LOCK_AFTER = 5
REPORT_REASONS = ("spam", "scam_or_fraud", "fake_numbers", "harassment", "inappropriate", "impersonation", "other")
REPORTS_PER_DAY = 5


def redact(doc: dict) -> dict:
    """Defense in depth for the audit viewer: secret-looking fields never leave the server."""
    out = {}
    for k, v in doc.items():
        if SECRET_KEYS.search(k) and k not in ("ts",):
            out[k] = "[redacted]"
        elif isinstance(v, dict):
            out[k] = redact(v)
        else:
            out[k] = v
    return out


def _public_account(u: dict) -> dict:
    return {k: u.get(k) for k in ("_id", "role", "name", "email", "creator_id", "brand_id", "demo", "seeded", "suspended", "suspended_reason", "created_at")}


# ------------------------------------------------------------------ overview
def overview() -> dict:
    db = get_db()
    since = time.time() - LOCK_WINDOW_S
    failures: dict[str, int] = {}
    for f in db.login_failures.find({"at": {"$gte": since}}, {"email": 1}):
        failures[f["email"]] = failures.get(f["email"], 0) + 1
    locked = [{"email": e, "failures": n} for e, n in failures.items() if n >= LOCK_AFTER]
    reported: dict[str, int] = {}
    for r in db.reports.find({"status": "open", "target_type": "profile"}, {"target_id": 1}):
        reported[r["target_id"]] = reported.get(r["target_id"], 0) + 1
    suspicious = [{"profile_id": k, "open_reports": n} for k, n in reported.items() if n >= 2]
    payments: dict[str, int] = {}
    for p in db.payments.find({}, {"mode": 1, "status": 1}):
        key = f"{p.get('mode', 'unknown')}: {p.get('status', 'unknown')}"
        payments[key] = payments.get(key, 0) + 1
    errors = [
        {"creator_id": c.get("creator_id"), "platform": c.get("platform"), "status": c.get("status"), "error": c.get("last_error"), "at": c.get("last_sync_at")}
        for c in db.connections.find({"$or": [{"last_error": {"$nin": [None, ""]}}, {"status": {"$in": ["error", "expired"]}}]}).limit(50)
    ]
    from fastapi import Response

    from ..routers.meta import health

    system = health(Response())
    statuses: dict[str, int] = {}
    for x in db.listings.find({"type": {"$in": ["brand_campaign", "collective"]}}, {"status": 1}):
        s = camp.status_of(x)
        statuses[s] = statuses.get(s, 0) + 1
    roles: dict[str, int] = {}
    for u in db.users.find({}, {"role": 1}):
        roles[u["role"]] = roles.get(u["role"], 0) + 1
    return {
        "accounts": {"by_role": roles, "suspended": db.users.count_documents({"suspended": True})},
        "campaigns": statuses,
        "reports": {"open": db.reports.count_documents({"status": "open"})},
        "claims": {"pending": db.claim_requests.count_documents({"status": "pending"})},
        "removals": {"pending": db.removal_requests.count_documents({"status": "pending"})},
        "locked": locked,
        "suspicious": suspicious,
        "payments": payments,
        "payment_events": db.webhook_events.count_documents({}),
        "connection_errors": errors,
        "health": system,
    }


# ------------------------------------------------------------------ accounts
def accounts(q: str | None, role: str | None, suspended: bool | None, limit: int = 100) -> list[dict]:
    query: dict = {}
    if role:
        query["role"] = role
    if suspended is not None:
        query["suspended"] = True if suspended else {"$ne": True}
    if q:
        rx = {"$regex": re.escape(q), "$options": "i"}
        query["$or"] = [{"name": rx}, {"email": rx}, {"_id": rx}, {"creator_id": rx}, {"brand_id": rx}]
    return [_public_account(u) for u in get_db().users.find(query).sort("created_at", -1).limit(limit)]


def set_suspended(user_id: str, suspend: bool, reason: str, admin: dict) -> dict:
    db = get_db()
    u = db.users.find_one({"_id": user_id})
    if not u:
        raise HTTPException(404, "Account not found")
    if u["role"] == "admin":
        raise HTTPException(409, "Admin accounts are managed from the server (app.admin_cli).")
    if bool(u.get("suspended")) == suspend:
        return _public_account(u)  # already so
    update = {"suspended": suspend, "suspended_reason": reason if suspend else None, "suspended_at": now_iso() if suspend else None}
    db.users.update_one({"_id": user_id}, {"$set": update})
    if suspend:
        au.revoke_all(user_id)  # signs them out everywhere
    au.audit("admin_" + ("suspend" if suspend else "restore"), admin["_id"], "admin", target_user=user_id, reason=reason)
    return _public_account(db.users.find_one({"_id": user_id}))


# ------------------------------------------------------------------ campaigns
def campaigns(status: str | None) -> list[dict]:
    db = get_db()
    rows = []
    for x in db.listings.find({"type": {"$in": ["brand_campaign", "collective"]}}).sort("posted_on", -1):
        s = camp.status_of(x)
        if status and s != status:
            continue
        owner = db.brands.find_one({"_id": x["owner_id"]}, {"name": 1}) or {}
        rows.append({"id": x["_id"], "title": x["title"], "status": s, "owner": owner.get("name"), "owner_id": x["owner_id"], "deadline": x.get("deadline"),
                     "reports": db.reports.count_documents({"target_type": "campaign", "target_id": x["_id"], "status": "open"})})
    return rows


def close_campaign(listing_id: str, reason: str, admin: dict) -> dict:
    x = get_db().listings.find_one({"_id": listing_id})
    if not x:
        raise HTTPException(404, "Campaign not found")
    x, changed = camp.transition(x, "close", admin)
    au.audit("admin_close_campaign", admin["_id"], "admin", listing_id=listing_id, reason=reason, changed=changed)
    return {"id": listing_id, "status": camp.status_of(x)}


# ------------------------------------------------------------------ reports
def report(user: dict, target_type: str, target_id: str, reason: str, details: str | None) -> dict:
    """A signed-in user reports something they can see. Deals only by their parties."""
    db = get_db()
    if target_type == "campaign":
        x = db.listings.find_one({"_id": target_id})
        if not x or not camp.visible_to(x, user):
            raise HTTPException(404, "Campaign not found")
        if x.get("owner_id") in (user.get("brand_id"), user.get("creator_id")):
            raise HTTPException(409, "You can't report your own campaign.")
    elif target_type == "profile":
        c = db.creators.find_one({"_id": target_id}, {"discoverable": 1, "public_page": 1})
        b = db.brands.find_one({"_id": target_id, "removed": {"$ne": True}}, {"_id": 1})
        if not (b or (c and (c.get("discoverable", True) or c.get("public_page") is not False))):
            raise HTTPException(404, "Profile not found")
        if target_id in (user.get("creator_id"), user.get("brand_id")):
            raise HTTPException(409, "You can't report your own profile.")
    elif target_type == "pitch":
        p = db.pitches.find_one({"_id": target_id})
        if not p or not (p.get("brand_id") == user.get("brand_id") and p["status"] != "draft"):
            raise HTTPException(404, "Pitch not found")
    elif target_type == "deal":
        d = db.deals.find_one({"_id": target_id})
        if not d:
            raise HTTPException(404, "Deal not found")
        au.deal_side(user, d)  # only its creator and brand
    key = {"reporter_id": user["_id"], "target_type": target_type, "target_id": target_id, "status": "open"}
    same = db.reports.find_one(key)
    if same:
        return {"id": same["_id"], "status": "open", "duplicate": True}
    since = time.time() - 86_400
    if db.reports.count_documents({"reporter_id": user["_id"], "ts": {"$gte": since}}) >= REPORTS_PER_DAY:
        raise HTTPException(429, f"You can send {REPORTS_PER_DAY} reports a day. Try again tomorrow.")
    rid = f"rp_{uuid.uuid4().hex[:10]}"
    db.reports.insert_one({**key, "_id": rid, "reason": reason, "details": details, "at": now_iso(), "ts": time.time(), "reporter_role": user.get("role")})
    au.audit("report_filed", user["_id"], user.get("role"), report_id=rid, target_type=target_type, target_id=target_id)
    return {"id": rid, "status": "open", "duplicate": False}


def reports(status: str) -> list[dict]:
    return list(get_db().reports.find({"status": status}).sort("ts", -1).limit(200))


def resolve_report(report_id: str, resolution: str, reason: str, admin: dict) -> dict:
    db = get_db()
    r = db.reports.find_one({"_id": report_id})
    if not r:
        raise HTTPException(404, "Report not found")
    if r["status"] != "open":
        raise HTTPException(409, "This report is already resolved.")
    db.reports.update_one({"_id": report_id}, {"$set": {"status": "resolved", "resolution": resolution, "resolution_reason": reason, "resolved_at": now_iso(), "resolved_by": admin["_id"]}})
    au.audit("admin_resolve_report", admin["_id"], "admin", report_id=report_id, resolution=resolution, reason=reason)
    return db.reports.find_one({"_id": report_id})


# ------------------------------------------------------------------ audit log
def audit_log(action: str | None, user_id: str | None, since_ts: float | None, until_ts: float | None, limit: int) -> list[dict]:
    q: dict = {}
    if action:
        q["action"] = {"$regex": f"^{re.escape(action)}", "$options": "i"}
    if user_id:
        q["user_id"] = user_id
    if since_ts or until_ts:
        q["ts"] = {**({"$gte": since_ts} if since_ts else {}), **({"$lte": until_ts} if until_ts else {})}
    return [redact(e) for e in get_db().audit.find(q).sort("ts", -1).limit(limit)]
