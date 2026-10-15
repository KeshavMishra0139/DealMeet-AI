"""YouTube public data: linking a creator's own channel, and YouTube Analytics."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..seed.catalog import NICHES
from ..services import auth as au
from ..services import ratelimit
from ..services import youtube_analytics as yta
from ..services import youtube_public as yt
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["youtube"])

LINK_PER_HOUR = 20


class LinkIn(BaseModel):
    handle: str = Field(min_length=2, max_length=200)


def _stored(creator_id: str) -> dict:
    c = load_creator(creator_id)
    summary = (c.get("channels") or {}).get("youtube")
    if not summary:
        return {"linked": False, "status": yt.status(c)}
    videos = list(get_db().posts.find({"creator_id": creator_id, "platform": "youtube"}, {"_id": 0, "description": 0}).sort("published_at", -1).limit(30))
    return {
        "linked": True,
        "status": yt.status(c),
        "channel": summary,
        "videos": videos[:12],
        "prices": yt.prices_for(videos, c["niche"]),
        "niche_label": NICHES[c["niche"]]["label"],
        "analytics": summary.get("analytics"),
        "analytics_consent": yta.CONSENT_TEXT,
        "source": yt.SOURCE,
        "fetched_at": summary.get("fetched_at"),
    }


@router.get("/creators/{creator_id}/youtube")
def get_linked(creator_id: str, _: dict = Depends(au.own_creator)):
    return _stored(creator_id)


@router.post("/creators/{creator_id}/youtube/link")
def link(creator_id: str, body: LinkIn, user: dict = Depends(au.own_creator)):
    """Link (or refresh) the creator's channel by handle. Public data, cached for 12 hours."""
    ratelimit.enforce(f"ytlink:{user['_id']}", LINK_PER_HOUR, 3600, "Too many channel lookups. Try again in an hour.")
    c = load_creator(creator_id)
    yt.save_for_creator(creator_id, yt.channel_report(body.handle, c["niche"]))
    return _stored(creator_id)


@router.delete("/creators/{creator_id}/youtube/link")
def unlink(creator_id: str, _: dict = Depends(au.own_creator)):
    """Removes the linked channel and every YouTube post and snapshot stored for it."""
    yt.unlink(creator_id)
    return _stored(creator_id)


class AnalyticsIn(BaseModel):
    # A Google OAuth access token with the YouTube scopes, used once and never stored.
    access_token: str = Field(min_length=20, max_length=4096)


def _own_creator_id(user: dict) -> str:
    au.require_role(user, "creator")
    if not user.get("creator_id"):
        raise HTTPException(409, "Finish onboarding first.")
    return user["creator_id"]


@router.post("/connect/youtube/analytics")
def connect_analytics(body: AnalyticsIn, user: dict = Depends(au.current_user)):
    """Reads the last 28 days of YouTube Analytics for the creator's linked channel."""
    creator_id = _own_creator_id(user)
    ratelimit.enforce(f"yta:{user['_id']}", 10, 3600, "Too many Analytics refreshes. Try again in an hour.")
    yta.connect(creator_id, body.access_token)
    au.audit("connect_youtube_analytics", user["_id"], user["role"])
    return _stored(creator_id)


@router.delete("/connect/youtube/analytics")
def disconnect_analytics(user: dict = Depends(au.current_user)):
    creator_id = _own_creator_id(user)
    yta.disconnect(creator_id)
    return _stored(creator_id)
