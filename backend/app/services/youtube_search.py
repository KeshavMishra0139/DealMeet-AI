"""Creator search beyond DealMeet: public YouTube channels that match the search.

So a search works like a search engine from day one, not only over the creators who have
joined. Only what YouTube itself shows publicly comes back: the channel's name, handle,
picture, subscriber count (unless hidden), video count and a line of its description.
Never a price or an estimate: putting a number on someone who hasn't joined is what the old
public lookup did, and it was removed. A channel already linked to a DealMeet profile points
to that profile's public page instead.

Quota: search.list costs 100 units, so searches are cached for 12 hours (the same cache as
every YouTube call), capped per day (SEARCHES_PER_DAY, 80 searches = 8,000 of the default 10,000 units) and per IP. When a cap is
hit, or YouTube isn't configured, the search still returns DealMeet's own results and says
why YouTube's are missing.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException

from ..db import get_db
from ..seed.catalog import NICHES
from . import ratelimit
from . import youtube_public as yt

log = logging.getLogger("jodidar.youtube_search")

SEARCHES_PER_DAY = 80  # 8,000 of the default 10,000 daily units, the rest for linking channels
PER_IP_PER_HOUR = 30
RESULTS = 12


def _term(q: str, niches: list[str]) -> str:
    """What to ask YouTube: the words typed, steered by any niches picked."""
    words = q.strip().lstrip("@")
    topic = " ".join(NICHES[n]["label"] for n in niches if n in NICHES)
    return " ".join(x for x in (words, topic) if x) or ""


def _cards(ids: list[str]) -> list[dict]:
    if not ids:
        return []
    data, _ = yt._call("channels", {"part": "snippet,statistics", "id": ",".join(ids[:50]), "maxResults": 50})
    by_id = {c["id"]: c for c in data.get("items") or []}
    linked = {
        c["channels"]["youtube"]["channel_id"]: c["handle"]
        for c in get_db().creators.find(
            {"channels.youtube.channel_id": {"$in": ids}, "discoverable": {"$ne": False}, "public_page": {"$ne": False}},
            {"handle": 1, "channels.youtube.channel_id": 1},
        )
    }
    out = []
    for cid in ids:
        c = by_id.get(cid)
        if not c:
            continue
        sn, st = c.get("snippet") or {}, c.get("statistics") or {}
        handle = sn.get("customUrl")
        hidden = bool(st.get("hiddenSubscriberCount"))
        out.append({
            "channel_id": cid,
            "title": sn.get("title") or "YouTube channel",
            "handle": handle,
            "thumbnail": ((sn.get("thumbnails") or {}).get("default") or {}).get("url"),
            "description": (sn.get("description") or "").strip().split("\n")[0][:140],
            "subscribers": None if hidden else int(st.get("subscriberCount", 0)),
            "videos": int(st.get("videoCount", 0)),
            "country": sn.get("country"),
            "url": f"https://www.youtube.com/{handle}" if handle else f"https://www.youtube.com/channel/{cid}",
            "on_dealmeet": f"/c/{linked[cid]}" if cid in linked else None,
        })
    return out


def search(q: str, niches: list[str], ip: str | None, limit: int) -> dict:
    """{"items": [...], "note": str | None}. Never raises: YouTube trouble is a note."""
    term = _term(q, niches)
    if len(term) < 3:
        return {"items": [], "note": None}
    if not yt.configured():
        return {"items": [], "note": "YouTube results aren't set up on this server yet."}
    try:
        ids: list[str] = []
        # An exact @handle is one cheap call, and it's what the person meant.
        if q.strip().startswith("@") and " " not in q.strip():
            try:
                data, _ = yt._call("channels", yt.parse_query(q.strip()) | {"part": "id"})
                ids += [c["id"] for c in data.get("items") or []]
            except HTTPException as e:
                if e.status_code != 422:
                    raise
        params = {"part": "snippet", "type": "channel", "q": term, "maxResults": RESULTS, "regionCode": "IN"}
        if not yt.is_cached("search", params):
            # Budgets only count searches that would cost quota.
            if ip and not ratelimit.hit(f"ytsearch:ip:{ip}", PER_IP_PER_HOUR, 3600):
                return {"items": _cards(ids)[:limit], "note": "That's a lot of YouTube searches from here; showing DealMeet creators for now."}
            if not ratelimit.hit("ytsearch:day", SEARCHES_PER_DAY, 86_400):
                return {"items": _cards(ids)[:limit], "note": "YouTube results are paused for today; showing DealMeet creators."}
        data, _ = yt._call("search", params)
        for item in data.get("items") or []:
            cid = (item.get("id") or {}).get("channelId") or (item.get("snippet") or {}).get("channelId")
            if cid and cid not in ids:
                ids.append(cid)
        cards = _cards(ids)
        if not q.strip():
            # Browsing a niche: the biggest channels first.
            cards.sort(key=lambda c: -(c["subscribers"] or 0))
        return {"items": cards[:limit], "note": None}
    except HTTPException as e:
        log.info("YouTube search unavailable: %s", e.detail)
        return {"items": [], "note": e.detail}
