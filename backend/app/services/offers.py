"""Offers from a brand to a creator, and offer drafts from a campaign shortlist.

A draft is editable and is sent only after an explicit confirm. There is never more
than one open offer from a brand to the same creator for the same campaign.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from ..config import now_iso
from ..db import get_db
from ..engines.fair_price import fair_price
from . import auth as au
from . import campaigns as camp
from . import consent as cs

CLOSED_STAGES = ("paid", "declined", "cancelled", "expired")


def open_offer(brand_id: str, creator_id: str, listing_id: str | None) -> dict | None:
    if not listing_id:
        return None
    return get_db().deals.find_one({"brand_id": brand_id, "creator_id": creator_id, "listing_id": listing_id, "stage": {"$nin": list(CLOSED_STAGES)}})


def create_offer(brand: dict, creator: dict, listing: dict | None, amount: int, message: str | None) -> dict:
    """Creates the deal. Checks consent, that the campaign is live and that no open
    offer exists for this creator and campaign."""
    db = get_db()
    if cs.scopes_for(creator, brand["_id"]) is None:
        raise HTTPException(404, "Creator not available")
    if listing:
        camp.require_live(listing, "taking offers")
        if open_offer(brand["_id"], creator["_id"], listing["_id"]):
            raise HTTPException(409, f"You already have an open offer to {creator['name']} for this campaign.")
    if db.deals.count_documents({"brand_id": brand["_id"]}) >= 50:
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")} if listing else {"deliverables": [{"kind": "reel", "count": 1}]}
    fp = fair_price(creator, brand, terms, with_model=False)
    did = f"dl_{uuid.uuid4().hex[:10]}"
    at = now_iso()
    db.deals.insert_one(
        {
            "_id": did,
            "kind": "single",
            "listing_id": listing["_id"] if listing else None,
            "brand_id": brand["_id"],
            "creator_id": creator["_id"],
            "amount": amount,
            "fair_at_offer": fp["total"],
            "deliverables": terms.get("deliverables"),
            "usage_rights_days": terms.get("usage_rights_days") or 0,
            "exclusivity_days": terms.get("exclusivity_days") or 0,
            "stage": "offer",
            "message": message,
            "timeline": [{"stage": "offer", "at": at, "note": f"Offer sent by {brand['name']}"}],
            "created_at": at,
        }
    )
    camp.mark_offered(listing["_id"] if listing else None, creator["_id"], did)
    below = 1 - amount / fp["total"] if fp["total"] else 0
    return {"id": did, "fair": fp["total"], "below_pct": round(below * 100)}


# ------------------------------------------------------------------ drafts
def _draft_id(listing_id: str, creator_id: str) -> str:
    return f"od_{listing_id}_{creator_id}"


def draft_view(d: dict) -> dict:
    c = get_db().creators.find_one({"_id": d["creator_id"]}, {"name": 1, "avatar_hue": 1, "is_reference": 1})
    return {
        "id": d["_id"],
        "listing_id": d["listing_id"],
        "creator_id": d["creator_id"],
        "creator_name": c["name"] if c else None,
        "avatar_hue": (c or {}).get("avatar_hue", 260),
        "is_reference": (c or {}).get("is_reference", False),
        "amount": d["amount"],
        "message": d.get("message"),
        "fair_estimate": d.get("fair_estimate"),
        "status": d["status"],
        "deal_id": d.get("deal_id"),
        "updated_at": d.get("updated_at"),
    }


def list_drafts(listing: dict) -> list[dict]:
    return [draft_view(d) for d in get_db().offer_drafts.find({"listing_id": listing["_id"]}).sort("updated_at", -1)]


def own_draft(draft_id: str, user: dict) -> dict:
    d = get_db().offer_drafts.find_one({"_id": draft_id})
    if not d:
        raise HTTPException(404, "Draft not found")
    if d["brand_id"] != user.get("brand_id"):
        raise HTTPException(403, "That draft belongs to another account.")
    return d


def create_draft(listing: dict, brand: dict, creator_id: str, amount: int | None, message: str | None, user: dict) -> tuple[dict, bool]:
    db = get_db()
    if not db.shortlists.count_documents({"listing_id": listing["_id"], "creator_id": creator_id}):
        raise HTTPException(409, "Add the creator to this campaign's shortlist first.")
    c = db.creators.find_one({"_id": creator_id})
    if not c or cs.scopes_for(c, brand["_id"]) is None:
        raise HTTPException(404, "Creator not available")
    if camp.status_of(listing) == "closed":
        raise HTTPException(409, "This campaign is closed.")
    if open_offer(brand["_id"], creator_id, listing["_id"]):
        raise HTTPException(409, f"You already have an open offer to {c['name']} for this campaign.")
    did = _draft_id(listing["_id"], creator_id)
    existing = db.offer_drafts.find_one({"_id": did})
    if existing and existing["status"] in ("draft", "sending"):
        return draft_view(existing), False  # one draft per creator per campaign
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    fair = fair_price(c, brand, terms, with_model=False)
    at = now_iso()
    doc = {
        "_id": did,
        "listing_id": listing["_id"],
        "brand_id": brand["_id"],
        "creator_id": creator_id,
        "amount": amount or fair["total"],
        "message": message,
        "fair_estimate": {"total": fair["total"], "range": fair["range"]},
        "status": "draft",
        "deal_id": None,
        "created_at": at,
        "updated_at": at,
    }
    db.offer_drafts.replace_one({"_id": did}, doc, upsert=True)
    au.audit("offer_draft_created", user["_id"], user.get("role"), listing_id=listing["_id"], creator_id=creator_id)
    return draft_view(doc), True


def update_draft(d: dict, changes: dict, user: dict) -> dict:
    if d["status"] != "draft":
        raise HTTPException(409, "This draft was already sent.")
    if changes:
        changes["updated_at"] = now_iso()
        get_db().offer_drafts.update_one({"_id": d["_id"]}, {"$set": changes})
        au.audit("offer_draft_edited", user["_id"], user.get("role"), draft_id=d["_id"], fields=sorted(k for k in changes if k != "updated_at"))
    return draft_view(get_db().offer_drafts.find_one({"_id": d["_id"]}))


def send_draft(d: dict, user: dict) -> dict:
    """Sends a confirmed draft. A repeated request returns the deal it already made."""
    db = get_db()
    if d["status"] == "sent":
        return {**draft_view(d), "duplicate": True}
    # Claim the draft so two sends at once can't both make an offer.
    res = db.offer_drafts.update_one({"_id": d["_id"], "status": "draft"}, {"$set": {"status": "sending"}})
    if not res.modified_count:
        fresh = db.offer_drafts.find_one({"_id": d["_id"]})
        if fresh and fresh["status"] == "sent":
            return {**draft_view(fresh), "duplicate": True}
        raise HTTPException(409, "This draft is being sent already.")
    try:
        brand = db.brands.find_one({"_id": d["brand_id"]})
        creator = db.creators.find_one({"_id": d["creator_id"]})
        listing = db.listings.find_one({"_id": d["listing_id"]})
        if not (brand and creator and listing):
            raise HTTPException(404, "The campaign or creator is no longer available.")
        made = create_offer(brand, creator, listing, d["amount"], d.get("message"))
    except Exception:
        db.offer_drafts.update_one({"_id": d["_id"]}, {"$set": {"status": "draft"}})
        raise
    db.offer_drafts.update_one({"_id": d["_id"]}, {"$set": {"status": "sent", "deal_id": made["id"], "sent_at": now_iso(), "updated_at": now_iso()}})
    au.audit("offer_draft_sent", user["_id"], user.get("role"), draft_id=d["_id"], deal_id=made["id"])
    return {**draft_view(db.offer_drafts.find_one({"_id": d["_id"]})), "duplicate": False, "fair": made["fair"], "below_pct": made["below_pct"]}


def discard_draft(d: dict, user: dict) -> None:
    if d["status"] != "draft":
        raise HTTPException(409, "This draft was already sent.")
    get_db().offer_drafts.delete_one({"_id": d["_id"], "status": "draft"})
    au.audit("offer_draft_discarded", user["_id"], user.get("role"), draft_id=d["_id"])
