"""YouTube Analytics for a creator's own channel, through their Google sign-in.

The browser asks Google for youtube.readonly and yt-analytics.readonly only when the
creator clicks "Connect YouTube Analytics" (never at ordinary sign-in), then sends
the access token here once. It is used immediately and never stored or logged:
Firebase gives no refresh token, so "Refresh" repeats the Google consent.

The token's channel must be the channel the creator linked by handle; that match
is also what marks the linked channel's ownership as verified.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta

import httpx
from fastapi import HTTPException

from ..config import IST
from ..db import get_db
from .youtube_public import SOURCE

log = logging.getLogger("jodidar.yt_analytics")

DATA_API = "https://www.googleapis.com/youtube/v3"
ANALYTICS_API = "https://youtubeanalytics.googleapis.com/v2/reports"
SCOPES = ["https://www.googleapis.com/auth/youtube.readonly", "https://www.googleapis.com/auth/yt-analytics.readonly"]
DAYS = 28
CONSENT_TEXT = (
    "We can see: your channel's views, watch time and audience age, gender and country. "
    "We can't: upload, comment, manage your channel or see your password. You can disconnect anytime."
)


def _get(url: str, token: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params=params, headers={"Authorization": f"Bearer {token}"}, timeout=15)
    except httpx.HTTPError as e:
        log.warning("YouTube Analytics call failed: %s", type(e).__name__)
        raise HTTPException(502, "Couldn't reach YouTube right now. Try again in a minute.") from None
    if r.status_code >= 400:
        reasons: set = set()
        try:
            reasons = {e.get("reason") for e in r.json()["error"].get("errors", [])}
        except (ValueError, KeyError, TypeError, AttributeError):
            pass
        if r.status_code == 401:
            raise HTTPException(409, "Google's sign-in expired before we could read your analytics. Click Connect again.")
        if reasons & {"quotaExceeded", "dailyLimitExceeded", "rateLimitExceeded", "userRateLimitExceeded"}:
            raise HTTPException(503, "YouTube's daily quota is used up. Try again tomorrow.")
        if r.status_code == 403:
            raise HTTPException(403, "YouTube Analytics access wasn't granted. Click Connect again and allow both YouTube permissions.")
        raise HTTPException(502, f"YouTube returned an error ({r.status_code}).")
    return r.json()


def _rows(report: dict) -> list[list]:
    return report.get("rows") or []


def connect(creator_id: str, token: str) -> dict:
    db = get_db()
    c = db.creators.find_one({"_id": creator_id}) or {}
    linked = (c.get("channels") or {}).get("youtube")
    if not linked:
        raise HTTPException(409, "Link your YouTube channel by its @handle first, then connect Analytics.")
    mine = _get(f"{DATA_API}/channels", token, {"part": "id,snippet", "mine": "true"}).get("items") or []
    if not mine:
        raise HTTPException(409, "This Google account doesn't have a YouTube channel.")
    if mine[0]["id"] != linked["channel_id"]:
        title = (mine[0].get("snippet") or {}).get("title") or mine[0]["id"]
        raise HTTPException(409, f"This Google account's channel ({title}) isn't the channel linked here ({linked.get('title')}). Sign in with the account that owns it.")
    end = datetime.now(IST).date()
    start = end - timedelta(days=DAYS)
    base = {"ids": "channel==MINE", "startDate": start.isoformat(), "endDate": end.isoformat()}
    totals = _rows(_get(ANALYTICS_API, token, {**base, "metrics": "views,estimatedMinutesWatched,averageViewDuration"}))
    age_gender = _rows(_get(ANALYTICS_API, token, {**base, "dimensions": "ageGroup,gender", "metrics": "viewerPercentage"}))
    countries = _rows(_get(ANALYTICS_API, token, {**base, "dimensions": "country", "metrics": "views", "sort": "-views", "maxResults": 10}))
    t = totals[0] if totals else [0, 0, 0]
    fetched = datetime.now(IST).isoformat(timespec="seconds")
    snapshot = {
        "period_days": DAYS,
        "start": start.isoformat(),
        "end": end.isoformat(),
        "views": int(t[0] or 0),
        "minutes_watched": int(t[1] or 0),
        "average_view_duration_s": int(t[2] or 0),
        "age_gender": [{"age": r[0].replace("age", ""), "gender": r[1], "percent": float(r[2])} for r in age_gender],
        "countries": [{"country": r[0], "views": int(r[1])} for r in countries],
        "source": SOURCE,
        "fetched_at": fetched,
    }
    db.creators.update_one(
        {"_id": creator_id},
        {"$set": {"channels.youtube.analytics": snapshot, "channels.youtube.analytics_connected": True, "channels.youtube.ownership_verified": True}},
    )
    day = end.isoformat()
    db.metric_snapshots.update_one(
        {"creator_id": creator_id, "platform": "youtube", "date": day},
        {"$set": {"creator_id": creator_id, "platform": "youtube", "date": day, "analytics": snapshot, "source": SOURCE, "fetched_at": fetched}},
        upsert=True,
    )
    return snapshot


def disconnect(creator_id: str) -> None:
    db = get_db()
    if not db.creators.count_documents({"_id": creator_id, "channels.youtube": {"$exists": True}}):
        return
    db.creators.update_one(
        {"_id": creator_id},
        {"$unset": {"channels.youtube.analytics": ""}, "$set": {"channels.youtube.analytics_connected": False, "channels.youtube.ownership_verified": False}},
    )
    db.metric_snapshots.update_many({"creator_id": creator_id, "platform": "youtube"}, {"$unset": {"analytics": ""}})
