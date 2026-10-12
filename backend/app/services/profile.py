"""A creator's own profile: what's filled in, how ready it is for brands, and
self-reported numbers.

Profile completeness is a fixed checklist (10 items, 10 points each), each with one
suggested fix. Brand-readiness is a second checklist built only from connected
data; an item that needs a connected account says "connect to check" rather than
failing. Self-reported numbers are kept with their history, labelled "manual", and
never overwrite numbers that came from a connected account.
"""
from __future__ import annotations

import re
import time
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from ..config import now_iso
from ..db import get_db
from ..seed.catalog import NICHES

DISCLOSURE = re.compile(r"#(ad|sponsored|collab|paidpartnership)\b|paid partnership", re.I)

# (key, label, fix) in display order. Each is worth 10 points.
COMPLETENESS = [
    ("name", "Name", "Add the name brands will see on your profile."),
    ("bio", "Bio of 30 characters or more", "Write two lines on what you make and who watches it."),
    ("niche", "Main niche", "Pick the niche that fits most of your posts."),
    ("categories", "Content categories", "Add up to six topics you post about, like 'quick breakfasts' or 'budget phones'."),
    ("location", "City", "Add your city, so regional brands can find you."),
    ("languages", "Languages", "Add the languages you post in."),
    ("formats", "Formats", "Pick the formats you make: reels, Shorts, long videos, carousels."),
    ("platforms", "Platforms", "Say where you post: Instagram, YouTube or both."),
    ("preferences", "Collaboration preferences", "Say whether you take paid or barter deals and your minimum fee, so you only see offers that fit."),
    ("numbers", "Audience numbers", "Connect Instagram or YouTube, or type your followers and average views under Self-reported numbers."),
]


def _has(c: dict, key: str) -> bool:
    prefs = c.get("collab_prefs") or {}
    return {
        "name": bool((c.get("name") or "").strip()),
        "bio": len((c.get("bio") or "").strip()) >= 30,
        "niche": c.get("niche") in NICHES,
        "categories": bool(c.get("sub_niches")),
        "location": bool(c.get("city")),
        "languages": bool(c.get("languages")),
        "formats": bool(c.get("formats")),
        "platforms": bool(c.get("platforms")),
        "preferences": bool(prefs.get("accepts")) and prefs.get("min_fee") is not None,
        "numbers": connected_platforms(c) != [] or bool((c.get("manual") or {}).get("followers")),
    }[key]


def completeness(c: dict) -> dict:
    items = [{"key": k, "label": label, "done": _has(c, k), "fix": None if _has(c, k) else fix} for k, label, fix in COMPLETENESS]
    done = sum(1 for i in items if i["done"])
    return {"score": done * 10, "done": done, "total": len(items), "items": items, "method": "10 fixed items, 10 points each."}


def connected_platforms(c: dict) -> list[str]:
    """Platforms with data from an official connection (not sample data, not typed)."""
    db = get_db()
    out = []
    if db.connections.count_documents({"creator_id": c["_id"], "platform": "instagram", "status": "connected"}):
        out.append("instagram")
    yt = (c.get("channels") or {}).get("youtube") or {}
    if yt.get("analytics_connected"):
        out.append("youtube")
    return out


def _item(key: str, label: str, status: str, detail: str, source: str | None = None, weight: int = 1) -> dict:
    return {"key": key, "label": label, "status": status, "detail": detail, "source": source, "weight": weight}


def readiness(c: dict) -> dict:
    """Brand-readiness from connected data. Status: passed, failed, connect (connect to
    check) or not_applicable. The score counts passed items over the applicable ones,
    with 'connect to check' counting as not yet passed."""
    db = get_db()
    platforms = connected_platforms(c)
    source = {"instagram": "instagram_api", "youtube": "youtube_api"}.get(platforms[0]) if platforms else None
    items = []
    items.append(
        _item("professional", "Professional account connected", "passed" if platforms else "connect",
              f"Connected: {', '.join(p.capitalize() for p in platforms)}." if platforms else "Connect an Instagram Creator or Business account, or YouTube Analytics.", source)
    )
    bio_ok = len((c.get("bio") or "").strip()) >= 30
    items.append(_item("bio", "Bio filled in", "passed" if bio_ok else "failed", "Your bio is ready." if bio_ok else "Write a bio of 30 characters or more.", "manual"))

    posts = list(db.posts.find({"creator_id": c["_id"], "platform": {"$in": platforms}}, {"caption": 1, "title": 1, "description": 1, "published_at": 1, "post_id": 1, "permalink": 1})) if platforms else []
    if not platforms:
        for key, label in (("consistency", "Posting consistency"), ("focus", "Niche focus"), ("disclosure", "Disclosure on paid posts"), ("demographics", "Audience demographics available")):
            items.append(_item(key, label, "connect", "Connect to check: this needs your real posts and insights."))
    else:
        cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        recent = [p for p in posts if (p.get("published_at") or "").replace("+0000", "+00:00") >= cutoff]
        items.append(
            _item("consistency", "Posting consistency", "passed" if len(recent) >= 4 else "failed",
                  f"{len(recent)} posts in the last 30 days" + ("." if len(recent) >= 4 else ": brands look for at least one a week."), source)
        )
        post_tags = [{t.lower() for t in re.findall(r"#(\w+)", f"{p.get('caption') or ''} {p.get('title') or ''} {p.get('description') or ''}")} for p in posts]
        counts = Counter(t for tags in post_tags for t in tags)
        top = counts.most_common(1)[0][0] if counts else None
        share = round(sum(1 for tags in post_tags if top in tags) / len(posts) * 100) if top else 0
        items.append(
            _item("focus", "Niche focus", "passed" if share >= 40 else "failed",
                  f"{share}% of your recent posts share your top topic (#{top})." if top else "No recurring topic found in your recent captions.", source)
        )
        deal_links = {(d.get("proof_url") or "").rstrip("/") for d in db.deals.find({"creator_id": c["_id"], "proof_url": {"$ne": None}})}
        paid = [p for p in posts if (p.get("permalink") or "").rstrip("/") in deal_links or DISCLOSURE.search(p.get("caption") or "")]
        if not paid:
            items.append(_item("disclosure", "Disclosure on paid posts", "not_applicable", "No paid posts found yet.", source))
        else:
            ok = all(DISCLOSURE.search(p.get("caption") or "") for p in paid)
            items.append(_item("disclosure", "Disclosure on paid posts", "passed" if ok else "failed",
                               "Every paid post is labelled." if ok else "Add #ad or the paid-partnership label to every paid post.", source))
        ig = (c.get("channels") or {}).get("instagram") or {}
        yt = ((c.get("channels") or {}).get("youtube") or {}).get("analytics") or {}
        has_demo = bool(ig.get("demographics")) or bool(yt.get("age_gender"))
        items.append(
            _item("demographics", "Audience demographics available", "passed" if has_demo else "failed",
                  "Brands can see your audience's age, gender and location if you share it." if has_demo else
                  ("Instagram shares demographics from 100 followers." if ig and (ig.get("followers") or 0) < 100 else "Your connected account hasn't returned demographics yet."), source)
        )
    applicable = [i for i in items if i["status"] != "not_applicable"]
    passed = sum(1 for i in applicable if i["status"] == "passed")
    return {
        "score": round(passed / len(applicable) * 100) if applicable else 0,
        "passed": passed,
        "applicable": len(applicable),
        "to_connect": sum(1 for i in items if i["status"] == "connect"),
        "items": items,
        "method": "Passed items over applicable items. Items that need a connected account count as not passed yet and say 'connect to check'.",
    }


# ------------------------------------------------------------------ self-reported numbers
def add_manual_metrics(c: dict, platform: str, followers: int, avg_views: int | None, engagement_pct: float | None) -> dict:
    """Stores a self-reported reading with its history. It feeds the profile only where
    no connected account provides that number."""
    db = get_db()
    entry = {
        "_id": f"mm_{uuid.uuid4().hex[:10]}",
        "creator_id": c["_id"],
        "platform": platform,
        "followers": followers,
        "avg_views": avg_views,
        "engagement_pct": engagement_pct,
        "source": "manual",
        "at": now_iso(),
        "ts": time.time(),
    }
    db.manual_metrics.insert_one(entry)
    connected = platform in connected_platforms(c) or (platform == "instagram" and c.get("insights_source") == "instagram_api")
    applied = not connected
    if applied:
        prov = dict(c.get("provenance") or {})
        prov["followers"] = "manual"
        update = {"manual": {k: entry[k] for k in ("platform", "followers", "avg_views", "engagement_pct", "at")}, "followers": followers, "provenance": prov}
        db.creators.update_one({"_id": c["_id"]}, {"$set": update})
        from . import coach

        coach.on_new_data(c["_id"], "New self-reported numbers")
    return {"entry": {k: v for k, v in entry.items() if k not in ("_id", "ts")} | {"id": entry["_id"]}, "applied": applied,
            "note": None if applied else f"Saved. Your connected {platform.capitalize()} numbers stay in use: self-reported numbers never replace them."}


def manual_history(creator_id: str) -> list[dict]:
    rows = get_db().manual_metrics.find({"creator_id": creator_id}).sort("ts", -1).limit(20)
    return [{**{k: v for k, v in r.items() if k not in ("_id", "ts")}, "id": r["_id"]} for r in rows]
