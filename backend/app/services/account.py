"""Deleting an account: the user, their creator profile or brand, and everything that is
only theirs. Refused while a deal has work or money in flight, so nobody is left stuck.

Kept: deals that were paid (the other side's records; deal screens cope with a missing
profile), reports (for moderation) and one audit entry with the account id and role only.
"""
from __future__ import annotations

from fastapi import HTTPException

from ..db import COLLECTIONS, get_db
from . import auth as au

# Work or money in flight: the other side still needs this account.
IN_FLIGHT = ("contract", "escrow_funded", "live", "verified")
# Never removed with an account: shared cache, moderation and money records, the consent
# trail, pitches already in a brand's inbox, and deals handled below.
KEEP = {"ai_cache", "reports", "deals", "creators", "brands", "invoices", "consent_audit", "pitches"}


def _blocked(field: str, value: str) -> None:
    if get_db().deals.count_documents({field: value, "stage": {"$in": list(IN_FLIGHT)}}):
        raise HTTPException(409, "You have deals in progress. Finish or cancel them first, so nobody's work or money is stuck.")


def delete_account(user: dict) -> dict:
    if user.get("role") == "admin":
        raise HTTPException(403, "Admin accounts are removed on the server.")
    if user.get("seeded"):
        raise HTTPException(409, "Demo profiles can't be deleted. They reset to sample data.")
    db = get_db()
    removed: dict[str, int] = {}

    def drop(name: str, q: dict) -> None:
        n = db[name].delete_many(q).deleted_count
        if n:
            removed[name] = removed.get(name, 0) + n

    cid, bid = user.get("creator_id"), user.get("brand_id")
    if cid:
        _blocked("creator_id", cid)
    if bid:
        _blocked("brand_id", bid)
    if cid:
        for name in COLLECTIONS:
            if name not in KEEP:
                drop(name, {"creator_id": cid})
        drop("notifications", {"to": cid})
        # A collective's seat is declined rather than deleted, so the collective's split still adds up.
        db.deals.update_many({"creator_id": cid, "kind": "collective", "stage": "offer"}, {"$set": {"stage": "declined"}})
        drop("deals", {"creator_id": cid, "kind": {"$ne": "collective"}, "stage": {"$in": ["offer", "declined"]}})  # never started
        drop("creators", {"_id": cid})
    if bid:
        listings = [x["_id"] for x in db.listings.find({"owner_id": bid}, {"_id": 1})]
        for name in COLLECTIONS:
            if name not in KEEP:
                drop(name, {"brand_id": bid})
        drop("listings", {"owner_id": bid})
        drop("applications", {"$or": [{"lister_id": bid}, {"listing_id": {"$in": listings}}]})
        drop("notifications", {"to": bid})
        drop("deals", {"brand_id": bid, "stage": {"$in": ["offer", "declined"]}})
        drop("brands", {"_id": bid})
    drop("connections", {"user_id": user["_id"]})
    drop("oauth_states", {"user_id": user["_id"]})
    drop("notifications", {"to": user["_id"]})
    if user.get("email"):
        db.login_failures.delete_many({"email": user["email"]})
        db.login_codes.delete_many({"email": user["email"]})
    db.sessions.delete_many({"user_id": user["_id"]})
    db.users.delete_one({"_id": user["_id"]})
    au.audit("account_deleted", user["_id"], user.get("role"))
    return {"deleted": True, "removed": removed}
