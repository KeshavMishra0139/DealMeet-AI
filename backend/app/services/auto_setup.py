"""Setting a creator up from the account they signed in with, instead of a form.

Signing in with YouTube or Instagram is the creator agreeing to share that account's data,
so the profile is drafted from it: name and handle, niche and language (read from video
titles or captions by the language model, with script and keyword rules as the fallback),
formats, follower count and audience stage. What the account doesn't say (the city, income
goals) is left for the creator to add later, never guessed. If the platform can't be read,
the creator gets the usual form.
"""
from __future__ import annotations

import logging

from fastapi import HTTPException

from ..ai.regional import tag_captions
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from . import instagram as ig
from . import youtube_public as yt

log = logging.getLogger("jodidar.auto_setup")

DEFAULT_GOAL = 10_000  # the form's default monthly goal; changeable in Profile
TITLES = 8


def stage_for(followers: int | None) -> str:
    n = followers or 0
    if n <= 0:
        return "zero"
    if n < 1_000:
        return "under_1k"
    if n < 10_000:
        return "1k_10k"
    if n < 100_000:
        return "10k_100k"
    return "100k_plus"


def _read(texts: list[str]) -> tuple[str | None, str | None, bool]:
    """(niche, language, read_by_ai) from titles or captions."""
    texts = [t for t in texts if t and t.strip()][:TITLES]
    if not texts:
        return None, None, False
    tags = tag_captions(texts)
    s = tags.get("summary") or {}
    niche = s.get("niche") if s.get("niche") in NICHES else None
    lang = s.get("language") if s.get("language") in LANGS else None
    return niche, lang, tags.get("source") in ("ai", "cache")


def from_youtube(user: dict) -> dict | None:
    """A draft profile from the signed-in creator's own channel, or None when it can't be read."""
    channel_id = user.get("youtube_channel_id")
    if not channel_id:
        return None
    try:
        report = yt.channel_report(channel_id)
    except HTTPException as e:
        log.info("Auto setup: couldn't read channel %s (%s)", channel_id, e.detail)
        return None
    ch, videos = report["channel"], report["videos"]
    titles = [v["title"] for v in videos if v.get("title")]
    niche, lang, by_ai = _read(titles)
    review = []
    if not niche:
        # YouTube's own topic categories next; a middle-rate default is said so.
        niche = report["niche"]
        if report.get("niche_source") != "topics":
            review.append("niche")
    lang = lang or report.get("language")
    if not lang:
        review.append("languages")
    formats = [f for f in ("shorts", "long") if any(v["format"] == f for v in videos)] or ["long"]
    subs = ch.get("subscribers")
    return {
        "source": "youtube",
        "name": (ch.get("title") or user.get("name") or "Creator")[:60],
        "handle_hint": (ch.get("handle") or "").lstrip("@") or None,
        "niche": niche,
        "languages": [lang] if lang else ["en"],
        "formats": formats,
        "platforms": ["youtube"],
        "followers": subs,
        "audience_stage": stage_for(subs),
        "captions": titles[:TITLES],
        "read_by_ai": by_ai,
        "review": review + ["city"],
    }


def from_instagram(user: dict) -> dict | None:
    """A draft profile from the Instagram account the creator signed in with."""
    conn = get_db().connections.find_one({"user_id": user["_id"], "platform": "instagram", "creator_id": None})
    if not conn:
        return None
    try:
        token = ig._token(conn)
        profile = ig._graph("me", token, fields="username,name,account_type,followers_count,media_count")
        media = ig._graph("me/media", token, fields="caption,media_product_type", limit=24).get("data") or []
    except ig.IGError as e:
        log.info("Auto setup: couldn't read Instagram for %s (%s)", user["_id"], e)
        return None
    captions = [m.get("caption") or "" for m in media if m.get("caption")]
    niche, lang, by_ai = _read(captions)
    review = [] if niche else ["niche"]
    if not lang:
        review.append("languages")
    kinds = {(m.get("media_product_type") or "").upper() for m in media}
    formats = ["reels"] + (["carousel"] if "FEED" in kinds else [])
    followers = int(profile.get("followers_count") or 0)
    return {
        "source": "instagram",
        "name": (profile.get("name") or profile.get("username") or user.get("name") or "Creator")[:60],
        "handle_hint": profile.get("username"),
        "niche": niche or yt.FALLBACK_NICHE,  # a middle rate, flagged for review
        "languages": [lang] if lang else ["en"],
        "formats": formats,
        "platforms": ["instagram"],
        "followers": followers,
        "audience_stage": stage_for(followers),
        "captions": [c[:2200] for c in captions[:TITLES]],
        "read_by_ai": by_ai,
        "review": review + ["city"],
    }


def draft(user: dict) -> dict | None:
    """The best draft for this account: YouTube first if it signed in with both."""
    return from_youtube(user) or from_instagram(user)
