"""Public YouTube channel data through the YouTube Data API v3, with an API key (no login).

Quota: only 1-unit calls are used (channels.list, playlistItems.list, videos.list).
search.list (100 units) is never called. Every response is cached in the database
for 12 hours, so repeat lookups and the public page cost no quota.

A channel linked by its handle is public data: it doesn't prove the creator owns
the channel. Ownership is confirmed only by connecting YouTube Analytics (OAuth).
"""
from __future__ import annotations

import logging
import re
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException

from ..config import IST, get_settings
from ..db import get_db
from ..engines.fair_price import public_estimate
from ..seed.catalog import NICHES

log = logging.getLogger("jodidar.youtube")

API = "https://www.googleapis.com/youtube/v3"
CACHE_SECONDS = 12 * 3600
MAX_VIDEOS = 30
NEW_DAYS = 3  # videos younger than this are still gathering views
SOURCE = "youtube_api"

HANDLE = re.compile(r"^@?([A-Za-z0-9._-]{3,30})$")
CHANNEL_ID = re.compile(r"^UC[A-Za-z0-9_-]{22}$")
URL = re.compile(r"(?:https?://)?(?:www\.|m\.)?youtube\.com/(?:(@[A-Za-z0-9._-]{3,30})|channel/(UC[A-Za-z0-9_-]{22}))", re.I)

# YouTube topic categories (Wikipedia links) -> JodiDar niche. A guess the creator can change.
TOPIC_NICHES = [
    ("video_game", "gaming"),
    ("anime", "anime_edits"),
    ("food", "food"),
    ("fashion", "fashion"),
    ("physical_fitness", "fitness"),
    ("health", "fitness"),
    ("technology", "tech"),
    ("humour", "comedy"),
    ("tourism", "travel"),
    ("knowledge", "education"),
    ("finance", "finance"),
    ("business", "finance"),
    ("beauty", "beauty"),
    ("parenting", "parenting"),
]
FALLBACK_NICHE = "travel"  # a middle rate per 1,000 views, said so in the reasons


def configured() -> bool:
    return bool(get_settings().youtube_api_key)


def parse_query(q: str) -> dict:
    """A handle (@name), a channel id (UC...) or a channel URL -> API filter."""
    q = (q or "").strip()
    m = URL.search(q)
    if m:
        q = m.group(1) or m.group(2)
    if CHANNEL_ID.match(q):
        return {"id": q}
    m = HANDLE.match(q)
    if not m:
        raise HTTPException(422, "Enter a YouTube handle like @yourchannel, or a channel link.")
    return {"forHandle": "@" + m.group(1)}


def _call(endpoint: str, params: dict) -> tuple[dict, float]:
    """One API call, served from the 12-hour cache when possible. The key never
    enters the cache key, the database or the logs."""
    db = get_db()
    key = f"{endpoint}?{urlencode(sorted(params.items()))}"
    hit = db.yt_cache.find_one({"_id": key})
    if hit and hit["fetched_at"] > time.time() - CACHE_SECONDS:
        return hit["data"], hit["fetched_at"]
    if not configured():
        raise HTTPException(503, "YouTube data isn't connected on this server (YOUTUBE_API_KEY).")
    try:
        r = httpx.get(f"{API}/{endpoint}", params={**params, "key": get_settings().youtube_api_key}, timeout=10)
    except httpx.HTTPError as e:
        log.warning("YouTube %s failed: %s", endpoint, type(e).__name__)
        raise HTTPException(502, "Couldn't reach YouTube right now. Try again in a minute.") from None
    if r.status_code >= 400:
        reasons = set()
        try:
            reasons = {e.get("reason") for e in r.json()["error"]["errors"]}
        except (ValueError, KeyError, TypeError):
            pass
        if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}:
            raise HTTPException(503, "YouTube's daily quota for JodiDar is used up. Cached channels still work; new lookups resume tomorrow.")
        if reasons & {"keyInvalid", "keyExpired", "accessNotConfigured", "forbidden", "ipRefererBlocked"}:
            raise HTTPException(503, "YouTube data isn't available: the server's API key isn't valid or the API isn't enabled.")
        if r.status_code == 404:
            return {"items": []}, time.time()
        raise HTTPException(502, f"YouTube returned an error ({r.status_code}). Try again later.")
    data = r.json()
    now = time.time()
    db.yt_cache.replace_one({"_id": key}, {"_id": key, "data": data, "fetched_at": now}, upsert=True)
    return data, now


def _seconds(iso: str | None) -> int:
    m = re.match(r"^P(?:(\d+)D)?T?(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?$", iso or "")
    if not m:
        return 0
    d, h, mi, s = (int(x or 0) for x in m.groups())
    return ((d * 24 + h) * 60 + mi) * 60 + s


def video_format(duration_s: int, title: str, description: str) -> str:
    """'shorts' or 'long'. The API has no Shorts flag: up to 60 seconds counts as a Short,
    and up to 3 minutes when the video is tagged #shorts."""
    text = f"{title} {description}".lower()
    if duration_s <= 60 or (duration_s <= 180 and "#shorts" in text):
        return "shorts"
    return "long"


def prices_for(videos: list[dict], niche: str) -> dict:
    """An estimate per format, Shorts and long videos priced separately: their views
    aren't comparable. Videos from the last 3 days aren't counted yet."""
    cutoff = (datetime.now(timezone.utc) - timedelta(days=NEW_DAYS)).isoformat()
    prices = {}
    for fmt in ("shorts", "long"):
        of_fmt = [v for v in videos if v["format"] == fmt]
        settled = [v["views"] for v in of_fmt if (v.get("published_at") or "") < cutoff]
        prices[fmt] = public_estimate(settled, niche, fmt, newest_excluded=len(of_fmt) - len(settled))
    return prices


def guess_niche(topics: list[str]) -> str | None:
    t = " ".join(topics).lower()
    return next((n for key, n in TOPIC_NICHES if key in t), None)


def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST).isoformat(timespec="seconds")


def channel_report(query: str, niche: str | None = None) -> dict:
    """Live channel numbers, the last 30 videos and a price per format (estimate)."""
    data, fetched = _call("channels", {"part": "snippet,statistics,topicDetails,contentDetails", **parse_query(query)})
    items = data.get("items") or []
    if not items:
        raise HTTPException(404, "No YouTube channel found for that handle. Check the spelling, including the @.")
    ch = items[0]
    sn, st = ch.get("snippet") or {}, ch.get("statistics") or {}
    topics = (ch.get("topicDetails") or {}).get("topicCategories") or []
    uploads = ((ch.get("contentDetails") or {}).get("relatedPlaylists") or {}).get("uploads")
    videos: list[dict] = []
    if uploads:
        pl, _ = _call("playlistItems", {"part": "contentDetails", "playlistId": uploads, "maxResults": MAX_VIDEOS})
        ids = [i["contentDetails"]["videoId"] for i in pl.get("items") or [] if (i.get("contentDetails") or {}).get("videoId")]
        if ids:
            vd, _ = _call("videos", {"part": "snippet,statistics,contentDetails", "id": ",".join(ids)})
            for v in vd.get("items") or []:
                vs, vstat = v.get("snippet") or {}, v.get("statistics") or {}
                dur = _seconds((v.get("contentDetails") or {}).get("duration"))
                videos.append(
                    {
                        "post_id": v["id"],
                        "title": vs.get("title", ""),
                        "description": (vs.get("description") or "")[:2000],
                        "published_at": vs.get("publishedAt"),
                        "views": int(vstat.get("viewCount", 0)),
                        "likes": int(vstat["likeCount"]) if "likeCount" in vstat else None,
                        "comments": int(vstat["commentCount"]) if "commentCount" in vstat else None,
                        "duration_s": dur,
                        "format": video_format(dur, vs.get("title", ""), vs.get("description") or ""),
                        "permalink": f"https://www.youtube.com/watch?v={v['id']}",
                    }
                )
    videos.sort(key=lambda v: v["published_at"] or "", reverse=True)
    guessed = guess_niche(topics)
    use = niche if niche in NICHES else guessed or FALLBACK_NICHE
    prices = prices_for(videos, use)
    hidden = bool(st.get("hiddenSubscriberCount"))
    notes = []
    if hidden:
        notes.append("This channel hides its subscriber count. That's fine: the price uses views, not subscribers.")
    if niche not in NICHES and not guessed:
        notes.append(f"We couldn't tell the niche from the channel's topics, so it's priced at a middle rate ({NICHES[use]['label']}). Pick your niche to change it.")
    if not videos:
        notes.append("No public videos found on this channel.")
    return {
        "channel": {
            "id": ch["id"],
            "title": sn.get("title"),
            "handle": sn.get("customUrl"),
            "thumbnail": ((sn.get("thumbnails") or {}).get("default") or {}).get("url"),
            "country": sn.get("country"),
            "subscribers": None if hidden else int(st.get("subscriberCount", 0)),
            "subscribers_hidden": hidden,
            "total_views": int(st.get("viewCount", 0)),
            "video_count": int(st.get("videoCount", 0)),
            "topics": [t.rsplit("/", 1)[-1].replace("_", " ") for t in topics],
        },
        "videos": videos,
        "niche": use,
        "niche_label": NICHES[use]["label"],
        "niche_guessed": niche not in NICHES,
        "prices": prices,
        "notes": notes,
        "source": SOURCE,
        "fetched_at": _iso(fetched),
    }


def public_view(report: dict) -> dict:
    """What the public page shows: no video descriptions, last 12 videos."""
    out = {k: v for k, v in report.items() if k != "videos"}
    out["videos"] = [{k: v[k] for k in ("post_id", "title", "published_at", "views", "format", "permalink")} for v in report["videos"][:12]]
    return out


def save_for_creator(creator_id: str, report: dict) -> dict:
    """Store a linked channel under creators.channels.youtube (creators.platforms is the
    self-reported list of platforms the creator uses): the summary, one row per video and a daily snapshot."""
    db = get_db()
    ch = report["channel"]
    fetched = report["fetched_at"]
    owner = db.creators.find_one({"channels.youtube.channel_id": ch["id"], "_id": {"$ne": creator_id}}, {"_id": 1})
    if owner:
        raise HTTPException(409, "That channel is already linked to another JodiDar profile.")
    summary = {
        "channel_id": ch["id"],
        "handle": ch["handle"],
        "title": ch["title"],
        "thumbnail": ch["thumbnail"],
        "subscribers": ch["subscribers"],
        "subscribers_hidden": ch["subscribers_hidden"],
        "total_views": ch["total_views"],
        "video_count": ch["video_count"],
        "ownership_verified": False,  # public data; YouTube Analytics (OAuth) confirms ownership
        "source": SOURCE,
        "fetched_at": fetched,
    }
    prev = (db.creators.find_one({"_id": creator_id}, {"channels": 1}) or {}).get("channels", {}).get("youtube") or {}
    if prev.get("channel_id") == ch["id"]:
        # A refresh keeps what YouTube Analytics confirmed for this same channel.
        summary["ownership_verified"] = bool(prev.get("ownership_verified"))
        for k in ("analytics", "analytics_connected"):
            if k in prev:
                summary[k] = prev[k]
    db.creators.update_one({"_id": creator_id}, {"$set": {"channels.youtube": summary}})
    for v in report["videos"]:
        db.posts.update_one(
            {"creator_id": creator_id, "platform": "youtube", "post_id": v["post_id"]},
            {"$set": {**v, "creator_id": creator_id, "platform": "youtube", "source": SOURCE, "fetched_at": fetched}},
            upsert=True,
        )
    day = datetime.now(IST).date().isoformat()
    medians = {f"median_views_{k}": (p.get("median_views") if p.get("enough_data") else None) for k, p in report["prices"].items()}
    db.metric_snapshots.update_one(
        {"creator_id": creator_id, "platform": "youtube", "date": day},
        {
            "$set": {
                "creator_id": creator_id,
                "platform": "youtube",
                "date": day,
                "subscribers": ch["subscribers"],
                "total_views": ch["total_views"],
                "video_count": ch["video_count"],
                **medians,
                "source": SOURCE,
                "fetched_at": fetched,
            }
        },
        upsert=True,
    )
    return summary


def unlink(creator_id: str) -> None:
    db = get_db()
    db.creators.update_one({"_id": creator_id}, {"$unset": {"channels.youtube": ""}})
    db.posts.delete_many({"creator_id": creator_id, "platform": "youtube"})
    db.metric_snapshots.delete_many({"creator_id": creator_id, "platform": "youtube"})


def status(creator: dict) -> dict:
    """Connection status for the Connections screen and brand-readiness."""
    yt = (creator.get("channels") or {}).get("youtube")
    if yt and yt.get("analytics_connected"):
        return {"platform": "youtube", "label": "YouTube", "status": "connected", "detail": f"{yt.get('title')}: public data and YouTube Analytics.", "source": SOURCE, "fetched_at": yt.get("fetched_at")}
    if yt:
        return {
            "platform": "youtube",
            "label": "YouTube",
            "status": "linked",
            "detail": f"{yt.get('title')}: public channel data. Connect YouTube Analytics to confirm it's yours and add audience data.",
            "source": SOURCE,
            "fetched_at": yt.get("fetched_at"),
        }
    if not configured():
        return {"platform": "youtube", "label": "YouTube", "status": "unavailable", "detail": "YouTube data isn't set up on this server yet."}
    return {"platform": "youtube", "label": "YouTube", "status": "not_connected", "detail": "Link your channel by its @handle to use your real views."}
