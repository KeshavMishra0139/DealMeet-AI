"""Consent ledger: creators choose exactly what each lister can see.

Rules
- A creator who isn't discoverable is invisible to every lister.
- A per-lister grant overrides the creator's default scopes.
- A revoked grant hides the creator from that lister entirely.
- Every grant, revoke, request and view is written to an append-only audit log.
"""
from __future__ import annotations

import uuid

from ..config import now_iso
from ..db import get_db

SCOPES = ("stats", "demographics", "rate_card")
SCOPE_LABELS = {
    "stats": "Reach and engagement stats",
    "demographics": "Audience demographics",
    "rate_card": "Rate card",
}


def scopes_for(creator: dict, lister_id: str) -> dict | None:
    """Scopes this lister may see, or None if the creator is hidden from them."""
    if not creator.get("discoverable", True):
        return None
    grant = get_db().consents.find_one({"creator_id": creator["_id"], "lister_id": lister_id})
    if grant:
        if grant["status"] == "revoked":
            return None
        if grant["status"] == "active":
            return {k: bool(grant["scopes"].get(k)) for k in SCOPES}
    defaults = creator.get("consent_defaults") or {}
    return {k: bool(defaults.get(k)) for k in SCOPES}


def source_for(creator_id: str, lister_id: str) -> str:
    g = get_db().consents.find_one({"creator_id": creator_id, "lister_id": lister_id})
    return "grant" if g and g["status"] == "active" else "default"


def audit(creator_id: str, lister_id: str, action: str, scopes: list[str], actor: str) -> None:
    get_db().consent_audit.insert_one(
        {
            "_id": f"au_{uuid.uuid4().hex[:10]}",
            "creator_id": creator_id,
            "lister_id": lister_id,
            "action": action,
            "scopes": scopes,
            "at": now_iso(),
            "actor": actor,
        }
    )


def grant(creator_id: str, lister_id: str, scopes: dict) -> dict:
    db = get_db()
    clean = {k: bool(scopes.get(k)) for k in SCOPES}
    existing = db.consents.find_one({"creator_id": creator_id, "lister_id": lister_id})
    doc = {
        "_id": existing["_id"] if existing else f"cs_{uuid.uuid4().hex[:10]}",
        "creator_id": creator_id,
        "lister_id": lister_id,
        "scopes": clean,
        "status": "active",
        "granted_at": now_iso(),
        "revoked_at": None,
    }
    db.consents.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    audit(creator_id, lister_id, "updated" if existing and existing["status"] == "active" else "granted", [k for k, v in clean.items() if v], "creator")
    return doc


def revoke(creator_id: str, lister_id: str) -> None:
    db = get_db()
    existing = db.consents.find_one({"creator_id": creator_id, "lister_id": lister_id})
    doc = existing or {"_id": f"cs_{uuid.uuid4().hex[:10]}", "creator_id": creator_id, "lister_id": lister_id, "scopes": {}, "granted_at": None}
    doc.update({"status": "revoked", "revoked_at": now_iso()})
    db.consents.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    audit(creator_id, lister_id, "revoked", [], "creator")


def request(creator_id: str, lister_id: str, scopes: list[str]) -> None:
    db = get_db()
    db.notifications.insert_one(
        {
            "_id": f"nt_{uuid.uuid4().hex[:10]}",
            "to": creator_id,
            "kind": "access_request",
            "lister_id": lister_id,
            "scopes": [s for s in scopes if s in SCOPES],
            "status": "pending",
            "at": now_iso(),
        }
    )
    audit(creator_id, lister_id, "requested", [s for s in scopes if s in SCOPES], "lister")


def log_view(creator_id: str, lister_id: str, scopes: dict) -> None:
    """Record that a lister opened this creator's profile and what they saw.
    Collapses repeat views within the same minute."""
    db = get_db()
    seen = [k for k, v in scopes.items() if v]
    last = db.consent_audit.find_one({"creator_id": creator_id, "lister_id": lister_id, "action": "viewed"}, sort=[("at", -1)])
    if last and last["at"][:16] == now_iso()[:16]:
        return
    audit(creator_id, lister_id, "viewed", seen, "lister")
