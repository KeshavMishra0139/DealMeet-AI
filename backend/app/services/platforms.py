"""One dashboard per connected platform, in that platform's own words.

A creator who connected YouTube sees videos, subscribers, Shorts and long videos; an
Instagram creator sees reels, followers, saves and shares. With both connected, each
platform has its own dashboard (tabs on Home), and numbers are never mixed across them.

Everything comes from what the platform's API returned and the app stored:
creators.channels.<platform> (the channel or account summary), posts (one row per
video or reel) and metric_snapshots (one row per day). Nothing here is estimated, and
"this week" is the real calendar (these are live numbers, not the demo's fixed date).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta

from ..seed.catalog import LANGS
from ..config import IST
from ..db import get_db
from ..engines import metrics
from ..engines.common import safe_median, short

RECENT_N = 6
LIST_N = 10
PACE_DAYS = 28
FORMAT_LABELS = {"shorts": "Shorts", "long": "Long videos"}
IN_SENTENCE = {"shorts": "Shorts", "long": "long videos"}


def connected(c: dict) -> list[str]:
    """Platforms with data on file; the one the profile's numbers come from first."""
    channels = c.get("channels") or {}
    have = [p for p in ("youtube", "instagram") if channels.get(p)]
    primary = metrics.platform(c)
    return sorted(have, key=lambda p: p != primary)


def _day(iso: str | None) -> str | None:
    try:
        return datetime.fromisoformat((iso or "").replace("Z", "+00:00")).astimezone(IST).date().isoformat()
    except ValueError:
        return None


def _posts(creator_id: str, platform: str) -> list[dict]:
    """The platform's posts with views, newest first, in one shape for both platforms."""
    q: dict = {"creator_id": creator_id, "platform": platform, "views": {"$ne": None}}
    if platform == "instagram":
        q["media_product_type"] = {"$in": ["REELS", "reels"]}  # views are read for reels only
    out = []
    for p in get_db().posts.find(q).sort("published_at", -1).limit(30):
        day = _day(p.get("published_at"))
        if not day:
            continue
        text = p.get("title") if platform == "youtube" else (p.get("caption") or "").split("\n")[0]
        out.append(
            {
                "id": p.get("post_id"),
                "date": day,
                "title": (text or "")[:90] or None,
                "views": int(p.get("views") or 0),
                "likes": p.get("likes"),
                "comments": p.get("comments"),
                "saves": p.get("saves") if platform == "instagram" else None,
                "shares": p.get("shares") if platform == "instagram" else None,
                "format": p.get("format") if platform == "youtube" else "reels",
                "permalink": p.get("permalink"),
            }
        )
    return out


def _per_1k(posts: list[dict], field: str) -> float | None:
    known = [p for p in posts if p.get(field) is not None]
    views = sum(p["views"] for p in known)
    return round(sum(p[field] for p in known) / views * 1000, 1) if known and views else None


def _change(creator_id: str, platform: str, field: str) -> dict | None:
    """The audience count now against about a week ago, from daily snapshots."""
    db = get_db()
    latest = db.metric_snapshots.find_one({"creator_id": creator_id, "platform": platform, field: {"$ne": None}}, sort=[("date", -1)])
    if not latest:
        return None
    week_ago = (date.fromisoformat(latest["date"]) - timedelta(days=7)).isoformat()
    before = db.metric_snapshots.find_one({"creator_id": creator_id, "platform": platform, field: {"$ne": None}, "date": {"$lte": week_ago}}, sort=[("date", -1)])
    if not before:
        return None
    return {"now": latest[field], "before": before[field], "since": before["date"]}


def _ratio_line(t: dict, med: float, audience: int | None) -> str | None:
    if not audience:
        return None
    r = med / audience
    if r >= 1.5:
        return f"Your recent {t['posts']} reach about {r:.1f}x your {t['audience']}: people beyond your {t['audience']} are watching."
    if r >= 0.67:
        return f"Your recent {t['posts']} reach about as many people as your {t['audience']}."
    return f"Your recent {t['posts']} reach about {round(r * 100)}% of your {t['audience']}."


def _language(c: dict, recent: list[dict]) -> str | None:
    """The main language of the creator's titles: the AI review's reading when there is one,
    else script and word rules (ai/regional.py)."""
    from ..ai import price_review

    reviewed = (price_review.current(c) or {}).get("language")
    return reviewed if reviewed in LANGS else price_review.detect_language([p.get("title") or "" for p in recent])


def dashboard(c: dict, platform: str) -> dict:
    """The dashboard for one platform: headline numbers, the recent posts against the
    audience, formats, a list of recent posts and plain-language insights."""
    t = metrics.TERMS[platform]
    ch = (c.get("channels") or {}).get(platform) or {}
    posts = _posts(c["_id"], platform)
    recent = posts[:RECENT_N]
    audience = ch.get("subscribers") if platform == "youtube" else ch.get("followers")
    med = safe_median([p["views"] for p in recent]) if recent else None
    today = datetime.now(IST).date()
    cutoff = (today - timedelta(days=PACE_DAYS)).isoformat()
    pace_posts = [p for p in posts if p["date"] >= cutoff]
    pace = round(len(pace_posts) / (PACE_DAYS / 7), 1)
    likes, comments = _per_1k(recent, "likes"), _per_1k(recent, "comments")

    kpis = [
        {"key": "audience", "label": t["audience"].capitalize(), "value": audience, "hidden": audience is None and platform == "youtube"},
        {"key": "median_views", "label": f"Median views, last {len(recent)} {t['posts']}", "value": round(med) if med is not None else None},
        {"key": "pace", "label": f"{t['posts'].capitalize()} a week, last 4 weeks", "value": pace},
    ]
    if platform == "youtube":
        kpis += [
            {"key": "total_views", "label": "Channel views, all time", "value": ch.get("total_views")},
            {"key": "post_count", "label": "Videos on the channel", "value": ch.get("video_count")},
            {"key": "likes_per_1k", "label": "Likes per 1,000 views", "value": likes},
            {"key": "comments_per_1k", "label": "Comments per 1,000 views", "value": comments},
        ]
    else:
        kpis += [
            {"key": "reach_28d", "label": "Accounts reached, 28 days", "value": ch.get("reach_28d")},
            {"key": "views_28d", "label": "Views, 28 days", "value": ch.get("views_28d")},
            {"key": "saves_shares_per_1k", "label": "Saves + shares per 1,000 views", "value": _saves_shares_per_1k(recent)},
            {"key": "likes_per_1k", "label": "Likes per 1,000 views", "value": likes},
        ]

    formats = []
    if platform == "youtube":
        for fmt, label in FORMAT_LABELS.items():
            of = [p["views"] for p in posts if p["format"] == fmt]
            if of:
                formats.append({"key": fmt, "label": label, "count": len(of), "median_views": round(safe_median(of))})

    insights = []
    if med is not None:
        line = _ratio_line(t, med, audience)
        if line:
            insights.append(line)
    if len(formats) == 2 and all(f["count"] >= 2 for f in formats):
        s, lg = formats
        hi_, lo_ = (s, lg) if s["median_views"] >= lg["median_views"] else (lg, s)
        if lo_["median_views"] and hi_["median_views"] / lo_["median_views"] >= 1.5:
            insights.append(f"Your {IN_SENTENCE[hi_['key']]} get about {hi_['median_views'] / lo_['median_views']:.1f}x the views of your {IN_SENTENCE[lo_['key']]} (median {short(hi_['median_views'])} against {short(lo_['median_views'])}).")
        else:
            insights.append(f"Your Shorts and long videos get similar views (median {short(s['median_views'])} and {short(lg['median_views'])}).")
    insights.append(
        f"You posted {len(pace_posts)} {t['posts'] if len(pace_posts) != 1 else t['post']} in the last 4 weeks ({pace} a week)."
        if pace_posts else f"No new {t['posts']} in the last 4 weeks."
    )
    if posts:
        best = max(recent, key=lambda p: p["views"])
        insights.append(f"Your best recent {t['post']}: “{best['title'] or 'Untitled'}” with {short(best['views'])} views.")
    if likes is not None and comments is not None:
        insights.append(f"{likes:g} likes and {comments:g} comments per 1,000 views on your recent {t['posts']}.")
    language = _language(c, recent)
    if language:
        insights.append(f"Your recent {t['post']} titles are mostly in {LANGS[language]['label']}.")
    if platform == "instagram":
        ss = _saves_shares_per_1k(recent)
        if ss is not None:
            insights.append(f"{ss:g} saves and shares per 1,000 views: what brands read as content worth keeping.")

    notes = []
    if platform == "youtube":
        if audience is None:
            notes.append("This channel hides its subscriber count. Views still count; subscribers don't set your price.")
        if not ch.get("ownership_verified"):
            notes.append("Public channel data. Connect YouTube Analytics on Connections to confirm the channel is yours and add watch time and audience.")
        notes.append("YouTube doesn't share saves or shares, so they aren't shown here.")
    else:
        notes += [n for n in ch.get("notes") or []]

    return {
        "platform": platform,
        "terms": t,
        "account": _account(platform, ch),
        "source": ch.get("source") or ("youtube_api" if platform == "youtube" else "instagram_api"),
        "fetched_at": ch.get("fetched_at"),
        "kpis": kpis,
        "chart": {"recent": [{"date": p["date"], "views": p["views"], "title": p["title"]} for p in reversed(recent)], "audience": audience},
        "formats": formats,
        "posts": posts[:LIST_N],
        "change": _change(c["_id"], platform, "subscribers" if platform == "youtube" else "followers"),
        "analytics": _analytics(ch) if platform == "youtube" else _ig_audience(ch),
        "insights": insights,
        "language": language,
        "notes": notes,
    }


def _saves_shares_per_1k(posts: list[dict]) -> float | None:
    known = [p for p in posts if p.get("saves") is not None and p.get("shares") is not None]
    views = sum(p["views"] for p in known)
    return round(sum(p["saves"] + p["shares"] for p in known) / views * 1000, 1) if known and views else None


def _account(platform: str, ch: dict) -> dict:
    if platform == "youtube":
        return {"name": ch.get("title"), "handle": ch.get("handle"), "picture": ch.get("thumbnail"), "verified": bool(ch.get("ownership_verified"))}
    return {"name": ch.get("username"), "handle": f"@{ch['username']}" if ch.get("username") else None, "picture": ch.get("picture"), "verified": True}


def _analytics(ch: dict) -> dict | None:
    """YouTube Analytics, when the creator connected it: 28-day watch time and audience."""
    a = ch.get("analytics")
    if not a:
        return None
    ages: dict[str, float] = {}
    women = 0.0
    for row in a.get("age_gender") or []:
        ages[row["age"]] = ages.get(row["age"], 0) + row["percent"]
        if row["gender"] == "female":
            women += row["percent"]
    top_age = max(ages.items(), key=lambda kv: kv[1]) if ages else None
    countries = a.get("countries") or []
    total = sum(x["views"] for x in countries) or 1
    return {
        "period_days": a.get("period_days"),
        "views": a.get("views"),
        "minutes_watched": a.get("minutes_watched"),
        "average_view_duration_s": a.get("average_view_duration_s"),
        "top_age": {"age": top_age[0], "percent": round(top_age[1])} if top_age else None,
        "women_percent": round(women) if ages else None,
        "top_countries": [{"country": x["country"], "share": round(x["views"] / total * 100)} for x in countries[:3]],
        "fetched_at": a.get("fetched_at"),
    }


def _ig_audience(ch: dict) -> dict | None:
    demo = ch.get("demographics") or {}
    age, city = demo.get("age") or {}, demo.get("city") or {}
    if not age:
        return None
    total = sum(age.values()) or 1
    top_age = max(age.items(), key=lambda kv: kv[1])
    c_total = sum(city.values()) or 1
    return {
        "top_age": {"age": top_age[0], "percent": round(top_age[1] / total * 100)},
        "top_cities": [{"city": k.split(",")[0], "share": round(v / c_total * 100)} for k, v in sorted(city.items(), key=lambda kv: -kv[1])[:3]],
    }


def overview(c: dict) -> dict:
    """Every connected platform's dashboard, the primary one first."""
    plats = connected(c)
    return {"primary": plats[0] if plats else None, "terms": metrics.terms(c), "platforms": [dashboard(c, p) for p in plats]}
