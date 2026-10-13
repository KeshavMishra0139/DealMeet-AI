"""Load (or reload) all seed data into the database."""
from __future__ import annotations

import copy
import logging

from ..config import get_settings, now_iso
from ..db import COLLECTIONS
from . import creator_a
from .creators import build_creator_b, build_roster
from .market import CONSENT_AUDIT, CONSENTS, DEALS, INVOICES, LISTERS, LISTINGS

log = logging.getLogger("jodidar.seed")

CONSENT_DEFAULTS = {"stats": True, "demographics": False, "rate_card": False}
SYNTHETIC = "synthetic"  # data source of everything seeded: sample data, never shown as real
DEMO_ADMIN_ID = "us_demo_admin"
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
    from ..services import reach

    reach.backfill(db)
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
        brands.append({"claimed": True, "public_handles": {}, **b, "slug": slug})
    targets = {b["_id"]: b.get("target") or {} for b in listers}
    out = []
    for x in listings:
        t = targets.get(x["owner_id"], {})
        out.append({**x, "audience": x.get("audience") or {"ages": t.get("ages") or ["18-24", "25-34"], "gender": t.get("gender", "any")}})
    return brands, out


# Fields that tie a record to a creator or a brand, across collections.
OWNER_FIELDS = ("creator_id", "brand_id", "owner_id", "lister_id", "to")


def remove_sample(db) -> dict:
    """Removes every sample record for a live site: records marked synthetic, the seeded
    demo accounts and their sessions, and anything tied to a sample creator or brand
    (plans, notifications, applications, deals...). Real accounts and their own data
    stay. Safe to repeat. Returns what was removed, per collection."""
    creator_ids = [c["_id"] for c in all_creators()]
    brand_ids = [b["_id"] for b in LISTERS]
    # A sample brand page a real (non-demo) account has claimed is theirs now; it stays.
    claimed = {b["_id"] for b in db.brands.find({"_id": {"$in": brand_ids}, "owner_user_id": {"$ne": None}}, {"owner_user_id": 1})
               if db.users.count_documents({"_id": b.get("owner_user_id"), "demo": {"$ne": True}})}
    brand_ids = [b for b in brand_ids if b not in claimed]
    # Demo accounts made during the demo (new personas, guest brands) and their profiles.
    demo_users = list(db.users.find({"$or": [{"seeded": True}, {"demo": True}]}, {"creator_id": 1, "brand_id": 1}))
    creator_ids += [u["creator_id"] for u in demo_users if u.get("creator_id")]
    brand_ids += [u["brand_id"] for u in demo_users if u.get("brand_id") and u["brand_id"] not in claimed]
    sample_ids = creator_ids + brand_ids
    removed: dict[str, int] = {}
    for name in COLLECTIONS:
        if name == "ai_cache":
            continue
        q: dict = {"$or": [{"source": SYNTHETIC}] + [{f: {"$in": sample_ids}} for f in OWNER_FIELDS]}
        if name in ("creators", "brands"):
            q["$or"].append({"_id": {"$in": sample_ids}})
        if name == "brands" and claimed:
            q = {"$and": [q, {"_id": {"$nin": list(claimed)}}]}
        n = db[name].delete_many(q).deleted_count
        if n:
            removed[name] = n
    users = [u["_id"] for u in demo_users]
    if users:
        removed["sessions"] = db.sessions.delete_many({"user_id": {"$in": users}}).deleted_count
        removed["users"] = db.users.delete_many({"_id": {"$in": users}}).deleted_count
    log.info("Removed sample data: %s", removed)
    return removed


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
    if get_settings().demo_admin:  # local walkthroughs only; see DEMO_ADMIN in .env.example
        users.append({"_id": DEMO_ADMIN_ID, "role": "admin", "name": "Demo admin", "creator_id": None, "brand_id": None})
    else:
        db.users.delete_one({"_id": DEMO_ADMIN_ID})
    for u in users:
        u.update({"email": None, "demo": True, "seeded": True, "suspended": False, "created_at": now_iso()})
        db.users.replace_one({"_id": u["_id"]}, u, upsert=True)
    live = {u["_id"] for u in db.users.find({}, {"_id": 1})}
    db.sessions.delete_many({"user_id": {"$nin": list(live)}})
