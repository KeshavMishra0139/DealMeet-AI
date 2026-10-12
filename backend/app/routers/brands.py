"""Brand Console API."""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from ..config import now_iso, today
from ..db import get_db, out
from ..engines import audience_overlap as overlap_engine
from ..engines import brand_matching, brand_safety, collective, metrics
from ..engines.common import inr
from ..engines.fair_price import fair_price
from ..engines.matching import listing_fit
from ..engines.trust import trust_score
from ..seed.catalog import CITIES, LANGS, NICHES
from ..services import auth as au
from ..services import brand_profile as bp
from ..services import cache
from ..services import campaigns as camp
from ..services import collectives
from ..services import consent as cs
from ..services import creator_search
from ..services import fan_proof, offers, payments, tee
from ..services.deals import auto_release_due, sweep
from ..services.views import audience_stage

Short = Annotated[str, Field(max_length=60)]

router = APIRouter(prefix="/api", tags=["brands"])

STAGES = ["offer", "contract", "escrow_funded", "live", "verified", "paid"]
STAGE_LABELS = {
    "offer": "Offer sent",
    "contract": "Contract",
    "escrow_funded": "Escrow funded",
    "live": "Post submitted",
    "verified": "Approved",
    "paid": "Paid out",
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


def _own_listing(listing_id: str, user: dict) -> dict:
    x = _listing(listing_id)
    au.require_listing_owner(user, x)
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
        "status": camp.status_of(x),
        "objectives": [camp.OBJECTIVES[o] for o in x.get("objectives") or [] if o in camp.OBJECTIVES],
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
def console(brand_id: str, _: dict = Depends(au.own_brand)):
    db = get_db()
    brand = _brand(brand_id)
    deals = [sweep(d) for d in db.deals.find({"brand_id": brand_id})]
    creators = {c["_id"]: c for c in db.creators.find({}, {"name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1})}
    campaigns = [_campaign_row(x, brand, deals) for x in db.listings.find({"owner_id": brand_id})]
    stages = {s: {"count": 0, "amount": 0} for s in STAGES}
    for d in deals:
        if d["stage"] in stages:
            stages[d["stage"]]["count"] += 1
            stages[d["stage"]]["amount"] += d["amount"]
    held = [d for d in deals if d["stage"] in ("escrow_funded", "live", "verified")]
    held_total = sum(d["amount"] for d in held)
    held_simulated = bool(held) and all((d.get("escrow") or {}).get("mode") == "simulated" for d in held)
    paid_total = sum(d["amount"] for d in deals if d["stage"] == "paid")
    paid_simulated = all((d.get("payout") or {}).get("status") == "simulated" for d in deals if d["stage"] == "paid")
    needs = []
    for d in deals:
        who = creators.get(d["creator_id"], {}).get("name", "A creator")
        if d["stage"] == "live":
            due = d.get("verify_due")
            late = due and due < today().isoformat()
            release = auto_release_due(d)
            left = (release - today()).days if release else 0
            overdue = f" Overdue; approved automatically in {left} day{'s' if left != 1 else ''}." if late else ""
            needs.append({"deal_id": d["_id"], "kind": "confirm", "text": f"Review {who}'s post", "detail": f"Approve it or ask for a revision ({inr(d['amount'])} in escrow).{overdue}", "urgent": bool(late)})
        elif d["stage"] == "contract" and not (d.get("contract") or {}).get("signed_by_brand"):
            needs.append({"deal_id": d["_id"], "kind": "sign", "text": f"Sign {who}'s contract", "detail": inr(d["amount"]), "urgent": False})
        elif d["stage"] == "contract" and (d.get("contract") or {}).get("signed_by_creator") and d.get("escrow") is None:
            needs.append({"deal_id": d["_id"], "kind": "fund", "text": f"Fund escrow for {who}", "detail": inr(d["amount"]), "urgent": False})
    live_campaigns = [c for c in campaigns if c["status"] == "live"]
    waiting = sum(1 for n in needs if n["kind"] == "confirm")
    headline = f"{len(live_campaigns)} campaign{'s' if len(live_campaigns) != 1 else ''} live. {inr(held_total)} held in escrow{' (simulated)' if held_simulated else ''}."
    if waiting:
        headline += f" {waiting} post{'s' if waiting != 1 else ''} waiting for your confirmation."
    return {
        "brand": out(brand),
        "headline": headline,
        "campaigns": sorted(campaigns, key=lambda c: c["posted_on"] or "", reverse=True),
        "escrow": {
            "held": held_total,
            "simulated": held_simulated,
            "count": len(held),
            "items": [
                {"deal_id": d["_id"], "creator": creators.get(d["creator_id"], {}).get("name"), "amount": d["amount"], "stage": d["stage"], "stage_label": STAGE_LABELS[d["stage"]]}
                for d in held
            ],
        },
        "paid_total": paid_total,
        "paid_simulated": paid_simulated,
        "payments_mode": payments.mode(),
        "payout_mode": payments.payout_mode(),
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
def campaigns(brand_id: str, _: dict = Depends(au.own_brand)):
    brand = _brand(brand_id)
    deals = list(get_db().deals.find({"brand_id": brand_id}))
    return [_campaign_row(x, brand, deals) for x in get_db().listings.find({"owner_id": brand_id})]


Objective = Literal["awareness", "consideration", "sales", "launch", "content"]


class CampaignEdit(BaseModel):
    """Every campaign field. A draft can be incomplete; publishing checks it."""

    title: str | None = Field(default=None, min_length=4, max_length=90)
    summary: str | None = Field(default=None, max_length=400)
    objectives: list[Objective] | None = Field(default=None, max_length=5)
    niches: list[Short] | None = Field(default=None, max_length=12)
    languages: list[Short] | None = Field(default=None, max_length=10)
    audience_ages: list[Short] | None = Field(default=None, max_length=5)
    audience_gender: Literal["any", "female", "male"] | None = None
    regions: list[Short] | None = Field(default=None, max_length=8)
    cities: list[Short] | None = Field(default=None, max_length=30)
    collective_size: int | None = Field(default=None, ge=10, le=50)
    budget_min: int | None = Field(default=None, ge=0, le=100_000_000)
    budget_max: int | None = Field(default=None, ge=0, le=100_000_000)
    budget_total: int | None = Field(default=None, ge=0, le=100_000_000)
    reels: int | None = Field(default=None, ge=0, le=5)
    stories: int | None = Field(default=None, ge=0, le=10)
    usage_rights_days: int | None = Field(default=None, ge=0, le=365)
    exclusivity_days: int | None = Field(default=None, ge=0, le=365)
    min_followers: int | None = Field(default=None, ge=0, le=50_000_000)
    start_date: str | None = Field(default=None, max_length=10)
    deadline: str | None = Field(default=None, max_length=10)


class CampaignIn(CampaignEdit):
    title: str = Field(min_length=4, max_length=90)
    collective: bool = False


def _changes(body: CampaignEdit, x: dict) -> dict:
    """The sent fields, in the stored shape."""
    sent = body.model_dump(exclude_unset=True)
    ch: dict = {}
    for k in ("objectives", "niches", "languages", "regions", "cities", "usage_rights_days", "exclusivity_days", "min_followers", "start_date", "deadline"):
        if k in sent:
            ch[k] = sent[k] if sent[k] is not None else ([] if k in ("objectives", "niches", "languages", "regions", "cities") else (None if k in ("start_date", "deadline") else 0))
    for k in ("title", "summary"):
        if sent.get(k) is not None:
            ch[k] = sent[k].strip()
    if "audience_ages" in sent or "audience_gender" in sent:
        aud = dict(x.get("audience") or {"ages": [], "gender": "any"})
        if "audience_ages" in sent:
            aud["ages"] = sent["audience_ages"] or []
        if sent.get("audience_gender"):
            aud["gender"] = sent["audience_gender"]
        ch["audience"] = aud
    if "reels" in sent or "stories" in sent:
        cur = {d["kind"]: d["count"] for d in x.get("deliverables") or []}
        reels = sent.get("reels", cur.get("reel", 0)) or 0
        stories = sent.get("stories", cur.get("story", 0)) or 0
        ch["deliverables"] = [d for d in x.get("deliverables") or [] if d["kind"] not in ("reel", "story")]
        ch["deliverables"] = ([{"kind": "reel", "count": reels}] if reels else []) + ([{"kind": "story", "count": stories}] if stories else []) + ch["deliverables"]
    budget = dict(x.get("budget") or {})
    if x.get("type") == "collective":
        if "budget_total" in sent:
            budget["total"] = sent["budget_total"]
            ch["budget"] = budget
        if sent.get("collective_size"):
            ch["collective_size"] = sent["collective_size"]
    elif x.get("deal_kind") != "affiliate" and ("budget_min" in sent or "budget_max" in sent):
        if "budget_min" in sent:
            budget["per_creator_min"] = sent["budget_min"]
        if "budget_max" in sent:
            budget["per_creator_max"] = sent["budget_max"]
        ch["budget"] = budget
    return ch


def _campaign_view(x: dict, user: dict) -> dict:
    d = out(x)
    d["status"] = camp.status_of(x)
    owner = get_db().brands.find_one({"_id": x["owner_id"]})
    d["owner"] = {"id": owner["_id"], "name": owner["name"], "hue": owner.get("hue", 260), "slug": owner.get("slug")} if owner else None
    d["language_labels"] = [LANGS[l]["label"] for l in x.get("languages") or [] if l in LANGS]
    d["niche_labels"] = [NICHES[n]["label"] for n in x.get("niches") or [] if n in NICHES]
    d["objective_labels"] = [camp.OBJECTIVES[o] for o in x.get("objectives") or [] if o in camp.OBJECTIVES]
    mine = x["owner_id"] in (user.get("brand_id"), user.get("creator_id"))
    if mine:
        d["missing"] = camp.missing(x)
        d["actions"] = [a for a, (frm, to) in camp.TRANSITIONS.items() if camp.status_of(x) in frm]
    else:
        d.pop("history", None)
    return d


@router.post("/brands/{brand_id}/campaigns")
def create_campaign(brand_id: str, body: CampaignIn, user: dict = Depends(au.own_brand)):
    """Creates a draft. Creators don't see it until it's published."""
    _brand(brand_id)
    if get_db().listings.count_documents({"owner_id": brand_id}) >= 20:
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    lid = f"lst_{brand_id[3:]}_{uuid.uuid4().hex[:6]}"
    base = {
        "_id": lid,
        "type": "collective" if body.collective else "brand_campaign",
        "owner_id": brand_id,
        "title": "",
        "summary": "",
        "objectives": [],
        "niches": [],
        "languages": [],
        "audience": {"ages": [], "gender": "any"},
        "regions": ["Pan-India"],
        "cities": [],
        "deal_kind": "collective" if body.collective else "paid",
        "deliverables": [{"kind": "reel", "count": 1}],
        "usage_rights_days": 0,
        "exclusivity_days": 0,
        "min_followers": 0,
        "max_followers": None,
        "budget": {},
        "collective_size": 20 if body.collective else None,
        "posted_on": today().isoformat(),
        "start_date": None,
        "deadline": None,
        "source": "manual",
        "created_at": now_iso(),
    }
    changes = _changes(body, base)
    camp.validate_fields(changes)
    camp.create({**base, **changes}, user)
    cache.invalidate("spam")
    x = _listing(lid)
    return {"id": lid, "status": "draft", "missing": camp.missing(x)}


@router.patch("/campaigns/{listing_id}")
def edit_campaign(listing_id: str, body: CampaignEdit, user: dict = Depends(au.current_user)):
    x = _own_listing(listing_id, user)
    camp.edit(x, _changes(body, x), user)
    cache.invalidate("spam")
    return _campaign_view(_listing(listing_id), user)


class StatusIn(BaseModel):
    action: Literal["publish", "pause", "resume", "close"]


@router.post("/campaigns/{listing_id}/status")
def campaign_status(listing_id: str, body: StatusIn, user: dict = Depends(au.current_user)):
    """draft -> live -> paused <-> live; any -> closed (final)."""
    x = _own_listing(listing_id, user)
    x, changed = camp.transition(x, body.action, user)
    return {**_campaign_view(x, user), "changed": changed}


@router.get("/campaigns/{listing_id}/applications")
def campaign_applications(listing_id: str, user: dict = Depends(au.current_user)):
    return camp.applications(_own_listing(listing_id, user))


class ApplicationIn(BaseModel):
    status: Literal["applied", "shortlisted", "declined"]


@router.post("/campaigns/{listing_id}/applications/{creator_id}")
def campaign_application(listing_id: str, creator_id: str, body: ApplicationIn, user: dict = Depends(au.current_user)):
    """Shortlist or decline an application (or move it back to applied)."""
    return camp.set_application(_own_listing(listing_id, user), creator_id, body.status, user)


@router.get("/listings/{listing_id}")
def listing_detail(listing_id: str, user: dict = Depends(au.current_user)):
    x = _listing(listing_id)
    if not camp.visible_to(x, user):
        raise HTTPException(404, "Campaign not found")
    return _campaign_view(x, user)


@router.get("/listings/{listing_id}/matches")
def listing_matches(listing_id: str, user: dict = Depends(au.current_user)):
    x = _own_listing(listing_id, user)
    return brand_matching.matches(x, _brand(x["owner_id"]))


class CollectiveIn(BaseModel):
    budget: int | None = Field(default=None, ge=5_000)
    size_min: int = Field(default=10, ge=2, le=50)
    size_max: int = Field(default=50, ge=2, le=50)
    trust_min: int = Field(default=60, ge=0, le=100)
    target_reach: int | None = None


@router.post("/listings/{listing_id}/collective")
def build_collective(listing_id: str, body: CollectiveIn, user: dict = Depends(au.current_user)):
    x = _own_listing(listing_id, user)
    brand = _brand(x["owner_id"])
    return collective.build(x, brand, body.budget, body.size_min, body.size_max, body.trust_min, body.target_reach)


OVERLAP_NOTE = {
    "tee": "Computed inside an attested enclave (AWS Nitro Enclaves); its measurements matched our policy.",
    "not_configured": "Computed on DealMeet's server, from only the percentages this needs.",
    "failed": "Nothing was sent to it. Computed on DealMeet's server, from only the percentages this needs.",
}


def _audience_overlap(audience: dict, brand: dict) -> dict:
    """The protected job (services/tee.py), or its documented fallback on minimised data."""
    out = tee.protected(overlap_engine.JOB, overlap_engine.minimise(audience, brand.get("target") or {}), overlap_engine.compute)
    note = OVERLAP_NOTE["tee" if out["processed_in"] == "tee" else out["tee_status"]]
    return {**out["result"], "processed_in": out["processed_in"], "tee_status": out["tee_status"], "note": note}


@router.get("/brands/{brand_id}/creators")
def search_creators(
    brand_id: str,
    q: str | None = Query(default=None, max_length=80),
    niche: str | None = Query(default=None, max_length=40),
    followers: str | None = Query(default=None, max_length=20),
    reach: str | None = Query(default=None, max_length=20),
    sort: str = Query(default="reach", max_length=10),
    page: int = Query(default=1, ge=1, le=200),
    _: dict = Depends(au.own_brand),
):
    """Find creators: partial text match, exact niche, follower band and reach range.
    Only fields this brand may see (services/creator_search.py)."""
    _brand(brand_id)
    return creator_search.search(brand_id, q, niche, followers, reach, sort, page)


@router.get("/brands/{brand_id}/creators/{creator_id}")
def creator_for_brand(brand_id: str, creator_id: str, listing_id: str | None = None, _: dict = Depends(au.own_brand)):
    db = get_db()
    brand = _brand(brand_id)
    c = db.creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    scopes = cs.scopes_for(c, brand_id)
    if scopes is None:
        raise HTTPException(404, "This creator isn't discoverable to you")
    listing = db.listings.find_one({"_id": listing_id}) if listing_id else None
    if listing_id and (not listing or listing["owner_id"] != brand_id):
        raise HTTPException(403, "That campaign belongs to another account.")
    cs.log_view(creator_id, brand_id, scopes)
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
    overlap = None
    if scopes["demographics"]:
        demographics = {**(c.get("audience") or {}), "provenance": metrics.prov(c, "audience")}
        if c.get("audience"):
            overlap = _audience_overlap(c["audience"], brand)
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
            "follower_price": fp["follower_price"] if scopes["stats"] else None,  # it would reveal the follower count
            "model_check": fp.get("model_check"),
        },
        "stats": stats,
        "demographics": demographics,
        "audience_overlap": overlap,
        "rate_card": rate_card,
        "listing": {"id": listing["_id"], "title": listing["title"]} if listing else None,
        "fan_proof": fan_proof.summary(creator_id, brand_id),
        "deal": out(db.deals.find_one({"creator_id": creator_id, "brand_id": brand_id, "listing_id": listing_id})) if listing_id else None,
    }


class AccessIn(BaseModel):
    scopes: list[Literal["stats", "demographics", "rate_card"]]


@router.post("/brands/{brand_id}/creators/{creator_id}/request-access")
def request_access(brand_id: str, creator_id: str, body: AccessIn, _: dict = Depends(au.own_brand)):
    _brand(brand_id)
    if not get_db().creators.find_one({"_id": creator_id}):
        raise HTTPException(404, "Creator not found")
    cs.request(creator_id, brand_id, list(body.scopes))
    return {"requested": body.scopes}


class OfferIn(BaseModel):
    # The sending brand comes from the session. An id sent here must match it.
    brand_id: str | None = None
    creator_id: str
    listing_id: str | None = None
    amount: int = Field(ge=500, le=10_000_000)
    message: str | None = Field(default=None, max_length=400)


@router.post("/offers")
def send_offer(body: OfferIn, user: dict = Depends(au.current_user)):
    au.require_role(user, "brand")
    if body.brand_id and body.brand_id != user.get("brand_id"):
        raise HTTPException(403, "You can only send offers as your own brand.")
    body.brand_id = user.get("brand_id")
    db = get_db()
    brand = _brand(body.brand_id or "")
    c = db.creators.find_one({"_id": body.creator_id})
    if not c:
        raise HTTPException(404, "Creator not available")
    listing = db.listings.find_one({"_id": body.listing_id}) if body.listing_id else None
    if body.listing_id and (not listing or listing["owner_id"] != body.brand_id):
        raise HTTPException(403, "That campaign belongs to another account.")
    return offers.create_offer(brand, c, listing, body.amount, body.message, user["_id"])


class DeliverableIn(BaseModel):
    kind: Literal["reel", "story", "short", "carousel", "live", "link_in_bio"]
    count: int = Field(ge=0, le=20)


class MemberTerms(BaseModel):
    price: int | None = Field(default=None, ge=500, le=10_000_000)
    deliverables: list[DeliverableIn] | None = Field(default=None, max_length=6)


class BookIn(BaseModel):
    member_ids: list[Short] = Field(min_length=2, max_length=50)
    # The de-duplicated reach the builder showed; booking re-prices the chosen members as a fixed pack.
    combined_reach: int | None = Field(default=None, ge=0)
    # The brand's adjustments before sending: a member's fee and deliverables.
    adjust: dict[Short, MemberTerms] = Field(default={}, max_length=50)


@router.post("/listings/{listing_id}/collective/book")
def book_collective(listing_id: str, body: BookIn, user: dict = Depends(au.current_user)):
    """Sends the collective. Each member then confirms their own terms."""
    x = _own_listing(listing_id, user)
    brand = _brand(x["owner_id"])
    adjust = {k: v.model_dump(exclude_none=True) for k, v in body.adjust.items()}
    return collectives.book(x, brand, list(dict.fromkeys(body.member_ids)), adjust, body.combined_reach, user)


class BrandIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    category: str = Field(min_length=2, max_length=60)
    description: str = Field(default="", max_length=400)
    website: str | None = Field(default=None, max_length=200)
    contact_email: str | None = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

    @field_validator("website")
    @classmethod
    def _site(cls, v: str | None) -> str | None:
        return bp.clean_website(v)
    niches: list[Short] = Field(min_length=1, max_length=12)
    ages: list[Short] = Field(min_length=1, max_length=12)
    gender: Literal["any", "female", "male"] = "any"
    cities: list[Short] = Field(default=[], max_length=30)
    languages: list[Short] = Field(min_length=1, max_length=12)
    budget_monthly: int = Field(ge=5_000, le=50_000_000)
    goal: str = Field(default="Awareness", max_length=40)


@router.post("/brands")
def create_brand(body: BrandIn, user: dict = Depends(au.current_user)):
    """Brand onboarding: creates the signed-in brand account's organisation, once."""
    au.require_role(user, "brand")
    db = get_db()
    if user.get("brand_id") and db.brands.count_documents({"_id": user["brand_id"]}):
        raise HTTPException(409, "This account already has a brand profile.")
    if db.brands.count_documents({"_id": {"$regex": "^br_(new|guest)_"}}) >= 50:
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    bid = f"br_new_{uuid.uuid4().hex[:6]}"
    regions = sorted({CITIES[c][1] for c in body.cities if c in CITIES}) or ["North", "South", "East", "West", "Central", "Northeast"]
    db.brands.insert_one(
        {
            "_id": bid,
            "kind": "brand",
            "name": body.name.strip(),
            "slug": bp.unique_slug(body.name),
            "category": body.category.strip(),
            "description": body.description.strip(),
            "website": body.website,
            "contact": {"name": user.get("name"), "email": body.contact_email, "phone": None},
            "source": "manual",
            "owner_user_id": user["_id"],
            "hue": sum(map(ord, body.name)) % 360,
            "niches": body.niches,
            "target": {"ages": body.ages, "gender": body.gender, "regions": regions, "cities": body.cities, "languages": body.languages},
            "budget_monthly": body.budget_monthly,
            "goal": body.goal,
            "verified": False,  # nothing checks a self-registered brand in this demo
            "created_at": now_iso(),
        }
    )
    au.link_profile(user, bid)
    au.audit("brand_created", user["_id"], "brand", brand_id=bid)
    return {"id": bid}


@router.get("/brands/{brand_id}/profile")
def brand_profile(brand_id: str, _: dict = Depends(au.own_brand)):
    """The organisation profile, with its private contact (owner only)."""
    return bp.view(_brand(brand_id), owner=True)


@router.patch("/brands/{brand_id}/profile")
def update_brand_profile(brand_id: str, body: bp.OrgIn, user: dict = Depends(au.own_brand)):
    return bp.update(_brand(brand_id), body, user)

