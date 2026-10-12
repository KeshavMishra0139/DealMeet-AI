"""Creator search for brands: text, niche, follower band and reach, queried in MongoDB.

What a brand may filter on follows what it may see (services/consent.py):
- Creators who aren't discoverable, or who revoked this brand, never appear.
- Niche and the follower band (for example "1K to 10K") are shown to every brand, so
  anyone can filter on them.
- Exact followers and reach (median views) belong to the "stats" scope. They come back
  only for creators who share stats with this brand, and the reach filter and sort only
  ever look at those creators. Otherwise narrowing the filter would reveal hidden numbers.
  The response says how many creators were left out for that reason, never which.

Reach is the stored, measured creators.reach_views (services/reach.py), so the range is
a database query. The text search is a case-insensitive partial match (an escaped regex)
on name, handle, bio, city and sub-niches, plus any niche whose label matches.
"""
from __future__ import annotations

import re

from fastapi import HTTPException

from ..db import get_db
from ..seed.catalog import LANGS, NICHES, STAGES
from .views import audience_stage

PAGE_SIZE = 24

FOLLOWER_BANDS = [s for s in STAGES if s["id"] != "zero"]
REACH_BUCKETS = [
    {"id": "under_1k", "label": "Under 1K", "min": 0, "max": 999},
    {"id": "1k_10k", "label": "1K to 10K", "min": 1_000, "max": 9_999},
    {"id": "10k_50k", "label": "10K to 50K", "min": 10_000, "max": 49_999},
    {"id": "50k_100k", "label": "50K to 100K", "min": 50_000, "max": 99_999},
    {"id": "100k_plus", "label": "100K+", "min": 100_000, "max": None},
]
SORTS = {"reach": "Highest reach first", "name": "Name, A to Z"}

FIELDS = {
    "name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1, "niche": 1, "languages": 1, "city": 1,
    "followers": 1, "reach_views": 1, "reach_source": 1, "source": 1, "provenance": 1, "provenance_default": 1,
    "insights_source": 1,
}


def options() -> dict:
    """The filter choices, so the web app doesn't keep its own copy."""
    return {
        "niches": [{"id": k, "label": v["label"]} for k, v in sorted(NICHES.items(), key=lambda kv: kv[1]["label"])],
        "followers": [{"id": b["id"], "label": b["label"]} for b in FOLLOWER_BANDS],
        "reach": [{"id": b["id"], "label": b["label"]} for b in REACH_BUCKETS],
        "sorts": [{"id": k, "label": v} for k, v in SORTS.items()],
    }


def _range(lo: int, hi: int | None) -> dict:
    return {"$gte": lo, **({"$lte": hi} if hi is not None else {})}


def _pick(items: list[dict], value: str | None, what: str) -> dict | None:
    if not value:
        return None
    found = next((i for i in items if i["id"] == value), None)
    if not found:
        raise HTTPException(422, f"Unknown {what} filter.")
    return found


def search(brand_id: str, q: str | None = None, niche: str | None = None, followers: str | None = None, reach: str | None = None, sort: str = "reach", page: int = 1) -> dict:
    db = get_db()
    if niche and niche not in NICHES:
        raise HTTPException(422, "Unknown niche.")
    band = _pick(FOLLOWER_BANDS, followers, "followers")
    bucket = _pick(REACH_BUCKETS, reach, "reach")
    if sort not in SORTS:
        raise HTTPException(422, "Unknown sort.")

    # Consent: who's hidden from this brand, and who shares stats with it.
    grants = list(db.consents.find({"lister_id": brand_id}, {"creator_id": 1, "status": 1, "scopes": 1}))
    revoked = [g["creator_id"] for g in grants if g["status"] == "revoked"]
    active = {g["creator_id"]: g.get("scopes") or {} for g in grants if g["status"] == "active"}
    shares_stats = {"$or": [
        {"_id": {"$in": [cid for cid, s in active.items() if s.get("stats")]}},
        {"_id": {"$nin": list(active)}, "consent_defaults.stats": True},
    ]}

    clauses: list[dict] = [{"discoverable": {"$ne": False}}]
    if revoked:
        clauses.append({"_id": {"$nin": revoked}})
    text = (q or "").strip()
    if text:
        rx = {"$regex": re.escape(text), "$options": "i"}
        matches: list[dict] = [{"name": rx}, {"handle": rx}, {"bio": rx}, {"city": rx}, {"sub_niches": rx}]
        niche_ids = [k for k, v in NICHES.items() if text.lower() in v["label"].lower()]
        if niche_ids:
            matches.append({"niche": {"$in": niche_ids}})
        clauses.append({"$or": matches})
    if niche:
        clauses.append({"niche": niche})
    if band:
        clauses.append({"followers": _range(band["min"], band["max"])})
    hidden = 0
    if bucket:
        hidden = db.creators.count_documents({"$and": [*clauses, {"$nor": [shares_stats]}]})
        clauses += [shares_stats, {"reach_views": _range(bucket["min"], bucket["max"])}]
    query = {"$and": clauses}

    total = db.creators.count_documents(query)
    skip = (page - 1) * PAGE_SIZE
    if sort == "name":
        docs = list(db.creators.find(query, FIELDS).sort("name", 1).skip(skip).limit(PAGE_SIZE))
    else:
        # Creators who share stats, highest reach first; then everyone else by name, in an
        # order that says nothing about their reach.
        visible = {"$and": [query, shares_stats, {"reach_views": {"$ne": None}}]}
        n_visible = db.creators.count_documents(visible)
        docs = list(db.creators.find(visible, FIELDS).sort([("reach_views", -1), ("name", 1)]).skip(skip).limit(PAGE_SIZE))
        if len(docs) < PAGE_SIZE:
            rest = {"$and": [query, {"$nor": [{"$and": [shares_stats, {"reach_views": {"$ne": None}}]}]}]}
            docs += list(db.creators.find(rest, FIELDS).sort("name", 1).skip(max(0, skip - n_visible)).limit(PAGE_SIZE - len(docs)))

    stats_ids = {d["_id"] for d in db.creators.find({"$and": [{"_id": {"$in": [d["_id"] for d in docs]}}, shares_stats]}, {"_id": 1})}
    return {
        "results": [_card(d, d["_id"] in stats_ids) for d in docs],
        "total": total,
        "page": page,
        "pages": max(1, -(-total // PAGE_SIZE)),
        "hidden_by_reach": hidden,
        "options": options(),
    }


def _card(c: dict, stats: bool) -> dict:
    from .views import source_of

    return {
        "id": c["_id"],
        "name": c["name"],
        "handle": c.get("handle"),
        "avatar_hue": c.get("avatar_hue", 260),
        "is_reference": c.get("is_reference", False),
        "niche_label": NICHES[c["niche"]]["label"],
        "languages": [LANGS[lang]["label"] for lang in c.get("languages") or [] if lang in LANGS],
        "city": c.get("city"),
        "audience_stage": audience_stage(c.get("followers", 0))["label"],
        "shares_stats": stats,
        # Only with the stats scope; the follower band above is public.
        "followers": c.get("followers") if stats else None,
        "followers_source": source_of(c, "followers") if stats else None,
        "reach_views": c.get("reach_views") if stats else None,
        "reach_source": c.get("reach_source") if stats else None,
        "sample": c.get("source") == "synthetic",
    }
