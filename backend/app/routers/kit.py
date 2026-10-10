"""Auto media kit (PDF) and the public JodiDar link-in-bio page."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..ai.llm import generate
from ..config import now_iso, today
from ..db import get_db
from ..engines import brand_safety, metrics
from ..engines.common import inr, inr_range, short
from ..engines.fair_price import fair_price
from ..engines.trust import trust_score
from ..seed.catalog import LANGS, NICHES
from ..services.creator_ctx import best_fit_brand, load_creator
from ..services.pdf import media_kit_pdf

router = APIRouter(prefix="/api", tags=["kit"])


class KitCopy(BaseModel):
    headline: str = Field(max_length=120)
    bio: str = Field(max_length=420)


def _public(c: dict) -> dict:
    p = c.get("public_scopes")
    if p is None:
        d = c.get("consent_defaults") or {}
        p = {"stats": d.get("stats", True), "demographics": d.get("demographics", False), "rates": True}
    return p


def _copy(c: dict, pub: dict) -> tuple[KitCopy, str]:
    """Headline and bio for the public kit. They quote reach numbers only when the
    creator shows stats publicly."""
    niche = NICHES[c["niche"]]["label"]
    langs = " and ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS)
    has = pub["stats"] and metrics.has_reels(c)
    ratio = metrics.reach_ratio(c) if has else 0
    # Only cite the best format when its label is real data, not simulated.
    best = metrics.by_topic(c)[0]["topic"] if has and metrics.by_topic(c) and metrics.prov(c, "reels.0.topic") != "simulated" else None
    noun = niche if niche.lower().endswith("edits") else f"{niche} reels"
    facts = (
        f"Niche: {niche}. Languages: {langs}. "
        + (f"Followers: {short(c.get('followers', 0))}. " if pub["stats"] else "")
        + (f"Median views of last 6 reels: {short(metrics.median_views(c))}. Reach ratio: about {ratio:.0f}x followers. Best format: {best}. " if has else "")
        + (f"City: {c.get('city')}." if c.get("city") else f"Region: {c.get('region')}.")
    )

    def fallback() -> KitCopy:
        head = f"{niche} in {langs}"
        if has and ratio >= 2:
            head += f", reaching about {ratio:.0f}x the follower count"
        bio = f"{noun} in {langs}."
        if has:
            bio += f" Recent reels have a median of {short(metrics.median_views(c))} views."
        if best:
            bio += f" {best} is the format audiences respond to most."
        bio += " Available for brand reels, collectives and long-term partnerships through JodiDar escrow."
        return KitCopy(headline=head, bio=bio)

    prompt = (
        f"{facts}\nWrite a media-kit headline (under 12 words) and a 2-sentence bio in the third person, "
        "describing the content and audience for brands. Do not quote the creator or invent opinions, numbers or past brand names."
    )
    return generate("media_kit_copy", prompt, KitCopy, fallback, facts=facts, max_tokens=400)


def build_kit(c: dict) -> dict:
    pub = _public(c)
    brand = best_fit_brand(c)
    fp1 = fair_price(c, brand, None, with_model=False)
    fp2 = fair_price(c, brand, {"deliverables": [{"kind": "reel", "count": 1}, {"kind": "story", "count": 2}]}, with_model=False)
    fp3 = fair_price(c, brand, {"deliverables": [{"kind": "reel", "count": 2}]}, with_model=False)
    copy, source = _copy(c, pub)
    sim_views = metrics.prov(c, "reels.0.views") == "simulated"
    sim_saves = metrics.prov(c, "reels.0.saves") == "simulated"
    stats = None
    if pub["stats"] and metrics.has_reels(c):
        stats = [
            {"label": "Followers", "value": short(c.get("followers", 0)), "simulated": metrics.prov(c, "followers") == "simulated"},
            {"label": "Median views, last 6", "value": short(metrics.median_views(c)), "simulated": sim_views},
            {"label": "Reach vs followers", "value": f"{metrics.reach_ratio(c):.1f}x", "simulated": sim_views},
            {"label": "Saves + shares / view", "value": f"{metrics.ss_rate(c) * 100:.1f}%", "simulated": sim_saves},
        ]
    formats = None
    if pub["stats"] and metrics.has_reels(c):
        sim_topic = metrics.prov(c, "reels.0.topic") == "simulated"
        formats = [{"topic": t["topic"], "views": short(t["median_views"]), "simulated": sim_topic} for t in metrics.by_topic(c) if t["count"] >= 2][:3]
    audience = None
    if pub["demographics"] and c.get("audience"):
        a = c["audience"]
        top_age = max(a["age"].items(), key=lambda kv: kv[1])
        cities = ", ".join(x["name"] for x in a.get("cities", [])[:3])
        audience = {
            "line": f"Mostly {top_age[0]} ({round(top_age[1] * 100)}%), {round(a['gender'].get('female', 0) * 100)}% women, top cities {cities}.",
            "simulated": metrics.prov(c, "audience") == "simulated",
        }
    rates = None
    if pub["rates"]:
        rates = [
            {"label": "1 reel", "value": inr_range(fp1["range"]["low"], fp1["range"]["high"])},
            {"label": "1 reel + 2 stories", "value": inr_range(fp2["range"]["low"], fp2["range"]["high"])},
            {"label": "2-reel bundle", "value": inr_range(fp3["range"]["low"], fp3["range"]["high"])},
        ]
    safety = brand_safety.assess(c)
    t = trust_score(c)
    has_sim = any(x.get("simulated") for x in (stats or []) + (formats or [])) or bool(audience and audience["simulated"])
    return {
        "creator_id": c["_id"],
        "name": c["name"],
        "handle": c["handle"],
        "avatar_hue": c.get("avatar_hue", 260),
        "is_reference": c.get("is_reference", False),
        "reference_note": c.get("reference_note") if c.get("is_reference") else None,
        "niche": NICHES[c["niche"]]["label"],
        "languages": [LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS],
        "location": c.get("city") or c.get("region"),
        "copy": copy.model_dump(),
        "copy_source": source,
        "stats": stats,
        "formats": formats,
        "audience": audience,
        "rates": rates,
        "from_rate": fp1["range"]["low"] if pub["rates"] else None,
        "trust": {"score": t["score"], "level": t["level"], "reasons": t["reasons"], "simulated": t.get("simulated", [])} if t else None,
        "safety_note": f"Brand safety: {safety['flags'][0]['label'].lower()}; {safety['flags'][0]['fix'].lower()}" if safety["flags"] else "Brand safety: no concerns found.",
        "public": pub,
        "link": f"jodidar.ai/c/{c['handle']}",
        "path": f"/c/{c['handle']}",
        "generated_on": today().strftime("%d %b %Y"),
        "has_simulated": has_sim,
    }


@router.get("/creators/{creator_id}/kit")
def kit(creator_id: str):
    return build_kit(load_creator(creator_id))


class PublicIn(BaseModel):
    stats: bool
    demographics: bool
    rates: bool


@router.post("/creators/{creator_id}/kit")
def update_public(creator_id: str, body: PublicIn):
    load_creator(creator_id)
    get_db().creators.update_one({"_id": creator_id}, {"$set": {"public_scopes": body.model_dump()}})
    return build_kit(load_creator(creator_id))


@router.get("/creators/{creator_id}/kit.pdf")
def kit_pdf(creator_id: str, request: Request):
    k = build_kit(load_creator(creator_id))
    k["link"] = request.url.netloc + k["path"]  # the address this demo is served from
    return Response(media_kit_pdf(k), media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="jodidar-media-kit-{k["handle"]}.pdf"'})


@router.get("/public/{handle}")
def public_page(handle: str):
    c = get_db().creators.find_one({"handle": handle.lstrip("@")})
    if not c or c.get("public_page") is False:
        raise HTTPException(404, "This page isn't here")
    k = build_kit(c)
    return {kk: v for kk, v in k.items() if kk not in ("public",)}


class BookIn(BaseModel):
    brand_name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    budget: int = Field(ge=500, le=50_000_000)
    deliverable: str = Field(default="reel", pattern=r"^(reel|reel_stories|bundle)$")
    message: str | None = Field(default=None, max_length=400)


@router.post("/public/{handle}/book")
def book(handle: str, body: BookIn):
    db = get_db()
    c = db.creators.find_one({"handle": handle.lstrip("@")})
    if not c:
        raise HTTPException(404, "Creator not found")
    if (
        db.deals.count_documents({"creator_id": c["_id"], "source": "link_in_bio"}) >= 30
        or db.brands.count_documents({"_id": {"$regex": "^br_(new|guest)_"}}) >= 50
    ):
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    bid = f"br_guest_{uuid.uuid4().hex[:6]}"
    db.brands.insert_one(
        {
            "_id": bid,
            "kind": "brand",
            "name": body.brand_name.strip(),
            "category": "Booked via link-in-bio",
            "description": "",
            "hue": sum(map(ord, body.brand_name)) % 360,
            "niches": [c["niche"]],
            "target": {"ages": [], "gender": "any", "regions": [], "cities": [], "languages": []},
            "verified": False,
            "guest": True,
            # The email isn't stored: other visitors of this shared demo could read it.
            "contact_given": True,
            "created_at": now_iso(),
        }
    )
    deliverables = {
        "reel": [{"kind": "reel", "count": 1}],
        "reel_stories": [{"kind": "reel", "count": 1}, {"kind": "story", "count": 2}],
        "bundle": [{"kind": "reel", "count": 2}],
    }[body.deliverable]
    fp = fair_price(c, None, {"deliverables": deliverables}, with_model=False)
    did = f"dl_{uuid.uuid4().hex[:10]}"
    at = now_iso()
    db.deals.insert_one(
        {
            "_id": did,
            "kind": "single",
            "listing_id": None,
            "brand_id": bid,
            "creator_id": c["_id"],
            "amount": body.budget,
            "fair_at_offer": fp["total"],
            "deliverables": deliverables,
            "usage_rights_days": 0,
            "exclusivity_days": 0,
            "stage": "offer",
            "message": body.message,
            "source": "link_in_bio",
            "timeline": [{"stage": "offer", "at": at, "note": f"Booking request from {body.brand_name.strip()} via link-in-bio"}],
            "created_at": at,
        }
    )
    return {
        "ok": True,
        "fair": fp["total"] if _public(c)["rates"] else None,
        "message": f"Sent to {c['name']}. Nothing is charged yet: if they accept, you e-sign and fund escrow on this booking's page. Nothing is emailed in this demo, so use Follow this booking to get back to it.",
        # The guest has no login yet, so this link opens the deal as their brand to sign and pay.
        "track": f"/brand/deals/{did}?as={bid}",
    }
