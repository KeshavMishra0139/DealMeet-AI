"""Search suggestions like YouTube's: the phrases people search for, as they type.

Uses the public autocomplete that YouTube's own search box uses (Google's suggest service,
`ds=yt`) for creator searches, and Google's general suggestions for brand searches. No API
key and no YouTube quota. Each prefix is cached for a day, so a busy search box asks once
per prefix. Any failure (slow, blocked, unexpected answer) returns nothing, and DealMeet's
own suggestions still show.
"""
from __future__ import annotations

import json
import logging
import time

import httpx

from ..db import get_db

log = logging.getLogger("jodidar.suggest")

URL = "https://suggestqueries.google.com/complete/search"
CACHE_SECONDS = 24 * 3600
MAX = 8


def phrases(q: str, kind: str = "creators") -> list[str]:
    q = q.strip().lower()
    if not q:
        return []
    key = f"{kind}:{q}"
    db = get_db()
    hit = db.suggest_cache.find_one({"_id": key})
    if hit and hit["at"] > time.time() - CACHE_SECONDS:
        return hit["items"]
    params = {"client": "firefox", "q": q, "hl": "en", "gl": "in"}
    if kind == "creators":
        params["ds"] = "yt"  # YouTube's own suggestions
    try:
        r = httpx.get(URL, params=params, timeout=2.5, headers={"User-Agent": "Mozilla/5.0 (DealMeet AI search)"})
        r.raise_for_status()
        try:
            data = json.loads(r.content.decode("utf-8"))
        except UnicodeDecodeError:
            data = json.loads(r.content.decode("latin-1"))
        items = [s for s in data[1] if isinstance(s, str)][:MAX]
    except (httpx.HTTPError, ValueError, IndexError, TypeError) as e:
        log.info("Web suggestions unavailable: %s", type(e).__name__)
        return []
    db.suggest_cache.replace_one({"_id": key}, {"_id": key, "items": items, "at": time.time()}, upsert=True)
    return items
