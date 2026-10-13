from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db, out
from ..seed.catalog import CITIES, FORMATS, LANGS, NICHES
from ..services import cache
from ..services import profile as prof
from ..services.auth import own_brand, own_creator
from ..services.creator_ctx import load_creator
from ..services.views import creator_view

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/creators/{creator_id}")
def get_creator(creator_id: str, _: dict = Depends(own_creator)):
    c = get_db().creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    from ..engines import metrics

    # The words every screen uses for this creator's posts and audience (videos and subscribers on YouTube).
    return {**creator_view(c), "terms": metrics.terms(c)}


@router.get("/brands/{brand_id}")
def get_brand(brand_id: str, _: dict = Depends(own_brand)):
    b = get_db().brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    return out(b)


# ------------------------------------------------------------------ the creator's own profile
Short = Annotated[str, Field(min_length=1, max_length=40)]


class CollabPrefs(BaseModel):
    accepts: Literal["paid", "barter", "both"]
    min_fee: int | None = Field(default=None, ge=0, le=10_000_000)
    avoid: list[Short] = Field(default=[], max_length=10)


class ProfileIn(BaseModel):
    """Every field is optional; only what's sent changes."""

    name: str | None = Field(default=None, min_length=1, max_length=60)
    bio: str | None = Field(default=None, max_length=400)
    niche: str | None = Field(default=None, max_length=40)
    sub_niches: list[Short] | None = Field(default=None, max_length=6)
    city: str | None = Field(default=None, max_length=60)
    languages: list[Short] | None = Field(default=None, min_length=1, max_length=10)
    formats: list[Short] | None = Field(default=None, max_length=6)
    platforms: list[Literal["instagram", "youtube"]] | None = Field(default=None, max_length=2)
    collab_prefs: CollabPrefs | None = None


def _profile(c: dict) -> dict:
    from ..services import social

    return {
        "creator": creator_view(c),
        "collab_prefs": c.get("collab_prefs") or {"accepts": None, "min_fee": None, "avoid": []},
        "manual": c.get("manual"),
        "manual_history": prof.manual_history(c["_id"]),
        "platforms": social.status(c)["platforms"],
        "completeness": prof.completeness(c),
        "readiness": prof.readiness(c),
    }


@router.get("/creators/{creator_id}/profile")
def get_profile(creator_id: str, _: dict = Depends(own_creator)):
    return _profile(load_creator(creator_id))


@router.patch("/creators/{creator_id}/profile")
def update_profile(creator_id: str, body: ProfileIn, _: dict = Depends(own_creator)):
    c = load_creator(creator_id)
    changes = body.model_dump(exclude_none=True)
    if "niche" in changes and changes["niche"] not in NICHES:
        raise HTTPException(422, "Unknown niche")
    if "languages" in changes and any(x not in LANGS for x in changes["languages"]):
        raise HTTPException(422, "Unknown language")
    if "formats" in changes and any(x not in FORMATS for x in changes["formats"]):
        raise HTTPException(422, "Unknown format")
    if "city" in changes:
        if changes["city"] not in CITIES:
            raise HTTPException(422, "Pick a city from the list")
        changes["state"], changes["region"] = CITIES[changes["city"]]
    if "name" in changes:
        changes["name"] = changes["name"].strip()
    if "bio" in changes:
        changes["bio"] = changes["bio"].strip()
    if "sub_niches" in changes:
        changes["sub_niches"] = list(dict.fromkeys(x.strip() for x in changes["sub_niches"] if x.strip()))
    if changes:
        get_db().creators.update_one({"_id": creator_id}, {"$set": changes})
        cache.invalidate("trust:")
    return _profile(load_creator(creator_id))


class ManualIn(BaseModel):
    platform: Literal["instagram", "youtube"]
    followers: int = Field(ge=0, le=500_000_000)
    avg_views: int | None = Field(default=None, ge=0, le=500_000_000)
    engagement_pct: float | None = Field(default=None, ge=0, le=100)


@router.post("/creators/{creator_id}/manual-metrics")
def add_manual(creator_id: str, body: ManualIn, _: dict = Depends(own_creator)):
    """Self-reported numbers, labelled so, with history. Connected numbers always win."""
    c = load_creator(creator_id)
    result = prof.add_manual_metrics(c, body.platform, body.followers, body.avg_views, body.engagement_pct)
    return {**_profile(load_creator(creator_id)), "note": result["note"], "applied": result["applied"]}
