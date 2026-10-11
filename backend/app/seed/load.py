"""Load (or reload) all seed data into the database."""
from __future__ import annotations

import copy
import logging

from ..config import now_iso
from ..db import COLLECTIONS
from . import creator_a
from .creators import build_creator_b, build_roster
from .market import CONSENT_AUDIT, CONSENTS, DEALS, INVOICES, LISTERS, LISTINGS

log = logging.getLogger("jodidar.seed")

CONSENT_DEFAULTS = {"stats": True, "demographics": False, "rate_card": False}


def all_creators() -> list[dict]:
    a, prov = creator_a.build()
    a["provenance"] = prov
    a["provenance_default"] = "simulated"
    b = build_creator_b()
    b["provenance"] = {}
    b["provenance_default"] = "seed"
    rest = build_roster()
    for c in rest:
        c["provenance"] = {}
        c["provenance_default"] = "seed"
    creators = [a, b, *rest]
    for c in creators:
        c.setdefault("consent_defaults", dict(CONSENT_DEFAULTS))
    return creators


def seed_all(db, force: bool = False) -> dict:
    if not force and db.creators.count_documents({}) > 0:
        return {"seeded": False}
    for name in COLLECTIONS:
        if name != "ai_cache":  # cached AI copy stays valid across resets and saves paid calls
            db[name].delete_many({})
    creators = all_creators()
    db.creators.insert_many(copy.deepcopy(creators))
    db.brands.insert_many(copy.deepcopy(LISTERS))
    db.listings.insert_many(copy.deepcopy(LISTINGS))
    db.consents.insert_many(copy.deepcopy(CONSENTS))
    db.consent_audit.insert_many(copy.deepcopy(CONSENT_AUDIT))
    db.deals.insert_many(copy.deepcopy(DEALS))
    db.invoices.insert_many(copy.deepcopy(INVOICES))
    seed_users(db, creators)
    counts = {name: db[name].count_documents({}) for name in COLLECTIONS}
    log.info("Seeded demo data: %s", counts)
    return {"seeded": True, "counts": counts}


def seed_users(db, creators: list[dict]) -> None:
    """One demo account per seeded creator and lister, with stable ids so sessions
    survive a reset. Accounts made during the demo (new personas, guest brands and
    sign-ups) are sandbox data too, and a reset removes them with their sessions."""
    db.users.delete_many({"seeded": {"$ne": True}})
    users = [
        {"_id": f"us_{c['_id']}", "role": "creator", "name": c["name"], "creator_id": c["_id"], "brand_id": None}
        for c in creators
    ] + [
        {"_id": f"us_{b['_id']}", "role": "brand", "name": b["name"], "creator_id": None, "brand_id": b["_id"]}
        for b in LISTERS
    ]
    for u in users:
        u.update({"email": None, "demo": True, "seeded": True, "suspended": False, "created_at": now_iso()})
        db.users.replace_one({"_id": u["_id"]}, u, upsert=True)
    live = {u["_id"] for u in db.users.find({}, {"_id": 1})}
    db.sessions.delete_many({"user_id": {"$nin": list(live)}})
