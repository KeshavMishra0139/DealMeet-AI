"""A brand's saved shortlist per campaign, and the side-by-side compare view.

Rows are built with the same ranking as the matches, under the scopes each creator
shares with this brand today. A creator who stopped sharing shows as unavailable.
"""
from __future__ import annotations

from fastapi import HTTPException

from ..config import now_iso
from ..db import get_db
from ..engines.brand_matching import CRITERIA, rank_creator
from . import auth as au
from . import campaigns as camp
from . import consent as cs

MAX_ITEMS = 50
COMPARE_MIN, COMPARE_MAX = 2, 4


def _sync_application(listing: dict, creator_id: str, frm: str, to: str, user: dict) -> None:
    """Keep an applicant's status in step with the shortlist."""
    a = get_db().applications.find_one({"listing_id": listing["_id"], "creator_id": creator_id})
    if a and a["status"] in (frm, "opted_in" if frm == "applied" else frm):
        camp.set_application(listing, creator_id, to, user)


def add(listing: dict, brand: dict, creator_id: str, note: str | None, user: dict) -> dict:
    db = get_db()
    if camp.status_of(listing) == "closed":
        raise HTTPException(409, "This campaign is closed.")
    c = db.creators.find_one({"_id": creator_id})
    if not c or cs.scopes_for(c, brand["_id"]) is None:
        raise HTTPException(404, "Creator not available")
    key = {"listing_id": listing["_id"], "creator_id": creator_id}
    existing = db.shortlists.find_one(key)
    if not existing and db.shortlists.count_documents({"listing_id": listing["_id"]}) >= MAX_ITEMS:
        raise HTTPException(409, f"A shortlist holds up to {MAX_ITEMS} creators. Remove some first.")
    at = now_iso()
    db.shortlists.update_one(
        {"_id": f"sl_{listing['_id']}_{creator_id}"},
        {"$set": {**key, "brand_id": brand["_id"], "note": (note or "").strip() or None, "updated_at": at}, "$setOnInsert": {"added_at": at, "added_by": user["_id"]}},
        upsert=True,
    )
    if not existing:
        au.audit("shortlist_added", user["_id"], user.get("role"), listing_id=listing["_id"], creator_id=creator_id)
        _sync_application(listing, creator_id, "applied", "shortlisted", user)
    return items(listing, brand)


def remove(listing: dict, brand: dict, creator_id: str, user: dict) -> dict:
    res = get_db().shortlists.delete_one({"listing_id": listing["_id"], "creator_id": creator_id})
    if not res.deleted_count:
        raise HTTPException(404, "That creator isn't on the shortlist")
    au.audit("shortlist_removed", user["_id"], user.get("role"), listing_id=listing["_id"], creator_id=creator_id)
    if camp.status_of(listing) != "closed":
        _sync_application(listing, creator_id, "shortlisted", "applied", user)
    return items(listing, brand)


def _row(c: dict | None, entry: dict, listing: dict, brand: dict) -> dict:
    scopes = cs.scopes_for(c, brand["_id"]) if c else None
    if scopes is None:
        # Stopped sharing or left: nothing about them is shown.
        return {"id": entry["creator_id"], "available": False, "note": entry.get("note"), "added_at": entry.get("added_at")}
    return {**rank_creator(c, listing, brand, scopes), "available": True, "note": entry.get("note"), "added_at": entry.get("added_at")}


def items(listing: dict, brand: dict) -> dict:
    db = get_db()
    entries = list(db.shortlists.find({"listing_id": listing["_id"]}).sort("added_at", 1))
    creators = {c["_id"]: c for c in db.creators.find({"_id": {"$in": [e["creator_id"] for e in entries]}})}
    drafts = {d["creator_id"]: d for d in db.offer_drafts.find({"listing_id": listing["_id"]})}
    deals = {d["creator_id"]: d["stage"] for d in db.deals.find({"listing_id": listing["_id"], "brand_id": brand["_id"]})}
    rows = []
    for e in entries:
        r = _row(creators.get(e["creator_id"]), e, listing, brand)
        d = drafts.get(e["creator_id"])
        r["draft"] = {"id": d["_id"], "status": d["status"], "amount": d["amount"]} if d and r["available"] else None
        r["deal_stage"] = deals.get(e["creator_id"]) if r["available"] else None
        rows.append(r)
    return {"listing_id": listing["_id"], "items": rows, "max": MAX_ITEMS, "criteria": CRITERIA}


def compare(listing: dict, brand: dict, ids: list[str]) -> dict:
    ids = list(dict.fromkeys(ids))
    if not COMPARE_MIN <= len(ids) <= COMPARE_MAX:
        raise HTTPException(422, f"Pick {COMPARE_MIN} to {COMPARE_MAX} creators from the shortlist to compare.")
    db = get_db()
    on_list = {e["creator_id"]: e for e in db.shortlists.find({"listing_id": listing["_id"], "creator_id": {"$in": ids}})}
    if set(ids) - set(on_list):
        raise HTTPException(422, "Only creators on this campaign's shortlist can be compared.")
    rows = []
    for cid in ids:
        c = db.creators.find_one({"_id": cid})
        scopes = cs.scopes_for(c, brand["_id"]) if c else None
        if scopes is None:
            raise HTTPException(409, "One of these creators stopped sharing with you. Remove them from the shortlist.")
        cs.log_view(cid, brand["_id"], scopes)  # a side-by-side view is a profile view
        rows.append({**rank_creator(c, listing, brand, scopes), "note": on_list[cid].get("note")})
    return {"listing_id": listing["_id"], "items": rows, "criteria": CRITERIA}
