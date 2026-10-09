"""Brand Console API."""
from __future__ import annotations

import uuid
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import now_iso, today
from ..db import get_db, out
from ..engines import brand_matching, brand_safety, collective, metrics
from ..engines.common import inr
from ..engines.fair_price import fair_price
from ..engines.matching import listing_fit
from ..engines.trust import trust_score
from ..seed.catalog import CITIES, LANGS, NICHES
from ..services import cache
from ..services import consent as cs
from ..services.deals import auto_release_due
from ..services.views import audience_stage

router = APIRouter(prefix="/api", tags=["brands"])

STAGES = ["offer", "contract", "escrow_funded", "live", "verified", "paid"]
STAGE_LABELS = {
    "offer": "Offer sent",
    "contract": "Contract",
    "escrow_funded": "Escrow funded",
    "live": "Post live",
    "verified": "Verified",
    "paid": "Paid",
    "declined": "Declined",
}


def _brand(brand_id: str) -> dict:
    b = get_db().brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


def _listing(listing_id: str) -> dict:
    x = get_db().listings.find_one({"_id": listing_id})
    if not x:
        raise HTTPException(404, "Campaign not found")
    return x


def _campaign_row(x: dict, brand: dict, deals: list[dict]) -> dict:
    db = get_db()
    mine = [d for d in deals if d.get("listing_id") == x["_id"]]
    fits = 0
    for c in db.creators.find({"_id": {"$regex": "^cr_"}, "discoverable": True}, {"reels": 0}):
        if NICHES[c["niche"]]["family"] in {NICHES[n]["family"] for n in x.get("niches") or []}:
            fits += 1
    b = x.get("budget") or {}
    return {
        "id": x["_id"],
        "title": x["title"],
        "type": x["type"],
        "deal_kind": x.get("deal_kind"),
        "status": x.get("status", "open"),
        "deadline": x.get("deadline"),
        "posted_on": x.get("posted_on"),
        "languages": [LANGS[l]["label"] for l in x.get("languages") or [] if l in LANGS],
        "budget": b,
        "collective_size": x.get("collective_size"),
        "candidates": fits,
        "applications": db.applications.count_documents({"listing_id": x["_id"], "status": {"$in": ["applied", "opted_in"]}}),
        "deals": len(mine),
        "committed": sum(d["amount"] for d in mine if d["stage"] not in ("offer", "declined")),
    }


@router.get("/brands/{brand_id}/console")
def console(brand_id: str):
    db = get_db()
    brand = _brand(brand_id)
    deals = list(db.deals.find({"brand_id": brand_id}))
    creators = {c["_id"]: c for c in db.creators.find({}, {"name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1})}
    campaigns = [_campaign_row(x, brand, deals) for x in db.listings.find({"owner_id": brand_id})]
    stages = {s: {"count": 0, "amount": 0} for s in STAGES}
    for d in deals:
        if d["stage"] in stages:
            stages[d["stage"]]["count"] += 1
            stages[d["stage"]]["amount"] += d["amount"]
    held = [d for d in deals if d["stage"] in ("escrow_funded", "live", "verified")]
    held_total = sum(d["amount"] for d in held)
    paid_total = sum(d["amount"] for d in deals if d["stage"] == "paid")
    needs = []
    for d in deals:
        who = creators.get(d["creator_id"], {}).get("name", "A creator")
        if d["stage"] == "live":
            due = d.get("verify_due")
            late = due and due < today().isoformat()
            release = auto_release_due(d)
            left = (release - today()).days if release else 0
            overdue = f" Overdue; auto-releases in {left} day{'s' if left != 1 else ''}." if late else ""
            needs.append({"deal_id": d["_id"], "kind": "confirm", "text": f"Confirm {who}'s post", "detail": f"{inr(d['amount'])} releases from escrow when you confirm.{overdue}", "urgent": bool(late)})
        elif d["stage"] == "contract" and not (d.get("contract") or {}).get("signed_by_brand"):
            needs.append({"deal_id": d["_id"], "kind": "sign", "text": f"Sign {who}'s contract", "detail": inr(d["amount"]), "urgent": False})
        elif d["stage"] == "contract" and (d.get("contract") or {}).get("signed_by_creator") and d.get("escrow") is None:
            needs.append({"deal_id": d["_id"], "kind": "fund", "text": f"Fund escrow for {who}", "detail": inr(d["amount"]), "urgent": False})
    live_campaigns = [c for c in campaigns if c["status"] == "open"]
    waiting = sum(1 for n in needs if n["kind"] == "confirm")
    headline = f"{len(live_campaigns)} campaign{'s' if len(live_campaigns) != 1 else ''} live. {inr(held_total)} held in escrow."
    if waiting:
        headline += f" {waiting} post{'s' if waiting != 1 else ''} waiting for your confirmation."
    return {
        "brand": out(brand),
        "headline": headline,
        "campaigns": sorted(campaigns, key=lambda c: c["posted_on"] or "", reverse=True),
        "escrow": {
            "held": held_total,
            "count": len(held),
            "items": [
                {"deal_id": d["_id"], "creator": creators.get(d["creator_id"], {}).get("name"), "amount": d["amount"], "stage": d["stage"], "stage_label": STAGE_LABELS[d["stage"]]}
                for d in held
            ],
        },
        "paid_total": paid_total,
        "stages": [{"stage": s, "label": STAGE_LABELS[s], **stages[s]} for s in STAGES],
        "needs_you": needs,
        "recent": [
            {
                "deal_id": d["_id"],
                "creator": creators.get(d["creator_id"], {}).get("name"),
                "creator_id": d["creator_id"],
                "avatar_hue": creators.get(d["creator_id"], {}).get("avatar_hue", 260),
                "is_reference": creators.get(d["creator_id"], {}).get("is_reference", False),
                "amount": d["amount"],
                "stage": d["stage"],
                "stage_label": STAGE_LABELS.get(d["stage"], d["stage"]),
                "kind": d.get("kind", "single"),
                "updated": (d.get("timeline") or [{}])[-1].get("at", d.get("created_at")),
            }
            for d in sorted(deals, key=lambda d: (d.get("timeline") or [{}])[-1].get("at", ""), reverse=True)[:8]
        ],
    }


@router.get("/brands/{brand_id}/campaigns")
def campaigns(brand_id: str):
    brand = _brand(brand_id)
    deals = list(get_db().deals.find({"brand_id": brand_id}))
    return [_campaign_row(x, brand, deals) for x in get_db().listings.find({"owner_id": brand_id})]


class CampaignIn(BaseModel):
    title: str = Field(min_length=4, max_length=90)
    summary: str = Field(min_length=10, max_length=400)
    niches: list[str] = Field(min_length=1)
    languages: list[str] = Field(min_length=1)
    regions: list[str] = ["Pan-India"]
    collective: bool = False
    collective_size: int = Field(default=20, ge=10, le=50)
    budget_min: int | None = Field(default=None, ge=0)
    budget_max: int | None = Field(default=None, ge=0)
    budget_total: int | None = Field(default=None, ge=0)
    reels: int = Field(default=1, ge=1, le=5)
    stories: int = Field(default=0, ge=0, le=10)
    usage_rights_days: int = Field(default=0, ge=0, le=365)
    exclusivity_days: int = Field(default=0, ge=0, le=365)
    min_followers: int = Field(default=0, ge=0)
    deadline: str | None = None


@router.post("/brands/{brand_id}/campaigns")
def create_campaign(brand_id: str, body: CampaignIn):
    _brand(brand_id)
    if any(n not in NICHES for n in body.niches):
        raise HTTPException(422, "Unknown niche")
    lid = f"lst_{brand_id[3:]}_{uuid.uuid4().hex[:6]}"
    deliverables = [{"kind": "reel", "count": body.reels}] + ([{"kind": "story", "count": body.stories}] if body.stories else [])
    budget = {"total": body.budget_total or 100_000} if body.collective else {"per_creator_min": body.budget_min or 5_000, "per_creator_max": body.budget_max or 25_000}
    get_db().listings.insert_one(
        {
            "_id": lid,
            "type": "collective" if body.collective else "brand_campaign",
            "owner_id": brand_id,
            "title": body.title.strip(),
            "summary": body.summary.strip(),
            "niches": body.niches,
            "languages": body.languages,
            "regions": body.regions or ["Pan-India"],
            "deal_kind": "collective" if body.collective else "paid",
            "deliverables": deliverables,
            "usage_rights_days": body.usage_rights_days,
            "exclusivity_days": body.exclusivity_days,
            "min_followers": body.min_followers,
            "max_followers": None,
            "budget": budget,
            "collective_size": body.collective_size if body.collective else None,
            "posted_on": today().isoformat(),
            "deadline": body.deadline,
            "status": "open",
        }
    )
    cache.invalidate("spam")
    return {"id": lid}


@router.get("/listings/{listing_id}")
def listing_detail(listing_id: str):
    x = _listing(listing_id)
    d = out(x)
    owner = get_db().brands.find_one({"_id": x["owner_id"]})
    d["owner"] = {"id": owner["_id"], "name": owner["name"], "hue": owner.get("hue", 260)} if owner else None
    d["language_labels"] = [LANGS[l]["label"] for l in x.get("languages") or [] if l in LANGS]
    d["niche_labels"] = [NICHES[n]["label"] for n in x.get("niches") or [] if n in NICHES]
    return d


@router.get("/listings/{listing_id}/matches")
def listing_matches(listing_id: str):
    x = _listing(listing_id)
    return brand_matching.matches(x, _brand(x["owner_id"]))


class CollectiveIn(BaseModel):
    budget: int | None = Field(default=None, ge=5_000)
    size_min: int = Field(default=10, ge=2, le=50)
    size_max: int = Field(default=50, ge=2, le=50)
    trust_min: int = Field(default=60, ge=0, le=100)
    target_reach: int | None = None


@router.post("/listings/{listing_id}/collective")
def build_collective(listing_id: str, body: CollectiveIn):
    x = _listing(listing_id)
    brand = _brand(x["owner_id"])
    return collective.build(x, brand, body.budget, body.size_min, body.size_max, body.trust_min, body.target_reach)


@router.get("/brands/{brand_id}/creators/{creator_id}")
def creator_for_brand(brand_id: str, creator_id: str, listing_id: str | None = None):
    db = get_db()
    brand = _brand(brand_id)
    c = db.creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    scopes = cs.scopes_for(c, brand_id)
    if scopes is None:
        raise HTTPException(404, "This creator isn't discoverable to you")
    cs.log_view(creator_id, brand_id, scopes)
    listing = db.listings.find_one({"_id": listing_id}) if listing_id else None
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")} if listing else None
    fp = fair_price(c, brand, terms, scopes=scopes)
    fit = listing_fit(c, listing, brand) if listing else None
    stats = None
    if scopes["stats"]:
        recent = metrics.recent(c)
        stats = {
            "followers": c.get("followers"),
            "median_views": round(metrics.median_views(c)),
            "reach_ratio": round(metrics.reach_ratio(c), 1),
            "saves_shares_per_view": round(metrics.ss_rate(c), 4),
            "posts_per_week": round(metrics.posts_per_week(c), 1),
            "recent": [{"date": r["date"], "views": r["views"], "topic": r.get("topic")} for r in recent],
            "provenance": {"views": metrics.prov(c, "reels.0.views"), "saves": metrics.prov(c, "reels.0.saves"), "topic": metrics.prov(c, "reels.0.topic")},
        }
    demographics = None
    if scopes["demographics"]:
        demographics = {**(c.get("audience") or {}), "provenance": metrics.prov(c, "audience")}
    rate_card = None
    if scopes["rate_card"]:
        rate_card = {"typical": c.get("current_rate"), "provenance": metrics.prov(c, "current_rate")}
    reasons = brand_matching.redact((fit or {}).get("reasons", []), scopes)
    return {
        "id": c["_id"],
        "name": c["name"],
        "handle": c["handle"],
        "avatar_hue": c.get("avatar_hue", 260),
        "is_reference": c.get("is_reference", False),
        "reference_note": c.get("reference_note") if c.get("is_reference") else None,
        "bio": c.get("bio"),
        "niche_label": NICHES[c["niche"]]["label"],
        "languages": [LANGS[l]["label"] for l in c.get("languages") or [] if l in LANGS],
        "location": c.get("city") or c.get("region"),
        "audience_stage": audience_stage(c.get("followers", 0))["label"],
        "trust": trust_score(c),
        "safety": brand_safety.public(c),
        "scopes": scopes,
        "scope_source": cs.source_for(creator_id, brand_id),
        "scope_labels": cs.SCOPE_LABELS,
        "fit": {"score": fit["score"], "reasons": reasons, "cautions": brand_matching.redact_cautions(fit["cautions"], scopes)} if fit else None,
        "fair": {
            "range": fp["range"],
            "total": fp["total"],
            "deliverables": fp["deliverables"],
            "steps": fp["steps"] if scopes["stats"] else None,
            "follower_price": fp["follower_price"],
            "model_check": fp.get("model_check"),
        },
        "stats": stats,
        "demographics": demographics,
        "rate_card": rate_card,
        "listing": {"id": listing["_id"], "title": listing["title"]} if listing else None,
        "deal": out(db.deals.find_one({"creator_id": creator_id, "brand_id": brand_id, "listing_id": listing_id})) if listing_id else None,
    }


class AccessIn(BaseModel):
    scopes: list[Literal["stats", "demographics", "rate_card"]]


@router.post("/brands/{brand_id}/creators/{creator_id}/request-access")
def request_access(brand_id: str, creator_id: str, body: AccessIn):
    _brand(brand_id)
    if not get_db().creators.find_one({"_id": creator_id}):
        raise HTTPException(404, "Creator not found")
    cs.request(creator_id, brand_id, list(body.scopes))
    return {"requested": body.scopes}


class OfferIn(BaseModel):
    brand_id: str
    creator_id: str
    listing_id: str | None = None
    amount: int = Field(ge=500, le=10_000_000)
    message: str | None = Field(default=None, max_length=400)


@router.post("/offers")
def send_offer(body: OfferIn):
    db = get_db()
    brand = _brand(body.brand_id)
    c = db.creators.find_one({"_id": body.creator_id})
    if not c or cs.scopes_for(c, body.brand_id) is None:
        raise HTTPException(404, "Creator not available")
    listing = db.listings.find_one({"_id": body.listing_id}) if body.listing_id else None
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")} if listing else {"deliverables": [{"kind": "reel", "count": 1}]}
    fp = fair_price(c, brand, terms, with_model=False)
    did = f"dl_{uuid.uuid4().hex[:10]}"
    at = now_iso()
    db.deals.insert_one(
        {
            "_id": did,
            "kind": "single",
            "listing_id": body.listing_id,
            "brand_id": body.brand_id,
            "creator_id": body.creator_id,
            "amount": body.amount,
            "fair_at_offer": fp["total"],
            "deliverables": terms.get("deliverables"),
            "usage_rights_days": terms.get("usage_rights_days") or 0,
            "exclusivity_days": terms.get("exclusivity_days") or 0,
            "stage": "offer",
            "message": body.message,
            "timeline": [{"stage": "offer", "at": at, "note": f"Offer sent by {brand['name']}"}],
            "created_at": at,
        }
    )
    below = 1 - body.amount / fp["total"] if fp["total"] else 0
    return {"id": did, "fair": fp["total"], "below_pct": round(below * 100)}


class BookIn(BaseModel):
    member_ids: list[str] = Field(min_length=2, max_length=50)


@router.post("/listings/{listing_id}/collective/book")
def book_collective(listing_id: str, body: BookIn):
    db = get_db()
    x = _listing(listing_id)
    brand = _brand(x["owner_id"])
    pack = collective.build(x, brand, must_include=body.member_ids, size_max=len(body.member_ids))
    members = [m for m in pack["members"] if m["id"] in body.member_ids]
    total = sum(m["price"] for m in members)
    cid = f"co_{uuid.uuid4().hex[:8]}"
    at = now_iso()
    db.collectives.insert_one(
        {
            "_id": cid,
            "listing_id": listing_id,
            "brand_id": brand["_id"],
            "members": [{"creator_id": m["id"], "price": m["price"], "split": round(m["price"] / total, 4)} for m in members],
            "total": total,
            "combined_reach": sum(m["effective_reach"] for m in members),
            "status": "offered",
            "created_at": at,
        }
    )
    for m in members:
        db.deals.insert_one(
            {
                "_id": f"dl_{uuid.uuid4().hex[:10]}",
                "kind": "collective",
                "collective_id": cid,
                "listing_id": listing_id,
                "brand_id": brand["_id"],
                "creator_id": m["id"],
                "amount": m["price"],
                "fair_at_offer": m["price"],
                "deliverables": x.get("deliverables"),
                "usage_rights_days": x.get("usage_rights_days") or 0,
                "exclusivity_days": x.get("exclusivity_days") or 0,
                "stage": "offer",
                "message": f"You're part of a {len(members)}-creator collective for {brand['name']}. One escrow payment, split automatically.",
                "timeline": [{"stage": "offer", "at": at, "note": f"Collective offer from {brand['name']}"}],
                "created_at": at,
            }
        )
    return {"id": cid, "members": len(members), "total": total}


class BrandIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=200)
    niches: list[str] = Field(min_length=1)
    ages: list[str] = Field(min_length=1)
    gender: Literal["any", "female", "male"] = "any"
    cities: list[str] = []
    languages: list[str] = Field(min_length=1)
    budget_monthly: int = Field(ge=5_000, le=50_000_000)
    goal: str = "Awareness"


@router.post("/brands")
def create_brand(body: BrandIn):
    db = get_db()
    bid = f"br_new_{uuid.uuid4().hex[:6]}"
    regions = sorted({CITIES[c][1] for c in body.cities if c in CITIES}) or ["North", "South", "East", "West", "Central", "Northeast"]
    db.brands.insert_one(
        {
            "_id": bid,
            "kind": "brand",
            "name": body.name.strip(),
            "category": body.category.strip(),
            "description": body.description.strip(),
            "hue": sum(map(ord, body.name)) % 360,
            "niches": body.niches,
            "target": {"ages": body.ages, "gender": body.gender, "regions": regions, "cities": body.cities, "languages": body.languages},
            "budget_monthly": body.budget_monthly,
            "goal": body.goal,
            "verified": True,
            "created_at": now_iso(),
        }
    )
    return {"id": bid}

