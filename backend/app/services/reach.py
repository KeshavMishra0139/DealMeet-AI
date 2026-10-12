"""Measured reach, stored on each creator so brand search can filter on it in MongoDB.

- creators.reach_views: the median views of the creator's last 6 reels, or their
  self-reported average views when there are no reels. None when neither exists:
  the follower-based estimate metrics.median_views falls back to is never stored,
  because a filter on it would rank creators on a guess.
- creators.reach_source: where the number came from (instagram_api, youtube_api,
  manual or synthetic), so the app can label it like every other number.

refresh() runs wherever reels or self-reported numbers change (onboarding, Instagram
sync and disconnect, self-reported metrics); backfill() fills creators that don't have
the field yet, after seeding and on every start.
"""
from __future__ import annotations

from ..db import get_db
from ..engines import metrics
from ..engines.common import safe_median
from .views import source_of


def measured(c: dict) -> dict:
    """{"reach_views": int | None, "reach_source": str | None} for a creator document."""
    recent = metrics.recent(c)
    if recent:
        return {"reach_views": int(round(safe_median(r["views"] for r in recent))), "reach_source": source_of(c, "reels.0.views")}
    manual = (c.get("manual") or {}).get("avg_views")
    if manual:
        return {"reach_views": int(manual), "reach_source": "manual"}
    return {"reach_views": None, "reach_source": None}


def refresh(creator_id: str) -> None:
    db = get_db()
    c = db.creators.find_one({"_id": creator_id}, {"reels": 1, "manual": 1, "provenance": 1, "provenance_default": 1, "insights_source": 1})
    if c:
        db.creators.update_one({"_id": creator_id}, {"$set": measured(c)})


def backfill(db=None) -> int:
    """Sets reach on every creator that doesn't have it yet. Safe to repeat."""
    db = db if db is not None else get_db()
    n = 0
    for c in db.creators.find({"reach_views": {"$exists": False}}, {"reels": 1, "manual": 1, "provenance": 1, "provenance_default": 1, "insights_source": 1}):
        db.creators.update_one({"_id": c["_id"]}, {"$set": measured(c)})
        n += 1
    return n
