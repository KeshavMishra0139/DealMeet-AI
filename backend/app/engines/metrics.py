"""Per-creator metrics computed only from consented insights or typed data."""
from __future__ import annotations

from collections import defaultdict
from datetime import date, timedelta
from statistics import mean, pstdev

from ..config import today
from ..services.views import provenance_of
from .common import safe_median

RECENT_N = 6


def reels_sorted(c: dict) -> list[dict]:
    return sorted(c.get("reels") or [], key=lambda r: r["date"], reverse=True)


def recent(c: dict, n: int = RECENT_N) -> list[dict]:
    return reels_sorted(c)[:n]


def _simulated_in(c: dict, subset: list[dict], fields: tuple[str, ...]) -> list[str]:
    used = {id(r) for r in subset}
    reels = c.get("reels") or []
    return [
        f for f in fields
        if any(provenance_of(c, f"reels.{i}.{f}") == "simulated" for i, r in enumerate(reels) if id(r) in used)
    ]


def recent_simulated(c: dict, *fields: str) -> list[str]:
    """Which of these reel fields are simulated in the recent reels the numbers are built
    from (older reels don't count: Creator A's last six views are real, earlier ones aren't)."""
    return _simulated_in(c, recent(c), fields)


def window_reels(c: dict, days: int = 28) -> list[dict]:
    cutoff = today() - timedelta(days=days)
    return [r for r in c.get("reels") or [] if date.fromisoformat(r["date"]) >= cutoff]


def window_simulated(c: dict, *fields: str, days: int = 28) -> list[str]:
    """Like recent_simulated, for the reels inside the posting-pace window."""
    return _simulated_in(c, window_reels(c, days), fields)


def has_reels(c: dict) -> bool:
    return bool(c.get("reels"))


def median_views(c: dict) -> float:
    r = recent(c)
    if r:
        return safe_median(x["views"] for x in r)
    # No reels: the creator's self-reported average views, else a conservative estimate from followers.
    manual = (c.get("manual") or {}).get("avg_views")
    if manual:
        return float(manual)
    f = c.get("followers", 0)
    return f * (1.0 if f < 1_000 else 0.6 if f < 10_000 else 0.4)


def mean_views(c: dict) -> float:
    r = recent(c)
    return mean(x["views"] for x in r) if r else median_views(c)


def reach_ratio(c: dict) -> float:
    f = c.get("followers") or 0
    return mean_views(c) / f if f else 0.0


def _known(posts: list[dict], *fields: str) -> list[dict]:
    """Posts that carry these numbers. YouTube's public data has no saves or shares (None),
    and a channel can hide its likes: unknown is left out, never counted as zero."""
    return [x for x in posts if all(x.get(f) is not None for f in fields)]


def ss_known(c: dict) -> bool:
    """Whether saves and shares are known for the recent reels (not for YouTube videos)."""
    return bool(_known(recent(c), "saves", "shares"))


def ss_rate(c: dict) -> float:
    """(saves + shares) per view across recent reels that report them. Check ss_known
    first: 0.0 here can also mean "not reported"."""
    r = _known(recent(c), "saves", "shares")
    views = sum(x["views"] for x in r)
    return sum(x["saves"] + x["shares"] for x in r) / views if views else 0.0


def like_rate(c: dict) -> float:
    r = _known(recent(c), "likes")
    views = sum(x["views"] for x in r)
    return sum(x["likes"] for x in r) / views if views else 0.0


def posts_per_week(c: dict, days: int = 28) -> float:
    return len(window_reels(c, days)) / (days / 7)


def views_cv(c: dict) -> float:
    v = [x["views"] for x in recent(c)]
    if len(v) < 2 or mean(v) == 0:
        return 1.0
    return pstdev(v) / mean(v)


def by_topic(c: dict) -> list[dict]:
    """Performance per topic/format across all reels on file."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in c.get("reels") or []:
        groups[r.get("topic") or "Other"].append(r)
    out = []
    for topic, rs in groups.items():
        views = [r["views"] for r in rs]
        out.append(
            {
                "topic": topic,
                "count": len(rs),
                "median_views": safe_median(views),
                "views": sorted(views),
                # None when these posts don't report it (YouTube videos)
                "save_rate": _per_view(rs, "saves"),
                "share_rate": _per_view(rs, "shares"),
            }
        )
    return sorted(out, key=lambda t: t["median_views"], reverse=True)


def _per_view(posts: list[dict], field: str) -> float | None:
    known = _known(posts, field)
    if not known:
        return None
    return sum(r[field] for r in known) / (sum(r["views"] for r in known) or 1)


def fields_simulated(c: dict, *paths: str) -> list[str]:
    """Human labels for any of the given fields that are simulated."""
    labels = {
        "views": "views",
        "saves": "saves",
        "shares": "shares",
        "likes": "likes",
        "comments": "comments",
        "topic": "format labels",
        "audience": "audience demographics",
        "income_history": "income history",
        "past_deals": "past deals",
        "current_rate": "typical rate",
        "follower_history": "follower history",
        "comment_insights": "comment quality",
        "region": "region",
    }
    out = []
    for p in paths:
        if p.startswith("reels."):
            field = p.split(".")[-1]
            if any(provenance_of(c, f"reels.{i}.{field}") == "simulated" for i in range(len(c.get("reels") or []))):
                out.append(labels.get(field, field))
        elif provenance_of(c, p) == "simulated":
            out.append(labels.get(p, p))
    return out


def prov(c: dict, path: str) -> str:
    return provenance_of(c, path)


def income_by_source(c: dict, months: int = 6) -> dict[str, float]:
    hist = c.get("income_history") or []
    keep = sorted({h["month"] for h in hist})[-months:]
    out: dict[str, float] = defaultdict(float)
    for h in hist:
        if h["month"] in keep:
            out[h["source"]] += h["amount"]
    return dict(out)


def monthly_income(c: dict, months: int = 6) -> float:
    return sum(income_by_source(c, months).values()) / months


def brand_deals_per_month(c: dict) -> float:
    hist = [h for h in c.get("income_history") or [] if h["source"] == "brand"]
    return len(hist) / 6


def topic_name(topic: str) -> str:
    """'Quick breakfast' -> 'quick-breakfast' for use mid-sentence."""
    t = topic.lower()
    return t.replace("quick breakfast", "quick-breakfast")


def topic_plural(topic: str) -> str:
    """'Beat-sync fight edit' -> 'beat-sync fight edits'; 'Budgeting' -> 'budgeting reels';
    YouTube's 'Shorts' and 'Long videos' stay as they are."""
    t = topic_name(topic)
    if topic in YOUTUBE_TOPICS:
        return t
    if t.endswith(("edit", "transition", "tribute", "recap", "skit", "guide")):
        return t + "s"
    return t + " reels"


# Topics given to a linked channel's videos (services/youtube_public.py)
YOUTUBE_TOPICS = ("Shorts", "Long videos")


def post_word(topic: str | None = None) -> str:
    """'videos' for a linked channel's videos, else 'reels'."""
    return "videos" if topic in YOUTUBE_TOPICS else "reels"


def on_youtube(c: dict) -> bool:
    """Whether the posts on file are a linked YouTube channel's videos."""
    r = recent(c)
    return bool(r) and r[0].get("source") == "youtube_api"


def post_noun(c: dict) -> str:
    """'video' or 'reel', for copy about the creator's own posts."""
    return "video" if on_youtube(c) else "reel"


def audience_noun(c: dict) -> str:
    """'subscribers' or 'followers', for copy about the creator's follower count."""
    return "subscribers" if on_youtube(c) else "followers"
