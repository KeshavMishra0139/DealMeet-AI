"""Creator collectives: booking with per-member terms, confirmations, activation and
replacement.

The brand sees each member's deliverables, price and share of the budget and can adjust
them before sending. Every member confirms their own terms (accepting their deal); the
collective is active, and can be funded, only when all members have confirmed. A member
who declines can be replaced before funding. Each member's deliverables and payment
status are tracked on their own deal; members never see each other's terms.
"""
from __future__ import annotations

import uuid

from fastapi import HTTPException

from ..config import now_iso
from ..db import get_db
from ..engines import collective as builder
from ..engines.fair_price import deliverables_label
from . import auth as au
from . import consent as cs
from . import contracts

KINDS = {"reel", "story", "short", "carousel", "live", "link_in_bio"}
CONFIRMED = ("contract", "escrow_funded", "live", "verified", "paid")


def _clean_deliverables(ds: list[dict] | None, default: list[dict]) -> list[dict]:
    if ds is None:
        return default
    out = [{"kind": x["kind"], "count": int(x["count"])} for x in ds if int(x.get("count") or 0) > 0]
    if not out or any(x["kind"] not in KINDS or x["count"] > 20 for x in out):
        raise HTTPException(422, "Each member needs at least one deliverable (up to 20 of each).")
    return out


def _member_deal(x: dict, brand: dict, creator_id: str, price: int, deliverables: list[dict], cid: str, size: int, user_id: str | None) -> dict:
    at = now_iso()
    d = {
        "_id": f"dl_{uuid.uuid4().hex[:10]}",
        "kind": "collective",
        "collective_id": cid,
        "listing_id": x["_id"],
        "brand_id": brand["_id"],
        "creator_id": creator_id,
        "amount": price,
        "fair_at_offer": price,
        "deliverables": deliverables,
        "usage_rights_days": x.get("usage_rights_days") or 0,
        "exclusivity_days": x.get("exclusivity_days") or 0,
        "post_by": x.get("deadline"),
        "stage": "offer",
        "message": f"You're invited to a {size}-creator collective for {brand['name']}. Confirm your own terms; the pack starts once everyone has.",
        "timeline": [{"stage": "offer", "at": at, "note": f"Collective offer from {brand['name']}"}],
        "created_at": at,
    }
    contracts.start(d, user_id)
    return d


def book(x: dict, brand: dict, member_ids: list[str], adjust: dict[str, dict], combined_reach: int | None, user: dict) -> dict:
    """Book the chosen members, each with their own (possibly adjusted) price and deliverables."""
    from . import campaigns as camp

    camp.require_live(x, "taking bookings")
    db = get_db()
    pack = builder.build(x, brand, must_include=member_ids, size_max=len(member_ids))
    members = [m for m in pack["members"] if m["id"] in member_ids]
    if len(members) < 2:
        raise HTTPException(422, "A collective needs at least 2 creators who fit this campaign.")
    default = x.get("deliverables") or [{"kind": "reel", "count": 1}]
    rows = []
    for m in members:
        a = adjust.get(m["id"]) or {}
        price = int(a.get("price") or m["price"])
        if not 500 <= price <= 10_000_000:
            raise HTTPException(422, f"{m['name']}'s fee must be between ₹500 and ₹1,00,00,000.")
        rows.append({"creator_id": m["id"], "price": price, "fair": m["price"], "deliverables": _clean_deliverables(a.get("deliverables"), default)})
    total = sum(r["price"] for r in rows)
    visible = all(m["effective_reach"] is not None for m in members)
    raw = sum(m["reach"] for m in members) if visible else 0
    cid = f"co_{uuid.uuid4().hex[:8]}"
    db.collectives.insert_one(
        {
            "_id": cid,
            "listing_id": x["_id"],
            "brand_id": brand["_id"],
            "members": [{**r, "split": round(r["price"] / total, 4), "required": True} for r in rows],
            "total": total,
            "combined_reach": min(combined_reach or raw, raw) if visible else None,
            "status": "awaiting_confirmations",
            "history": [{"at": now_iso(), "event": "sent", "by": user["_id"]}],
            "created_at": now_iso(),
        }
    )
    for r in rows:
        deal = _member_deal(x, brand, r["creator_id"], r["price"], r["deliverables"], cid, len(rows), user["_id"])
        camp.mark_offered(x["_id"], r["creator_id"], deal["_id"])
        db.deals.insert_one(deal)
    au.audit("collective_booked", user["_id"], "brand", collective_id=cid, members=len(rows), total=total)
    return {"id": cid, "members": len(rows), "total": total}


def confirmations(col: dict) -> dict:
    deals = {d["creator_id"]: d for d in get_db().deals.find({"collective_id": col["_id"]})}
    confirmed = [m["creator_id"] for m in col["members"] if deals.get(m["creator_id"], {}).get("stage") in CONFIRMED]
    declined = [m["creator_id"] for m in col["members"] if deals.get(m["creator_id"], {}).get("stage") == "declined"]
    waiting = [m["creator_id"] for m in col["members"] if m["creator_id"] not in confirmed and m["creator_id"] not in declined]
    required = [m["creator_id"] for m in col["members"] if m.get("required", True)]
    if col.get("funded"):
        status = "completed" if all(deals.get(c, {}).get("stage") in ("verified", "paid") for c in confirmed) and confirmed else "funded"
    elif any(c in declined for c in required):
        status = "needs_replacement"
    elif all(c in confirmed for c in required):
        status = "active"
    else:
        status = "awaiting_confirmations"
    return {"status": status, "confirmed": len(confirmed), "declined": declined, "waiting": len(waiting), "required": len(required)}


def require_active(col: dict) -> None:
    c = confirmations(col)
    if c["status"] == "needs_replacement":
        raise HTTPException(409, "A member declined. Replace them before funding the collective.")
    if c["status"] != "active":
        raise HTTPException(409, f"Waiting for {c['waiting']} of {c['required']} members to confirm their terms. The collective starts once everyone has.")


def candidates(col: dict, brand: dict, n: int = 8) -> list[dict]:
    """Creators who could take a declined member's place, best first."""
    x = get_db().listings.find_one({"_id": col["listing_id"]})
    current = {m["creator_id"] for m in col["members"]}
    # Every eligible creator, not just the campaign's target pack size.
    pack = builder.build({**x, "collective_size": None}, brand, budget=10_000_000, size_max=len(current) + n)
    return [{k: m[k] for k in ("id", "name", "handle", "avatar_hue", "is_reference", "price", "fit", "why")} for m in pack["members"] if m["id"] not in current][:n]


def replace(col: dict, brand: dict, out_id: str, in_id: str, price: int | None, user: dict) -> dict:
    db = get_db()
    if col.get("funded"):
        raise HTTPException(409, "The collective is funded; its members can't change now.")
    out = db.deals.find_one({"collective_id": col["_id"], "creator_id": out_id})
    if not out or out["stage"] != "declined":
        raise HTTPException(409, "Only a member who declined can be replaced.")
    if any(m["creator_id"] == in_id for m in col["members"]):
        raise HTTPException(409, "That creator is already in the collective.")
    c = db.creators.find_one({"_id": in_id})
    if not c or cs.scopes_for(c, brand["_id"]) is None:
        raise HTTPException(404, "Creator not available")
    pick = next((m for m in candidates(col, brand, n=50) if m["id"] == in_id), None)
    if not pick:
        raise HTTPException(422, "That creator doesn't fit this campaign's requirements.")
    fee = int(price or pick["price"])
    if not 500 <= fee <= 10_000_000:
        raise HTTPException(422, "The fee must be between ₹500 and ₹1,00,00,000.")
    x = db.listings.find_one({"_id": col["listing_id"]})
    old = next(m for m in col["members"] if m["creator_id"] == out_id)
    members = [m for m in col["members"] if m["creator_id"] != out_id] + [{"creator_id": in_id, "price": fee, "fair": pick["price"], "deliverables": old["deliverables"], "required": True}]
    total = sum(m["price"] for m in members)
    for m in members:
        m["split"] = round(m["price"] / total, 4)
    deal = _member_deal(x, brand, in_id, fee, old["deliverables"], col["_id"], len(members), user["_id"])
    db.deals.insert_one(deal)
    db.deals.update_one({"_id": out["_id"]}, {"$set": {"replaced_by": in_id}})
    db.collectives.update_one({"_id": col["_id"]}, {"$set": {"members": members, "total": total, "combined_reach": None},
                                                    "$push": {"history": {"at": now_iso(), "event": "replaced", "out": out_id, "in": in_id, "by": user["_id"]}}})
    au.audit("collective_member_replaced", user["_id"], "brand", collective_id=col["_id"], out=out_id, into=in_id)
    return db.collectives.find_one({"_id": col["_id"]})


def payment_status(d: dict, col: dict) -> str:
    """Honest per-member payment status."""
    if d.get("stage") in ("offer", "contract", "declined"):
        return "Not funded yet" if not col.get("funded") else "Funded; waiting for this member"
    payout = (d.get("payout") or {}).get("status")
    if payout == "simulated":
        return "Paid out (simulated, no money moved)"
    if payout == "not_connected":
        return "Approved; payout not connected"
    mode = (col.get("escrow") or {}).get("mode")
    return "In escrow (simulated)" if mode == "simulated" else "In escrow (Razorpay test mode)"


def member_terms(m: dict) -> dict:
    return {"price": m["price"], "split": m["split"], "deliverables": m.get("deliverables"), "deliverables_label": deliverables_label({"deliverables": m.get("deliverables")})}
