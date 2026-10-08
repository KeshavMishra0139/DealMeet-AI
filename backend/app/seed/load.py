"""Load (or reload) all seed data into the database."""
from __future__ import annotations

import copy
import logging

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
        db[name].delete_many({})
    creators = all_creators()
    db.creators.insert_many(copy.deepcopy(creators))
    db.brands.insert_many(copy.deepcopy(LISTERS))
    db.listings.insert_many(copy.deepcopy(LISTINGS))
    db.consents.insert_many(copy.deepcopy(CONSENTS))
    db.consent_audit.insert_many(copy.deepcopy(CONSENT_AUDIT))
    db.deals.insert_many(copy.deepcopy(DEALS))
    db.invoices.insert_many(copy.deepcopy(INVOICES))
    counts = {name: db[name].count_documents({}) for name in COLLECTIONS}
    log.info("Seeded demo data: %s", counts)
    return {"seeded": True, "counts": counts}
