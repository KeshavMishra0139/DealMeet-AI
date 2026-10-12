"""Creator Studio API."""
from __future__ import annotations

import random
import re
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..ai.regional import tag_captions
from ..config import get_settings, now_iso
from ..db import get_db
from ..engines import brand_safety, money_paths, next_step, roadmap
from ..engines.fair_price import fair_price
from ..engines.matching import audience_fit
from ..seed.catalog import CITIES, NICHES
from ..seed.creators import AGE_PROFILES, _audience, _follower_history, _reels
from ..services import auth as au
from ..services import cache, reach, social_signin
from ..services import creator_ctx as cc
from ..services.views import creator_card

router = APIRouter(prefix="/api", tags=["creators"])


def _summary(c: dict) -> dict:
    card = creator_card(c)
    card["reference_note"] = c.get("reference_note")
    card["income_goal"] = c.get("income_goal")
    return card


@router.get("/creators/{creator_id}/home")
def home(creator_id: str, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    ctx = cc.build(c)
    return {
        "creator": _summary(c),
        "stage": ctx["stage"],
        "plan": ctx["plan"],
        "durable": ctx["durable"],
        "rate_gap": cc.rate_gap(c, ctx["fair"]),
        "pipeline": cc.pipeline(c),
        "context": cc.context_line(c),
    }


class MoveAction(BaseModel):
    action: Literal["done", "skip", "reopen"]
    result: Literal["worked", "partly", "no"] | None = None
    amount: int | None = Field(default=None, ge=0, le=10_000_000)
    note: str | None = Field(default=None, max_length=280)


@router.post("/creators/{creator_id}/moves/{move_id}")
def update_move(creator_id: str, move_id: str, body: MoveAction, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    status = {"done": "done", "skip": "skipped", "reopen": "open"}[body.action]
    try:
        return next_step.record_outcome(c, move_id, body.result, body.amount, body.note, status)
    except KeyError:
        raise HTTPException(404, "Move not found")


@router.post("/creators/{creator_id}/plan/next")
def plan_next(creator_id: str, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    ctx = cc.build(c, with_plan=False)
    return next_step.next_week(c, ctx)


@router.get("/creators/{creator_id}/roadmap")
def get_roadmap(creator_id: str, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    ctx = cc.build(c)
    return {
        "creator": _summary(c),
        "stage": ctx["stage"],
        **roadmap.build(c, ctx["stage"]["id"], ctx["plan"]["moves"], ctx["paths"]),
    }


@router.get("/creators/{creator_id}/money")
def money(creator_id: str, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    ctx = cc.build(c, with_plan=False)
    brands = sorted(
        (b for b in get_db().brands.find({"kind": "brand", "verified": True})),
        key=lambda b: -audience_fit(c, b)["fit"],
    )
    best = ctx["brand"]
    options = [{"id": b["_id"], "name": b["name"], "category": b["category"], "fit": audience_fit(c, b)["score"]} for b in brands]
    if options:  # a new marketplace may have no verified brands yet
        first = next((o for o in options if best and o["id"] == best["_id"]), options[0])
        ordered = [first, options[-1]] + options
        options = [o for i, o in enumerate(ordered) if o not in ordered[:i]]
    return {
        "creator": _summary(c),
        "stage": ctx["stage"],
        "fair": ctx["fair"],
        "brand_options": options,
        "paths": ctx["paths"],
        "goal": money_paths.goal_summary(c, ctx["paths"]),
        "durable": ctx["durable"],
        "rate_gap": cc.rate_gap(c, ctx["fair"]),
    }


@router.get("/creators/{creator_id}/fair-price")
def get_fair_price(creator_id: str, lister_id: str | None = None, listing_id: str | None = None, _: dict = Depends(au.own_creator)):
    c = cc.load_creator(creator_id)
    db = get_db()
    lister = db.brands.find_one({"_id": lister_id}) if lister_id else None
    terms = None
    if listing_id:
        listing = db.listings.find_one({"_id": listing_id})
        if not listing:
            raise HTTPException(404, "Listing not found")
        lister = lister or db.brands.find_one({"_id": listing["owner_id"]})
        terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    return fair_price(c, lister, terms)


# ------------------------------------------------------------------ onboarding
STAGE_FOLLOWERS = {"zero": 0, "under_1k": 450, "1k_10k": 3_200, "10k_100k": 24_000, "100k_plus": 140_000}


Short = Annotated[str, Field(max_length=60)]
Caption = Annotated[str, Field(max_length=2200)]  # Instagram's caption limit


class OnboardingIn(BaseModel):
    name: str = Field(min_length=1, max_length=60)
    niche: str = Field(max_length=40)
    platforms: list[Short] = Field(default=["instagram"], max_length=4)
    formats: list[Short] = Field(default=["reels"], max_length=10)
    audience_stage: Literal["zero", "under_1k", "1k_10k", "10k_100k", "100k_plus"]
    followers: int | None = Field(default=None, ge=0, le=50_000_000)
    income_goal: int = Field(ge=0, le=10_000_000)
    income_types: list[Short] = Field(default=[], max_length=10)
    languages: list[Short] = Field(min_length=1, max_length=10)
    city: str = Field(max_length=60)
    expertise: str | None = Field(default=None, max_length=80)
    captions: list[Caption] = Field(default=[], max_length=8)
    # Demo mode only: fill the profile with generated sample insights, labelled sample data.
    # Real numbers come from connecting Instagram or YouTube after onboarding.
    sample_insights: bool = False
    discoverable: bool = True
    consent_defaults: dict[Literal["stats", "demographics", "rate_card"], bool] = {"stats": True, "demographics": False, "rate_card": False}


def _handle(name: str) -> str:
    base = re.sub(r"[^a-z0-9]+", ".", name.lower()).strip(".") or "creator"
    db = get_db()
    handle, n = base, 1
    while db.creators.count_documents({"handle": handle}):
        n += 1
        handle = f"{base}{n}"
    return handle


@router.post("/creators")
def create_creator(body: OnboardingIn, user: dict = Depends(au.current_user)):
    """Onboarding: creates the signed-in creator account's profile, once."""
    au.require_role(user, "creator")
    if body.niche not in NICHES:
        raise HTTPException(422, "Unknown niche")
    db = get_db()
    if user.get("creator_id") and db.creators.count_documents({"_id": user["creator_id"]}):
        raise HTTPException(409, "This account already has a creator profile.")
    if body.sample_insights and not get_settings().demo_mode:
        raise HTTPException(422, "Sample insights exist only in demo mode. Connect Instagram or YouTube for real numbers.")
    if db.creators.count_documents({"created_by": "onboarding"}) >= 100:
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    followers = body.followers if body.followers is not None else STAGE_FOLLOWERS[body.audience_stage]
    cid = f"cr_new_{db.creators.count_documents({'created_by': 'onboarding'}) + 1}"
    while db.creators.count_documents({"_id": cid}):
        cid += "x"
    rng = random.Random(cid)
    city = body.city if body.city in CITIES else "Mumbai"
    connected = body.sample_insights  # sample data stands in for a connected account, labelled so
    langs = body.languages
    captions = [x.strip() for x in body.captions if x.strip()]
    caption_tags = tag_captions(captions) if captions else None
    doc = {
        "_id": cid,
        "handle": _handle(body.name),
        "name": body.name.strip(),
        "avatar_hue": rng.randint(0, 359),
        "is_reference": False,
        "reference_note": "Your profile. Insights are sample data for the demo, marked simulated." if connected else "Your profile, from what you typed in onboarding. Audience details are sample data, marked simulated.",
        "bio": f"{NICHES[body.niche]['label']} from {city}.",
        "niche": body.niche,
        "sub_niches": [],
        "platforms": body.platforms or ["instagram"],
        "formats": body.formats or ["reels"],
        "languages": langs,
        "city": city,
        "state": CITIES[city][0],
        "region": CITIES[city][1],
        "followers": followers,
        "following": max(50, int(followers * 0.05)) if followers else 0,
        "posts": 0,
        "reels": _reels(cid, body.niche, langs, followers, {}, rng) if connected and followers > 0 else [],
        "follower_history": _follower_history(followers, {}, rng) if connected and followers > 0 else [],
        "comment_insights": {"generic_share": 0.14, "sample_size": 60} if connected else {},
        "audience": _audience(body.niche, langs, city, rng),
        "income_goal": {"monthly": body.income_goal, "types": body.income_types},
        "income_history": [],
        "past_deals": [],
        "best_deal": None,
        "current_rate": None,
        "inbound_channels": [],
        "skills": [],
        "expertise": body.expertise or None,
        # Safety flags found in the creator's own captions become brand-safety notes, with the fix suggested.
        "content_flags": [f for f in ((caption_tags or {}).get("summary") or {}).get("flags", []) if f in brand_safety.FLAGS],
        "discoverable": body.discoverable,
        "consent_defaults": body.consent_defaults,
        "insights_connected": {"instagram": False, "youtube": False},
        "insights_source": "synthetic" if connected else "typed",
        "caption_tags": caption_tags,
        "onboarded": True,
        "created_by": "onboarding",
        "created_at": now_iso(),
        "provenance": {},
        "provenance_default": "real",
    }
    # What the creator typed is theirs. Everything the demo generates (the sandbox
    # login's sample insights, the audience mix, counts derived from the follower
    # band) is marked simulated, so the app labels it like Creator A's simulated fields.
    sample = ["audience", "following", "posts"]
    if body.followers is None and followers:
        sample.append("followers")  # estimated from the audience stage
    if connected:
        sample += ["reels", "follower_history", "comment_insights", "avg_likes", "avg_comments"]
    doc["provenance"] = {k: "simulated" for k in sample}
    if doc["reels"]:
        doc["posts"] = len(doc["reels"]) * 3
        doc["avg_likes"] = int(sum(r["likes"] for r in doc["reels"]) / len(doc["reels"]))
        doc["avg_comments"] = int(sum(r["comments"] for r in doc["reels"]) / len(doc["reels"]))
    if AGE_PROFILES.get(body.niche) is None:
        raise HTTPException(422, "Unknown niche")
    doc.update(reach.measured(doc))  # brand search filters on it
    db.creators.insert_one(doc)
    au.link_profile(user, cid)
    # Signed in with Instagram or YouTube: their real numbers replace what was typed.
    notes = social_signin.attach_pending(user, cid)
    cache.invalidate("trust:")  # per-creator scores; the trained model stays
    cache.invalidate("spam")
    return {"id": cid, "handle": doc["handle"], "notes": notes}


class TagIn(BaseModel):
    captions: list[Caption] = Field(min_length=1, max_length=8)


@router.post("/ai/tag")
def ai_tag(body: TagIn, _: dict = Depends(au.current_user)):
    return tag_captions(body.captions)


@router.get("/creators/{creator_id}/weekly-report")
def weekly_report(creator_id: str, _: dict = Depends(au.own_creator)):
    """This week against last week: brand views, offers, payouts, reach and followers,
    aggregated from the database (services/weekly_report.py)."""
    from ..services import weekly_report as wr

    cc.load_creator(creator_id)
    return wr.build(creator_id)


@router.get("/creators/{creator_id}/connections")
def connections(creator_id: str, _: dict = Depends(au.own_creator)):
    """Instagram and YouTube connection status. Nothing is simulated for an account that
    isn't connected."""
    from ..services import social

    return social.status(cc.load_creator(creator_id))
