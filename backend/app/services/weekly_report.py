"""A creator's week in numbers, aggregated in MongoDB from records the app already keeps.

The week is the 7 days ending today (config.today(): the demo's date in demo mode),
compared with the 7 days before it. Nothing is estimated:

- profile_views: brands opening the creator's profile (consent_audit "viewed" events,
  written by services/consent.log_view), and how many different brands.
- offers: deals offered to the creator (deals.created_at), with their total value.
- paid: deals that reached "paid" (their timeline), with the amount; says when the
  payouts were simulated (demo mode, no payout partner).
- reach: views on reels posted in each week, and how many reels. None when the creator
  has no reels at all.
- followers: the change between platform snapshots (metric_snapshots, written by each
  Instagram or YouTube sync), only when there's a snapshot in both weeks.

Each block carries `source`: "synthetic" when any record behind it is seeded sample data,
the data source for reach and followers, otherwise "dealmeet" (the app's own records).
"""
from __future__ import annotations

from datetime import timedelta

from ..config import today
from ..db import get_db
from .views import source_of

SNAPSHOT_FIELD = {"instagram": "followers", "youtube": "subscribers"}


def _bounds() -> dict:
    t = today()
    return {
        "start": (t - timedelta(days=6)).isoformat(),  # this week, inclusive
        "prev_start": (t - timedelta(days=13)).isoformat(),
        "end": (t + timedelta(days=1)).isoformat(),  # exclusive; ISO timestamps compare as text
        "today": t.isoformat(),
    }


def _week(field: str, start: str) -> dict:
    """"this" or "last" for a document already limited to the two weeks."""
    return {"$cond": [{"$gte": [field, start]}, "this", "last"]}


def _by_week(rows: list[dict]) -> dict:
    out = {"this": {}, "last": {}}
    for r in rows:
        out[r["_id"]] = r
    return out


def _source(sample_count: int) -> str:
    return "synthetic" if sample_count else "dealmeet"


def build(creator_id: str) -> dict:
    db = get_db()
    b = _bounds()
    window = {"$gte": b["prev_start"], "$lt": b["end"]}
    is_sample = {"$cond": [{"$eq": ["$source", "synthetic"]}, 1, 0]}

    views = _by_week(list(db.consent_audit.aggregate([
        {"$match": {"creator_id": creator_id, "action": "viewed", "at": window}},
        {"$group": {"_id": _week("$at", b["start"]), "n": {"$sum": 1}, "brands": {"$addToSet": "$lister_id"}, "sample": {"$sum": is_sample}}},
    ])))
    offers = _by_week(list(db.deals.aggregate([
        {"$match": {"creator_id": creator_id, "created_at": window}},
        {"$group": {"_id": _week("$created_at", b["start"]), "n": {"$sum": 1}, "value": {"$sum": "$amount"}, "sample": {"$sum": is_sample}}},
    ])))
    paid = _by_week(list(db.deals.aggregate([
        {"$match": {"creator_id": creator_id, "timeline.stage": "paid"}},
        {"$unwind": "$timeline"},
        {"$match": {"timeline.stage": "paid", "timeline.at": window}},
        {"$group": {
            "_id": _week("$timeline.at", b["start"]),
            "n": {"$sum": 1},
            "amount": {"$sum": "$amount"},
            "simulated": {"$sum": {"$cond": [{"$eq": ["$payout.status", "simulated"]}, 1, 0]}},
            "sample": {"$sum": is_sample},
        }},
    ])))
    reels = _by_week(list(db.creators.aggregate([
        {"$match": {"_id": creator_id}},
        {"$unwind": "$reels"},
        {"$match": {"reels.date": window}},
        {"$group": {"_id": _week("$reels.date", b["start"]), "n": {"$sum": 1}, "views": {"$sum": "$reels.views"}}},
    ])))
    creator = db.creators.find_one({"_id": creator_id}, {"reels": {"$slice": 1}, "provenance": 1, "provenance_default": 1, "insights_source": 1}) or {}
    has_reels = bool(creator.get("reels"))

    report = {
        "week": {"start": b["start"], "end": b["today"], "previous_start": b["prev_start"]},
        "profile_views": {
            "this": views["this"].get("n", 0),
            "last": views["last"].get("n", 0),
            "brands": len(views["this"].get("brands", [])),
            "source": _source(views["this"].get("sample", 0) + views["last"].get("sample", 0)),
        },
        "offers": {
            "this": offers["this"].get("n", 0),
            "last": offers["last"].get("n", 0),
            "value": offers["this"].get("value", 0),
            "last_value": offers["last"].get("value", 0),
            "source": _source(offers["this"].get("sample", 0) + offers["last"].get("sample", 0)),
        },
        "paid": {
            "this": paid["this"].get("amount", 0),
            "last": paid["last"].get("amount", 0),
            "deals": paid["this"].get("n", 0),
            "simulated": bool(paid["this"].get("simulated", 0) or paid["last"].get("simulated", 0)),
            "source": _source(paid["this"].get("sample", 0) + paid["last"].get("sample", 0)),
        },
        "reach": {
            "this": reels["this"].get("views", 0),
            "last": reels["last"].get("views", 0),
            "reels": reels["this"].get("n", 0),
            "last_reels": reels["last"].get("n", 0),
            "source": source_of(creator, "reels.0.views"),
        } if has_reels else None,
        "followers": _followers(creator_id, b),
    }
    report["quiet"] = not any(
        (report["profile_views"]["this"], report["offers"]["this"], report["paid"]["this"], (report["reach"] or {}).get("reels"))
    )
    return report


def _followers(creator_id: str, b: dict) -> list[dict]:
    """Follower (or subscriber) change per connected platform, from its daily snapshots."""
    db = get_db()
    out = []
    for platform, field in SNAPSHOT_FIELD.items():
        rows = list(db.metric_snapshots.aggregate([
            {"$match": {"creator_id": creator_id, "platform": platform, "date": {"$gte": b["prev_start"], "$lt": b["end"]}, field: {"$ne": None}}},
            {"$sort": {"date": 1}},
            {"$group": {"_id": _week("$date", b["start"]), "value": {"$last": f"${field}"}, "source": {"$last": "$source"}}},
        ]))
        weeks = _by_week(rows)
        if "value" in weeks["this"] and "value" in weeks["last"]:
            out.append({"platform": platform, "now": weeks["this"]["value"], "before": weeks["last"]["value"], "source": weeks["this"].get("source")})
    return out
