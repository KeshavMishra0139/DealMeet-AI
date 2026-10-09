"""Trust-first deal rail.

Offer -> Contract (e-sign) -> Escrow funded -> Post live -> Verified -> Paid by UPI

Money only moves through escrow. Brands fund before the post goes live; the
creator is paid automatically once the post is verified (brand confirmation
plus a mock official-API check), or automatically after a grace period if the
brand doesn't respond. Collective deals share one escrow payment and pay each
member their split.
"""
from __future__ import annotations

import random
import re
import uuid
from datetime import date, timedelta

from fastapi import HTTPException

from ..config import get_settings, now_iso, today
from ..db import get_db
from ..engines.common import day_month, inr, inr_full
from ..engines.fair_price import deliverables_label, fair_price

RAIL = [
    ("offer", "Offer"),
    ("contract", "Contract signed"),
    ("escrow_funded", "Escrow funded"),
    ("live", "Post live"),
    ("verified", "Verified"),
    ("paid", "Paid by UPI"),
]
ORDER = {k: i for i, (k, _) in enumerate(RAIL)}
VERIFY_DAYS = 3  # brand has this long to confirm a live post
GRACE_DAYS = 3  # then escrow auto-releases to the creator
POST_URL = re.compile(r"^https://(www\.)?(instagram\.com/(reel|p)/|youtube\.com/shorts/|youtu\.be/)[\w\-]+/?(\?.*)?$")


def _get(deal_id: str) -> dict:
    d = get_db().deals.find_one({"_id": deal_id})
    if not d:
        raise HTTPException(404, "Deal not found")
    return d


def _save(d: dict) -> None:
    get_db().deals.replace_one({"_id": d["_id"]}, d)


def _event(d: dict, stage: str, note: str) -> None:
    d.setdefault("timeline", []).append({"stage": stage, "at": now_iso(), "note": note})


def _names(d: dict) -> tuple[dict, dict]:
    db = get_db()
    return db.creators.find_one({"_id": d["creator_id"]}) or {}, db.brands.find_one({"_id": d["brand_id"]}) or {}


def invoice_number(creator: dict, seq: int) -> str:
    return f"JD-{re.sub(r'[^A-Za-z0-9]', '', creator.get('handle', 'creator'))[:8].upper()}-{seq:04d}"


def upi_for(creator: dict) -> str:
    return f"{re.sub(r'[^a-z0-9]', '', creator.get('handle', 'creator'))}@upi-demo"


def _ensure_contract(d: dict) -> None:
    if not d.get("contract"):
        d["contract"] = {"signed_by_creator": None, "signed_by_brand": None, "created_at": now_iso()}


def _maybe_fund_from_collective(d: dict) -> None:
    if d.get("kind") != "collective":
        return
    col = get_db().collectives.find_one({"_id": d.get("collective_id")})
    c = d.get("contract") or {}
    if col and col.get("funded") and c.get("signed_by_creator") and c.get("signed_by_brand") and d["stage"] == "contract":
        d["stage"] = "escrow_funded"
        d["escrow"] = {"mode": col["escrow"]["mode"], "ref": col["escrow"]["ref"], "funded_at": col["escrow"]["funded_at"], "collective": True}
        _event(d, "escrow_funded", "Covered by the collective's escrow payment")


def _invoice_for(d: dict, status: str) -> dict:
    db = get_db()
    inv = db.invoices.find_one({"deal_id": d["_id"]})
    creator, brand = _names(d)
    if inv is None:
        seq = db.invoices.count_documents({"creator_id": d["creator_id"]}) + 1
        inv = {
            "_id": f"inv_{uuid.uuid4().hex[:8]}",
            "number": invoice_number(creator, seq),
            "creator_id": d["creator_id"],
            "deal_id": d["_id"],
            "to": brand.get("name", "Brand"),
            "amount": d["amount"],
            "description": deliverables_label(d),
            "issued": today().isoformat(),
            "due": (today() + timedelta(days=VERIFY_DAYS + GRACE_DAYS)).isoformat(),
            "status": status,
            "off_platform": False,
            "reminders": [],
        }
        db.invoices.insert_one(inv)
    else:
        db.invoices.update_one({"_id": inv["_id"]}, {"$set": {"status": status, "amount": d["amount"]}})
        inv["status"] = status
    return inv


def _payout(d: dict) -> None:
    creator, brand = _names(d)
    utr = f"SIM{today().strftime('%y%m%d')}{random.randint(100000, 999999)}"
    d.setdefault("payouts", []).append({"creator_id": d["creator_id"], "amount": d["amount"], "upi": upi_for(creator), "utr": utr, "at": now_iso()})
    d["stage"] = "paid"
    _event(d, "paid", f"{inr(d['amount'])} paid by UPI to {upi_for(creator)} (UTR {utr})")
    _invoice_for(d, "paid")
    if d.get("kind") == "collective":
        col = get_db().collectives.find_one({"_id": d["collective_id"]})
        if col:
            get_db().collectives.update_one({"_id": col["_id"]}, {"$inc": {"paid_out": d["amount"]}})


def mock_insights_check(d: dict) -> dict:
    """Stands in for reading the post's insights through the official API."""
    creator, brand = _names(d)
    from ..engines import metrics

    views = int(metrics.median_views(creator) * random.Random(d["_id"]).uniform(0.55, 0.9)) if creator else 0
    return {
        "source": "Official API (demo sandbox)",
        "checked_at": now_iso(),
        "post_found": True,
        "views_so_far": views,
        "checks": [
            {"label": "Post is public and live", "ok": True},
            {"label": "Posted after the contract was signed", "ok": True},
            {"label": f"Mentions @{(brand.get('name') or 'brand').lower().replace(' ', '').replace('.', '')}", "ok": True},
            {"label": "Paid-partnership label added", "ok": True},
        ],
    }


def auto_release_due(d: dict) -> date | None:
    if d["stage"] != "live" or not d.get("verify_due"):
        return None
    return date.fromisoformat(d["verify_due"]) + timedelta(days=GRACE_DAYS)


def sweep(d: dict) -> dict:
    """Background rule, applied whenever a deal is read: release escrow if the
    brand hasn't confirmed a live post within the grace period."""
    due = auto_release_due(d)
    if due and today() >= due:
        d["verification"] = {**mock_insights_check(d), "auto": True}
        d["stage"] = "verified"
        _event(d, "verified", "Auto-verified: the brand didn't respond in time")
        _payout(d)
        _save(d)
    return d


def act(deal_id: str, role: str, action: str, payload: dict) -> dict:
    d = sweep(_get(deal_id))
    creator, brand = _names(d)
    stage = d["stage"]

    def need(cond: bool, msg: str = "That isn't possible at this stage") -> None:
        if not cond:
            raise HTTPException(409, msg)

    if role == "creator" and action == "accept":
        need(stage == "offer" and not d.get("counter"))
        _ensure_contract(d)
        d["contract"]["signed_by_creator"] = now_iso()
        d["contract"]["creator_signature"] = payload.get("name") or creator.get("name")
        if d.get("kind") == "collective":
            d["contract"]["signed_by_brand"] = d["contract"].get("signed_by_brand") or d.get("created_at")
        d["stage"] = "contract"
        _event(d, "contract", f"{creator.get('name')} accepted and e-signed the contract")
        _invoice_for(d, "pending")
        _maybe_fund_from_collective(d)
    elif role == "creator" and action == "counter":
        need(stage == "offer" and d.get("kind") != "collective", "Collective splits are fixed; accept or decline")
        amount = int(payload.get("amount") or 0)
        need(amount >= 500, "Enter a counter amount")
        d["counter"] = {"amount": amount, "by": "creator", "at": now_iso(), "note": payload.get("note")}
        _event(d, "offer", f"{creator.get('name')} countered at {inr(amount)}")
    elif role == "creator" and action == "decline":
        need(stage == "offer")
        d["stage"] = "declined"
        _event(d, "declined", f"{creator.get('name')} declined")
    elif role == "brand" and action == "accept_counter":
        need(stage == "offer" and d.get("counter"))
        d["amount"] = d["counter"]["amount"]
        _ensure_contract(d)
        d["contract"].update({"signed_by_creator": d["counter"]["at"], "signed_by_brand": now_iso(), "brand_signature": payload.get("name") or brand.get("name"), "creator_signature": creator.get("name")})
        d["counter"]["accepted_at"] = now_iso()
        d["stage"] = "contract"
        _event(d, "contract", f"{brand.get('name')} accepted the counter at {inr(d['amount'])}; contract signed by both")
        _invoice_for(d, "pending")
    elif role == "brand" and action == "decline_counter":
        need(stage == "offer" and d.get("counter"))
        d["counter"]["declined_at"] = now_iso()
        d["stage"] = "declined"
        _event(d, "declined", f"{brand.get('name')} declined the counter")
    elif role == "brand" and action == "withdraw":
        need(stage in ("offer", "contract") and not d.get("escrow"))
        d["stage"] = "declined"
        _event(d, "declined", f"{brand.get('name')} withdrew the offer")
    elif action == "sign":
        need(stage == "contract")
        _ensure_contract(d)
        key = "signed_by_creator" if role == "creator" else "signed_by_brand"
        need(not d["contract"].get(key), "Already signed")
        d["contract"][key] = now_iso()
        d["contract"][f"{role}_signature"] = payload.get("name") or (creator if role == "creator" else brand).get("name")
        _event(d, "contract", f"{(creator if role == 'creator' else brand).get('name')} e-signed the contract")
        _maybe_fund_from_collective(d)
    elif role == "brand" and action == "fund":
        c = d.get("contract") or {}
        need(stage == "contract" and c.get("signed_by_creator") and c.get("signed_by_brand"), "Both sides sign before escrow is funded")
        need(d.get("kind") != "collective", "Fund the collective once from its page")
        ref = payload.get("payment_ref") or f"esc_sim_{uuid.uuid4().hex[:4].upper()}"
        d["escrow"] = {"mode": payload.get("mode", "simulated"), "ref": ref, "funded_at": now_iso(), "amount": d["amount"]}
        d["stage"] = "escrow_funded"
        _event(d, "escrow_funded", f"{inr(d['amount'])} held in escrow ({'Razorpay test' if payload.get('mode') == 'razorpay-test' else 'simulated'} payment {ref})")
    elif role == "creator" and action == "submit_post":
        need(stage == "escrow_funded", "Wait until escrow is funded before posting")
        url = (payload.get("url") or "").strip()
        need(bool(POST_URL.match(url)), "Paste the link to your Instagram reel or YouTube Short")
        d["proof_url"] = url
        d["stage"] = "live"
        d["verify_due"] = (today() + timedelta(days=VERIFY_DAYS)).isoformat()
        _event(d, "live", "Post link submitted")
    elif role == "brand" and action == "confirm":
        need(stage == "live")
        d["verification"] = mock_insights_check(d)
        d["stage"] = "verified"
        _event(d, "verified", f"{brand.get('name')} confirmed; official-API check passed")
        _payout(d)
    elif role == "creator" and action == "nudge":
        need(stage == "live")
        _event(d, "live", f"{creator.get('name')} sent a reminder to confirm")
    else:
        raise HTTPException(400, "Unknown action")
    _save(d)
    return view(d, role)


def actions_for(d: dict, role: str) -> list[dict]:
    s = d["stage"]
    c = d.get("contract") or {}
    out: list[dict] = []
    if role == "creator":
        if s == "offer" and not d.get("counter"):
            out = [{"id": "accept", "label": f"Accept {inr(d['amount'])} and sign", "kind": "primary"}]
            if d.get("kind") != "collective":  # a collective's split is fixed and already priced on reach
                out.append({"id": "counter", "label": "Counter", "kind": "secondary", "needs": "amount"})
            out.append({"id": "decline", "label": "Decline", "kind": "ghost"})
        elif s == "contract" and not c.get("signed_by_creator"):
            out = [{"id": "sign", "label": "E-sign contract", "kind": "primary"}]
        elif s == "escrow_funded":
            out = [{"id": "submit_post", "label": "Submit post link", "kind": "primary", "needs": "url"}]
        elif s == "live":
            out = [{"id": "nudge", "label": "Remind the brand", "kind": "secondary"}]
    else:
        if s == "offer" and d.get("counter") and not d["counter"].get("declined_at"):
            out = [
                {"id": "accept_counter", "label": f"Accept {inr(d['counter']['amount'])} and sign", "kind": "primary"},
                {"id": "decline_counter", "label": "Decline", "kind": "ghost"},
            ]
        elif s == "offer":
            out = [{"id": "withdraw", "label": "Withdraw offer", "kind": "ghost"}]
        elif s == "contract" and not c.get("signed_by_brand"):
            out = [{"id": "sign", "label": "E-sign contract", "kind": "primary"}]
        elif s == "contract" and c.get("signed_by_creator") and d.get("kind") != "collective":
            out = [{"id": "fund", "label": f"Fund escrow {inr(d['amount'])}", "kind": "primary", "needs": "payment"}]
        elif s == "live":
            out = [{"id": "confirm", "label": "Confirm post and release payment", "kind": "primary"}]
    return out


def view(d: dict, role: str) -> dict:
    d = sweep(d)
    db = get_db()
    creator, brand = _names(d)
    listing = db.listings.find_one({"_id": d.get("listing_id")}) if d.get("listing_id") else None
    reached = ORDER.get(d["stage"], -1)
    times = {}
    for e in d.get("timeline") or []:
        times.setdefault(e["stage"], e["at"])
    steps = []
    for i, (key, label) in enumerate(RAIL):
        status = "done" if i < reached or d["stage"] == "paid" else "current" if i == reached else "upcoming"
        if d["stage"] == "declined":
            status = "done" if key == "offer" else "upcoming"
        steps.append({"key": key, "label": label, "status": status, "at": times.get(key)})
    terms = {"deliverables": d.get("deliverables"), "usage_rights_days": d.get("usage_rights_days"), "exclusivity_days": d.get("exclusivity_days")}
    fair_total = d.get("fair_at_offer")
    if not fair_total and creator:
        fair_total = fair_price(creator, brand or None, terms, with_model=False)["total"]
    alerts = []
    if d["stage"] == "offer" and fair_total and d["amount"] < 0.7 * fair_total:
        alerts.append({"kind": "low_offer", "text": f"This offer is {round((1 - d['amount'] / fair_total) * 100)}% below the fair price", "fair": fair_total})
    due = auto_release_due(d)
    if due:
        days_left = (due - today()).days
        late = d.get("verify_due") and today() > date.fromisoformat(d["verify_due"])
        alerts.append(
            {
                "kind": "verify_late" if late else "verify_window",
                "text": (f"{brand.get('name', 'The brand')} is {(today() - date.fromisoformat(d['verify_due'])).days} days late confirming" if late else f"{brand.get('name', 'The brand')} has until {day_month(d['verify_due'])} to confirm"),
                "detail": f"Escrow auto-releases to the creator in {days_left} day{'s' if days_left != 1 else ''} if there's no response.",
            }
        )
    invoice = db.invoices.find_one({"deal_id": d["_id"]})
    collective = None
    if d.get("kind") == "collective":
        col = db.collectives.find_one({"_id": d.get("collective_id")})
        if col:
            member = next((m for m in col["members"] if m["creator_id"] == d["creator_id"]), None)
            collective = {"id": col["_id"], "size": len(col["members"]), "total": col["total"], "funded": bool(col.get("funded")), "split": member["split"] if member else None}
    return {
        "id": d["_id"],
        "kind": d.get("kind", "single"),
        "stage": d["stage"],
        "amount": d["amount"],
        "fair_total": fair_total,
        "deliverables": deliverables_label(terms),
        "usage_rights_days": d.get("usage_rights_days") or 0,
        "exclusivity_days": d.get("exclusivity_days") or 0,
        "message": d.get("message"),
        "creator": {"id": creator.get("_id"), "name": creator.get("name"), "handle": creator.get("handle"), "avatar_hue": creator.get("avatar_hue", 260), "is_reference": creator.get("is_reference", False), "upi": upi_for(creator) if creator else None},
        "brand": {"id": brand.get("_id"), "name": brand.get("name", "Brand"), "hue": brand.get("hue", 260), "verified": brand.get("verified", True)},
        "listing": {"id": listing["_id"], "title": listing["title"]} if listing else None,
        "steps": steps,
        "timeline": list(reversed(d.get("timeline") or [])),
        "counter": d.get("counter"),
        "contract": {**(d.get("contract") or {}), "terms": contract_terms(d, creator, brand)} if d.get("contract") or d["stage"] == "offer" else None,
        "escrow": d.get("escrow"),
        "proof_url": d.get("proof_url"),
        "verify_due": d.get("verify_due"),
        "auto_release_on": due.isoformat() if due else None,
        "verification": d.get("verification"),
        "payouts": d.get("payouts") or [],
        "invoice": {"id": invoice["_id"], "number": invoice["number"], "status": invoice["status"]} if invoice else None,
        "alerts": alerts,
        "collective": collective,
        "actions": actions_for(d, role),
        "payments_mode": "razorpay-test" if get_settings().has_razorpay else "simulated",
    }


def contract_terms(d: dict, creator: dict, brand: dict) -> list[str]:
    terms = {"deliverables": d.get("deliverables")}
    brand_name = (brand.get("name") or "the brand").rstrip(".")
    t = [
        f"{creator.get('name', 'The creator')} will publish {deliverables_label(terms)} for {brand_name}.",
        f"Fee: {inr_full(d['amount'])}, held in escrow by JodiDar before the post goes live.",
        f"Payment is released by UPI once the post is verified, or automatically {VERIFY_DAYS + GRACE_DAYS} days after it goes live if the brand doesn't respond.",
        "The post carries a paid-partnership label and stays up for at least 30 days.",
    ]
    if d.get("usage_rights_days"):
        t.append(f"The brand may use the post in paid ads for {d['usage_rights_days']} days.")
    if d.get("exclusivity_days"):
        t.append(f"No competing brand in the same category for {d['exclusivity_days']} days.")
    t.append("Either side may cancel before escrow is funded at no cost. After funding, cancellation follows JodiDar's refund policy.")
    return t


def list_for(role: str, owner_id: str) -> list[dict]:
    q = {"creator_id": owner_id} if role == "creator" else {"brand_id": owner_id}
    rows = []
    for d in get_db().deals.find(q):
        v = view(d, role)
        rows.append(
            {
                "id": v["id"],
                "kind": v["kind"],
                "stage": v["stage"],
                "amount": v["amount"],
                "fair_total": v["fair_total"],
                "deliverables": v["deliverables"],
                "creator": v["creator"],
                "brand": v["brand"],
                "listing": v["listing"],
                "alerts": v["alerts"],
                "actions": [a["id"] for a in v["actions"]],
                "updated": (v["timeline"][0]["at"] if v["timeline"] else None),
                "collective": v["collective"],
                "counter": v["counter"],
            }
        )
    rows.sort(key=lambda r: r["updated"] or "", reverse=True)
    return rows


def fund_collective(collective_id: str, mode: str = "simulated", ref: str | None = None) -> dict:
    db = get_db()
    col = db.collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    if col.get("funded"):
        raise HTTPException(409, "Already funded")
    escrow = {"mode": mode, "ref": ref or f"esc_sim_{uuid.uuid4().hex[:4].upper()}", "funded_at": now_iso(), "amount": col["total"]}
    db.collectives.update_one({"_id": collective_id}, {"$set": {"funded": True, "escrow": escrow, "status": "funded"}})
    for d in db.deals.find({"collective_id": collective_id}):
        _maybe_fund_from_collective(d)
        _save(d)
    return collective_view(collective_id)


def collective_view(collective_id: str) -> dict:
    db = get_db()
    col = db.collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    brand = db.brands.find_one({"_id": col["brand_id"]}) or {}
    listing = db.listings.find_one({"_id": col["listing_id"]}) or {}
    deals = {d["creator_id"]: sweep(d) for d in db.deals.find({"collective_id": collective_id})}
    creators = {c["_id"]: c for c in db.creators.find({"_id": {"$in": [m["creator_id"] for m in col["members"]]}}, {"name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1})}
    members = []
    for m in col["members"]:
        d = deals.get(m["creator_id"]) or {}
        c = creators.get(m["creator_id"], {})
        members.append(
            {
                "creator_id": m["creator_id"],
                "name": c.get("name"),
                "handle": c.get("handle"),
                "avatar_hue": c.get("avatar_hue", 260),
                "is_reference": c.get("is_reference", False),
                "price": m["price"],
                "split": m["split"],
                "deal_id": d.get("_id"),
                "stage": d.get("stage"),
                "proof_url": d.get("proof_url"),
                "paid": d.get("stage") == "paid",
            }
        )
    stages: dict[str, int] = {}
    for m in members:
        stages[m["stage"] or "offer"] = stages.get(m["stage"] or "offer", 0) + 1
    return {
        "id": col["_id"],
        "brand": {"id": brand.get("_id"), "name": brand.get("name")},
        "listing": {"id": listing.get("_id"), "title": listing.get("title")},
        "total": col["total"],
        "combined_reach": col.get("combined_reach"),
        "funded": bool(col.get("funded")),
        "escrow": col.get("escrow"),
        "paid_out": sum(m["price"] for m in members if m["paid"]),
        # The whole pack is held in escrow; a member who declines has their share returned to the brand.
        "refunded": sum(m["price"] for m in members if m["stage"] == "declined") if col.get("funded") else 0,
        "members": members,
        "stages": stages,
        "created_at": col.get("created_at"),
        "payments_mode": "razorpay-test" if get_settings().has_razorpay else "simulated",
    }
