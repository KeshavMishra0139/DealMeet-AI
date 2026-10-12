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
SYNTHETIC = "synthetic"  # data source of everything seeded: sample data, never shown as real
SEEDED = ("creators", "brands", "listings", "consents", "consent_audit", "deals", "invoices")


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


def seed_all(db, force: bool = False, sandbox: bool = True) -> dict:
    """Load the sample data. `sandbox` (demo mode) wipes every record first, since all of it
    is sandbox data. Otherwise (the seed script on a real database) only records marked
    synthetic are replaced, and real accounts and their data are left alone."""
    if not force and db.creators.count_documents({}) > 0:
        return {"seeded": False}
    if sandbox:
        for name in COLLECTIONS:
            if name != "ai_cache":  # cached AI copy stays valid across resets and saves paid calls
                db[name].delete_many({})
    else:
        for name in SEEDED:
            db[name].delete_many({"source": SYNTHETIC})
    creators = all_creators()
    brands, listings = _with_profiles(LISTERS, LISTINGS)
    for name, docs in (
        ("creators", creators),
        ("brands", brands),
        ("listings", listings),
        ("consents", CONSENTS),
        ("consent_audit", CONSENT_AUDIT),
        ("deals", DEALS),
        ("invoices", INVOICES),
    ):
        # Every seeded record is sample data, and says so.
        db[name].insert_many([{**copy.deepcopy(d), "source": SYNTHETIC} for d in docs])
    seed_users(db, creators, drop_sandbox_accounts=sandbox)
    counts = {name: db[name].count_documents({}) for name in COLLECTIONS}
    log.info("Seeded demo data: %s", counts)
    return {"seeded": True, "counts": counts}


def _with_profiles(listers: list[dict], listings: list[dict]) -> tuple[list[dict], list[dict]]:
    """Each lister gets a unique address (slug); each campaign's target audience is its owner's."""
    from ..services.brand_profile import unique_slug

    taken: set[str] = set()
    brands = []
    for b in listers:
        slug = unique_slug(b["name"], taken)
        taken.add(slug)
        brands.append({**b, "slug": slug})
    targets = {b["_id"]: b.get("target") or {} for b in listers}
    out = []
    for x in listings:
        t = targets.get(x["owner_id"], {})
        out.append({**x, "audience": x.get("audience") or {"ages": t.get("ages") or ["18-24", "25-34"], "gender": t.get("gender", "any")}})
    return brands, out


def seed_users(db, creators: list[dict], drop_sandbox_accounts: bool = True) -> None:
    """One demo account per seeded creator and lister, with stable ids so sessions
    survive a reset. In demo mode, accounts made during the demo (new personas, guest
    brands and sign-ups) are sandbox data too, and a reset removes them with their sessions."""
    if drop_sandbox_accounts:
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
