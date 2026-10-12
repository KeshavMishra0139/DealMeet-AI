"""Instagram through the official Instagram API with Instagram Login (Business Login).

- OAuth with read-only scopes only: instagram_business_basic and
  instagram_business_manage_insights. No passwords, no scraping, no posting.
- The OAuth `state` is random, HMAC-signed, valid for 10 minutes and single-use.
  A "connect" state is tied to the signed-in account that started the connection;
  a "signin" state ("Continue with Instagram" on the sign-in page) has no account yet.
- One Instagram professional account is the sign-in identity of at most one DealMeet
  account (users.instagram_uid), whether it was connected or used to sign in.
- The long-lived token (about 60 days) is encrypted at rest (Fernet, TOKEN_ENC_KEY),
  never logged and never sent to the browser. A daily job refreshes tokens older
  than 24 hours that expire within 10 days.
- Sync reads the profile, recent media (with per-reel insights for the latest
  reels), account reach and views, and audience demographics. Everything stored is
  marked source "instagram_api" with fetched_at. Disconnecting deletes the token
  and all of it.
- Connected reels replace the profile's sample reels, so the fair price runs on the
  creator's real views, saves and shares. The price stays an estimate.
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import re
import secrets
import time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode

import httpx
from fastapi import HTTPException
from pymongo import ReturnDocument

from ..config import IST, get_settings, now_iso
from ..db import get_db
from . import crypto

log = logging.getLogger("jodidar.instagram")

AUTH_URL = "https://www.instagram.com/oauth/authorize"
TOKEN_URL = "https://api.instagram.com/oauth/access_token"
GRAPH = "https://graph.instagram.com"
SCOPES = ["instagram_business_basic", "instagram_business_manage_insights"]
SOURCE = "instagram_api"
STATE_TTL = 600
MEDIA_LIMIT = 50
REEL_INSIGHTS = 12  # per-reel insights for the latest reels (one call each)
MIN_DEMOGRAPHICS_FOLLOWERS = 100
REFRESH_AFTER = 24 * 3600
REFRESH_WITHIN = 10 * 86400
SHORTCODE = re.compile(r"instagram\.com/(?:reel|p|tv)/([\w-]+)")

CONSENT_TEXT = (
    "We can see: your profile, posts, reach and audience age/gender/city. "
    "We can't: post, read your DMs or see your password. You can disconnect anytime."
)


class IGError(Exception):
    """An Instagram API problem, with a message safe to show (never a token)."""

    def __init__(self, kind: str, message: str):
        super().__init__(message)
        self.kind = kind
        self.message = message


def configured() -> bool:
    s = get_settings()
    return bool(s.ig_app_id and s.ig_app_secret and s.ig_redirect_uri and crypto.configured())


def _version() -> str:
    return get_settings().ig_graph_version


# ------------------------------------------------------------------ OAuth state
# Sign-in nonces start with this marker ("~" is outside token_urlsafe's alphabet), so a
# callback with a broken state still knows whether to send the browser back to the
# sign-in page or to Connections. The stored record's purpose is what's trusted.
SIGNIN_MARK = "si~"


def _state_key() -> bytes:
    s = get_settings()
    return hashlib.sha256(f"{s.token_enc_key}|{s.ig_app_secret}|ig-state".encode()).digest()


def _sign(nonce: str, user_id: str) -> str:
    return hmac.new(_state_key(), f"{nonce}.{user_id}".encode(), hashlib.sha256).hexdigest()[:32]


def new_state(user: dict | None, creator_id: str | None, purpose: str = "connect", next_path: str | None = None, binding: str | None = None) -> str:
    """A state for one Instagram login. "connect": a signed-in creator links Instagram.
    "signin": "Continue with Instagram" before anyone is signed in (no user yet); `binding`
    is the hash of a cookie only the browser that started it holds."""
    if purpose not in ("connect", "signin"):
        raise ValueError(purpose)
    nonce = (SIGNIN_MARK if purpose == "signin" else "") + secrets.token_urlsafe(24)
    user_id = user["_id"] if user else None
    get_db().oauth_states.insert_one(
        {
            "_id": nonce,
            "platform": "instagram",
            "purpose": purpose,
            "user_id": user_id,
            "creator_id": creator_id,
            "next": next_path,
            "binding": binding,
            "expires": time.time() + STATE_TTL,
            "used": False,
        }
    )
    return f"{nonce}.{_sign(nonce, user_id or '')}"


def state_purpose(state: str | None) -> str:
    """Which flow a state claims to be, for choosing where to send the browser back."""
    return "signin" if (state or "").startswith(SIGNIN_MARK) else "connect"


def consume_state(state: str, session_user: dict | None, purpose: str = "connect") -> dict:
    """The state's record, once. Refuses a forged, expired, reused or someone else's state,
    and a state started for the other flow."""
    what, where = ("sign-in", "the sign-in page") if purpose == "signin" else ("connection", "Connections")
    nonce, _, sig = (state or "").partition(".")
    db = get_db()
    doc = db.oauth_states.find_one({"_id": nonce, "platform": "instagram"}) if nonce else None
    if not doc or doc.get("purpose", "connect") != purpose or not hmac.compare_digest(_sign(nonce, doc.get("user_id") or ""), sig):
        raise HTTPException(400, f"That Instagram {what} link isn't valid. Start again from {where}.")
    if doc["expires"] < time.time():
        raise HTTPException(400, f"That Instagram {what} took too long. Start again from {where}.")
    if purpose == "connect" and session_user and session_user["_id"] != doc["user_id"]:
        raise HTTPException(403, "This Instagram connection was started by another account.")
    used = db.oauth_states.find_one_and_update({"_id": nonce, "used": False}, {"$set": {"used": True}}, return_document=ReturnDocument.AFTER)
    if not used:
        raise HTTPException(400, f"That Instagram {what} link was already used. Start again from {where}.")
    return doc


def authorize_url(state: str) -> str:
    s = get_settings()
    q = {"client_id": s.ig_app_id, "redirect_uri": s.ig_redirect_uri, "response_type": "code", "scope": ",".join(SCOPES), "state": state}
    return f"{AUTH_URL}?{urlencode(q)}"


# ------------------------------------------------------------------ HTTP
def _error(r: httpx.Response) -> IGError:
    try:
        err = r.json().get("error") or {}
    except ValueError:
        err = {}
    code = err.get("code")
    if code == 190 or r.status_code == 401:
        return IGError("expired", "Instagram access expired or was revoked. Reconnect Instagram.")
    if code in (4, 17, 32, 613) or r.status_code == 429:
        return IGError("rate_limit", "Instagram is limiting requests right now. Try again in an hour.")
    if code in (10, 200, 3):
        return IGError("permission", "Instagram didn't grant that permission. Reconnect and allow insights.")
    return IGError("api", f"Instagram returned an error ({r.status_code}).")


def _get(url: str, params: dict) -> dict:
    try:
        r = httpx.get(url, params=params, timeout=15)
    except httpx.HTTPError as e:
        log.warning("Instagram call failed: %s", type(e).__name__)  # never the URL: it carries the token
        raise IGError("network", "Couldn't reach Instagram right now. Try again in a minute.") from None
    if r.status_code >= 400:
        raise _error(r)
    return r.json()


def _graph(path: str, token: str, **params) -> dict:
    return _get(f"{GRAPH}/{_version()}/{path}", {**params, "access_token": token})


# ------------------------------------------------------------------ tokens
def exchange_code(code: str) -> dict:
    """Code -> short-lived token -> long-lived token (about 60 days)."""
    s = get_settings()
    try:
        r = httpx.post(
            TOKEN_URL,
            data={"client_id": s.ig_app_id, "client_secret": s.ig_app_secret, "grant_type": "authorization_code", "redirect_uri": s.ig_redirect_uri, "code": code},
            timeout=15,
        )
    except httpx.HTTPError:
        raise IGError("network", "Couldn't reach Instagram right now. Try again in a minute.") from None
    if r.status_code >= 400:
        raise IGError("api", "Instagram didn't accept the sign-in. Start again from Connections.")
    body = r.json()
    entry = (body.get("data") or [body])[0]
    short, ig_user_id = entry.get("access_token"), str(entry.get("user_id") or "")
    if not short:
        raise IGError("api", "Instagram didn't return an access token.")
    perms = entry.get("permissions") or []
    scopes = perms.split(",") if isinstance(perms, str) else list(perms)
    long = _get(f"{GRAPH}/access_token", {"grant_type": "ig_exchange_token", "client_secret": s.ig_app_secret, "access_token": short})
    if not long.get("access_token"):
        raise IGError("api", "Instagram didn't return a long-lived token.")
    return {
        "token": long["access_token"],
        "ig_user_id": ig_user_id,
        "scopes": scopes or SCOPES,
        "expires_at": time.time() + int(long.get("expires_in") or 60 * 86400),
    }


def identity(token: str) -> dict:
    """The professional account a token belongs to. Its `user_id` is the stable id that
    sync stores, so it's what sign-in matches on."""
    me = _graph("me", token, fields="user_id,username,account_type")
    ig_id = str(me.get("user_id") or me.get("id") or "")
    if not ig_id:
        raise IGError("api", "Instagram didn't say which account signed in.")
    return {"ig_user_id": ig_id, "username": me.get("username"), "account_type": me.get("account_type")}


def account_for(ig_user_id: str) -> dict | None:
    """The DealMeet account this Instagram account signs in to, if any. Accounts that
    connected Instagram before sign-in existed are found through their connection."""
    db = get_db()
    user = db.users.find_one({"instagram_uid": ig_user_id})
    if user:
        return user
    conn = db.connections.find_one({"platform": "instagram", "ig_user_id": ig_user_id}, sort=[("connected_at", -1)])
    return db.users.find_one({"_id": conn["user_id"]}) if conn else None


def claim_identity(user: dict, ig_user_id: str) -> None:
    """Makes this Instagram account `user`'s sign-in identity. One Instagram account signs
    in to one DealMeet account, so a second account can't connect it."""
    from pymongo.errors import DuplicateKeyError

    db = get_db()
    if db.users.count_documents({"instagram_uid": ig_user_id, "_id": {"$ne": user["_id"]}}):
        raise IGError("taken", "This Instagram account is already linked to another DealMeet account. Sign in to that account, or disconnect Instagram there first.")
    try:
        db.users.update_one({"_id": user["_id"]}, {"$set": {"instagram_uid": ig_user_id}})
    except DuplicateKeyError:  # claimed by another account a moment ago
        raise IGError("taken", "This Instagram account is already linked to another DealMeet account.") from None
    user["instagram_uid"] = ig_user_id


def save_connection(user: dict, creator_id: str | None, grant: dict) -> dict:
    """Stores the encrypted token. `creator_id` is None for a creator who signed in with
    Instagram before onboarding; onboarding attaches the connection to the new profile."""
    db = get_db()
    now = time.time()
    doc = {
        "user_id": user["_id"],
        "creator_id": creator_id,
        "platform": "instagram",
        "ig_user_id": grant["ig_user_id"],
        "token_enc": crypto.encrypt(grant["token"]),
        "scopes": grant["scopes"],
        "expires_at": grant["expires_at"],
        "connected_at": now,
        "refreshed_at": now,
        "status": "connected",
        "last_error": None,
    }
    db.connections.update_one({"user_id": user["_id"], "platform": "instagram"}, {"$set": doc}, upsert=True)
    return db.connections.find_one({"user_id": user["_id"], "platform": "instagram"})


def _token(conn: dict) -> str:
    token = crypto.decrypt(conn.get("token_enc") or "")
    if not token:
        raise IGError("expired", "The saved Instagram access can't be read anymore. Reconnect Instagram.")
    return token


def refresh_due(now: float | None = None) -> int:
    """Refresh long-lived tokens older than 24 hours that expire within 10 days."""
    now = now or time.time()
    db = get_db()
    n = 0
    for conn in db.connections.find(
        {"platform": "instagram", "status": "connected", "refreshed_at": {"$lt": now - REFRESH_AFTER}, "expires_at": {"$lt": now + REFRESH_WITHIN}}
    ):
        try:
            r = _get(f"{GRAPH}/refresh_access_token", {"grant_type": "ig_refresh_token", "access_token": _token(conn)})
            db.connections.update_one(
                {"_id": conn["_id"]},
                {"$set": {"token_enc": crypto.encrypt(r["access_token"]), "expires_at": now + int(r.get("expires_in") or 60 * 86400), "refreshed_at": now, "last_error": None}},
            )
            n += 1
        except (IGError, KeyError) as e:
            kind = getattr(e, "kind", "api")
            db.connections.update_one({"_id": conn["_id"]}, {"$set": {"status": "expired" if kind == "expired" else "connected", "last_error": getattr(e, "message", "refresh failed")}})
    return n


# ------------------------------------------------------------------ sync
def _iso(ts: float) -> str:
    return datetime.fromtimestamp(ts, tz=timezone.utc).astimezone(IST).isoformat(timespec="seconds")


def _values(insights: dict) -> dict:
    """{metric: number} from an insights response (total_value or the latest value)."""
    out = {}
    for m in insights.get("data") or []:
        if "total_value" in m and "value" in (m["total_value"] or {}):
            out[m["name"]] = m["total_value"]["value"]
        elif m.get("values"):
            out[m["name"]] = m["values"][-1].get("value")
    return out


def _breakdown(insights: dict) -> dict:
    """{dimension value: count} from a demographics response with one breakdown."""
    out: dict[str, int] = {}
    for m in insights.get("data") or []:
        for b in (m.get("total_value") or {}).get("breakdowns") or []:
            for r in b.get("results") or []:
                key = ",".join(r.get("dimension_values") or [])
                out[key] = out.get(key, 0) + int(r.get("value") or 0)
    return out


def _topic(caption: str | None) -> str:
    tag = re.search(r"#(\w{3,24})", caption or "")
    return tag.group(1).replace("_", " ").capitalize() if tag else "Untagged"


AGE_BUCKETS = {"13-17": "13-17", "18-24": "18-24", "25-34": "25-34", "35-44": "35-44", "45-54": "45+", "55-64": "45+", "65+": "45+"}


def _audience(demo: dict, previous: dict | None) -> dict | None:
    """Instagram follower demographics in the shape matching uses. Languages aren't in
    Instagram's data, so they come from the creator's profile languages."""
    age, gender, city = demo.get("age") or {}, demo.get("gender") or {}, demo.get("city") or {}
    total = sum(age.values())
    if not total:
        return None
    ages: dict[str, float] = {}
    for k, v in age.items():
        b = AGE_BUCKETS.get(k)
        if b:
            ages[b] = ages.get(b, 0) + v / total
    g_total = (gender.get("F", 0) + gender.get("M", 0)) or 1
    c_total = sum(city.values()) or 1
    cities = sorted(({"name": k.split(",")[0].strip(), "share": round(v / c_total, 3)} for k, v in city.items()), key=lambda x: -x["share"])[:6]
    return {
        "age": {k: round(v, 3) for k, v in ages.items()},
        "gender": {"female": round(gender.get("F", 0) / g_total, 3), "male": round(gender.get("M", 0) / g_total, 3)},
        "cities": cities,
        "languages": (previous or {}).get("languages") or {},
    }


def sync(creator_id: str) -> dict:
    """Pull the connected account's profile, media, insights and demographics."""
    db = get_db()
    conn = db.connections.find_one({"creator_id": creator_id, "platform": "instagram"})
    if not conn:
        raise IGError("not_connected", "Instagram isn't connected.")
    try:
        return _sync(conn)
    except IGError as e:
        db.connections.update_one(
            {"_id": conn["_id"]}, {"$set": {"last_error": e.message, **({"status": "expired"} if e.kind == "expired" else {})}}
        )
        raise


def _sync(conn: dict) -> dict:
    db = get_db()
    token = _token(conn)
    creator_id = conn["creator_id"]
    now = time.time()
    fetched = _iso(now)
    profile = _graph("me", token, fields="user_id,username,account_type,followers_count,media_count,profile_picture_url")
    if (profile.get("account_type") or "").upper() == "PERSONAL":
        raise IGError("personal", "This is a personal Instagram account. Switch it to a Creator or Business account in Instagram's settings, then reconnect.")
    ig_id = str(profile.get("user_id") or profile.get("id") or conn.get("ig_user_id"))
    followers = int(profile.get("followers_count") or 0)
    notes: list[str] = []

    media = _graph("me/media", token, fields="id,caption,media_type,media_product_type,timestamp,permalink,like_count,comments_count", limit=MEDIA_LIMIT).get("data") or []
    reels = [m for m in media if (m.get("media_product_type") or "").upper() == "REELS"]
    insights_by_id: dict[str, dict] = {}
    for m in reels[:REEL_INSIGHTS]:
        try:
            insights_by_id[m["id"]] = _values(_graph(f"{m['id']}/insights", token, metric="views,reach,saved,shares"))
        except IGError as e:
            if e.kind in ("expired", "rate_limit"):
                raise
            notes.append("Some reels' insights weren't available.")
    notes = sorted(set(notes))

    account: dict = {}
    try:
        account = _values(
            _graph(f"{ig_id}/insights", token, metric="reach,views", period="day", metric_type="total_value", since=int(now - 28 * 86400), until=int(now))
        )
    except IGError as e:
        if e.kind in ("expired", "rate_limit"):
            raise
        notes.append("Account reach and views weren't available.")

    demographics: dict | None = None
    engaged: dict | None = None
    if followers < MIN_DEMOGRAPHICS_FOLLOWERS:
        notes.append(f"Audience demographics need at least {MIN_DEMOGRAPHICS_FOLLOWERS} followers on Instagram.")
    else:
        tf = get_settings().ig_demographics_timeframe
        for metric in ("follower_demographics", "engaged_audience_demographics"):
            result = {}
            for breakdown in ("age", "gender", "city", "country"):
                try:
                    result[breakdown] = _breakdown(_graph(f"{ig_id}/insights", token, metric=metric, period="lifetime", metric_type="total_value", timeframe=tf, breakdown=breakdown))
                except IGError as e:
                    if e.kind in ("expired", "rate_limit"):
                        raise
            if metric == "follower_demographics":
                demographics = result or None
            else:
                engaged = result or None
        if not demographics or not any(demographics.values()):
            notes.append("Instagram didn't return audience demographics for this account yet.")

    # Posts: one row per media item, with per-reel insights where read.
    for m in media:
        ins = insights_by_id.get(m["id"], {})
        db.posts.update_one(
            {"creator_id": creator_id, "platform": "instagram", "post_id": m["id"]},
            {
                "$set": {
                    "creator_id": creator_id,
                    "platform": "instagram",
                    "post_id": m["id"],
                    "caption": (m.get("caption") or "")[:2200],
                    "media_type": m.get("media_type"),
                    "media_product_type": m.get("media_product_type"),
                    "published_at": m.get("timestamp"),
                    "permalink": m.get("permalink"),
                    "likes": m.get("like_count"),
                    "comments": m.get("comments_count"),
                    "views": ins.get("views"),
                    "reach": ins.get("reach"),
                    "saves": ins.get("saved"),
                    "shares": ins.get("shares"),
                    "source": SOURCE,
                    "fetched_at": fetched,
                }
            },
            upsert=True,
        )
    day = datetime.now(IST).date().isoformat()
    db.metric_snapshots.update_one(
        {"creator_id": creator_id, "platform": "instagram", "date": day},
        {
            "$set": {
                "creator_id": creator_id,
                "platform": "instagram",
                "date": day,
                "followers": followers,
                "media_count": profile.get("media_count"),
                "reach_28d": account.get("reach"),
                "views_28d": account.get("views"),
                "follower_demographics": demographics,
                "engaged_audience_demographics": engaged,
                "source": SOURCE,
                "fetched_at": fetched,
            }
        },
        upsert=True,
    )
    summary = {
        "ig_user_id": ig_id,
        "username": profile.get("username"),
        "account_type": profile.get("account_type"),
        "followers": followers,
        "media_count": profile.get("media_count"),
        "picture": profile.get("profile_picture_url"),
        "reach_28d": account.get("reach"),
        "views_28d": account.get("views"),
        "demographics": demographics,
        "notes": notes,
        "source": SOURCE,
        "fetched_at": fetched,
    }
    _apply_to_profile(creator_id, summary, media, insights_by_id)
    db.connections.update_one({"_id": conn["_id"]}, {"$set": {"status": "connected", "last_error": None, "last_sync_at": now, "ig_user_id": ig_id, "username": profile.get("username")}})
    from . import coach, fan_proof

    fan_proof.recompute(creator_id, "instagram")
    coach.on_new_data(creator_id, "New Instagram data")
    return summary


def _apply_to_profile(creator_id: str, summary: dict, media: list[dict], insights: dict[str, dict]) -> None:
    """Connected numbers replace the profile's sample or typed numbers. What was there
    before is kept aside and comes back on disconnect."""
    db = get_db()
    c = db.creators.find_one({"_id": creator_id}) or {}
    update: dict = {"channels.instagram": summary, "followers": summary["followers"]}
    if "pre_instagram" not in c:
        update["pre_instagram"] = {k: c.get(k) for k in ("reels", "followers", "audience", "provenance", "provenance_default", "insights_source", "insights_connected", "follower_history", "comment_insights")}
    prov = {k: v for k, v in (c.get("provenance") or {}).items() if not k.startswith(("reels", "followers", "audience"))}
    prov["followers"] = "real"
    reels = []
    for m in media:
        ins = insights.get(m["id"])
        if (m.get("media_product_type") or "").upper() != "REELS" or not ins or ins.get("views") is None:
            continue
        reels.append(
            {
                "id": f"ig_{m['id']}",
                "date": (m.get("timestamp") or "")[:10],
                "views": int(ins.get("views") or 0),
                "likes": int(m.get("like_count") or 0),
                "saves": int(ins.get("saved") or 0),
                "shares": int(ins.get("shares") or 0),
                "comments": int(m.get("comments_count") or 0),
                "format": "reels",
                "topic": _topic(m.get("caption")),
                "caption": (m.get("caption") or "")[:2200] or None,
                "lang": None,
                "copyrighted_clips": False,
                "original_voiceover": None,
                "source": SOURCE,
            }
        )
    if len(reels) >= 3:
        update["reels"] = reels
        prov["reels"] = "real"
        update["insights_source"] = SOURCE
        update["insights_connected.instagram"] = True
    audience = _audience(summary.get("demographics") or {}, c.get("audience"))
    if audience:
        update["audience"] = audience
        prov["audience"] = "real"
    update["provenance"] = prov
    db.creators.update_one({"_id": creator_id}, {"$set": update})
    from . import reach

    reach.refresh(creator_id)  # brand search filters on it


def disconnect(user: dict, creator_id: str) -> None:
    """Deletes the token and every piece of Instagram data stored for this creator."""
    db = get_db()
    db.connections.delete_many({"user_id": user["_id"], "platform": "instagram"})
    db.connections.delete_many({"creator_id": creator_id, "platform": "instagram"})
    # The Instagram account stays this account's sign-in only when it's the only way in;
    # otherwise disconnecting frees it.
    if user.get("password_hash") or user.get("firebase_uid"):
        db.users.update_one({"_id": user["_id"]}, {"$unset": {"instagram_uid": ""}})
    db.posts.delete_many({"creator_id": creator_id, "platform": "instagram"})
    db.metric_snapshots.delete_many({"creator_id": creator_id, "platform": "instagram"})
    db.oauth_states.delete_many({"user_id": user["_id"], "platform": "instagram"})
    c = db.creators.find_one({"_id": creator_id}) or {}
    restore = c.get("pre_instagram")
    update: dict = {"$unset": {"channels.instagram": "", "pre_instagram": ""}}
    if restore is not None:
        update["$set"] = {k: v for k, v in restore.items() if v is not None}
        update["$set"]["insights_connected"] = {**(restore.get("insights_connected") or {}), "instagram": False}
        update["$unset"].update({k: "" for k, v in restore.items() if v is None and k != "insights_connected"})
    db.creators.update_one({"_id": creator_id}, update)
    from . import fan_proof_hooks, reach

    reach.refresh(creator_id)

    fan_proof_hooks.on_disconnect(creator_id, "instagram")


# ------------------------------------------------------------------ status and post checks
def status(creator: dict) -> dict:
    base = {"platform": "instagram", "label": "Instagram"}
    if not configured():
        return {**base, "status": "unavailable", "detail": "Instagram connect isn't set up on this server yet."}
    conn = get_db().connections.find_one({"creator_id": creator["_id"], "platform": "instagram"})
    if not conn:
        return {**base, "status": "not_connected", "detail": "Connect with Instagram's official login (read-only) to use your real reach and audience."}
    ig = (creator.get("channels") or {}).get("instagram") or {}
    if conn.get("status") == "expired":
        return {**base, "status": "expired", "detail": conn.get("last_error") or "Instagram access expired. Reconnect Instagram."}
    detail = f"@{ig.get('username') or conn.get('username') or 'your account'}: profile, posts, reach and audience."
    if conn.get("last_error"):
        detail += f" Last sync: {conn['last_error']}"
    return {**base, "status": "connected", "detail": detail, "source": SOURCE, "fetched_at": ig.get("fetched_at")}


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", (s or "").lower())


def check_post(deal: dict) -> dict | None:
    """Checks a deal's Instagram post against the creator's connected account. None when
    there's no Instagram link or no connection; the deal then shows 'not checked'."""
    m = SHORTCODE.search(deal.get("proof_url") or "")
    if not m or not configured():
        return None
    db = get_db()
    conn = db.connections.find_one({"creator_id": deal["creator_id"], "platform": "instagram", "status": "connected"})
    if not conn:
        return None
    code = m.group(1)
    checked = _iso(time.time())
    try:
        media = _graph("me/media", _token(conn), fields="id,caption,timestamp,permalink,media_product_type", limit=MEDIA_LIMIT).get("data") or []
    except IGError as e:
        return {
            "source": SOURCE,
            "checked_at": checked,
            "note": f"Couldn't check the post: {e.message}",
            "checks": [{"label": label, "status": "not_checked"} for label in ("The post is public and live", "Posted on the creator's connected account", "Posted after the contract was signed", "The caption mentions the brand", "Paid-partnership label added")],
        }
    post = next((x for x in media if f"/{code}" in (x.get("permalink") or "")), None)
    brand = db.brands.find_one({"_id": deal["brand_id"]}) or {}
    contract = deal.get("contract") or {}
    signed = max([t for t in (contract.get("signed_by_creator"), contract.get("signed_by_brand")) if t] or [""])
    checks = []
    if not post:
        checks.append({"label": "Posted on the creator's connected account", "status": "failed", "detail": f"Not among the latest {MEDIA_LIMIT} posts of @{conn.get('username') or 'the connected account'}."})
        checks.append({"label": "The post is public and live", "status": "not_checked"})
        checks.append({"label": "Posted after the contract was signed", "status": "not_checked"})
        checks.append({"label": "The caption mentions the brand", "status": "not_checked"})
    else:
        checks.append({"label": "Posted on the creator's connected account", "status": "passed", "detail": f"@{conn.get('username') or 'connected account'}"})
        checks.append({"label": "The post is public and live", "status": "passed"})
        posted = post.get("timestamp") or ""
        if signed:
            after = datetime.fromisoformat(posted.replace("Z", "+00:00").replace("+0000", "+00:00")) >= datetime.fromisoformat(signed)
            checks.append({"label": "Posted after the contract was signed", "status": "passed" if after else "failed", "detail": f"Posted {posted[:10]}"})
        else:
            checks.append({"label": "Posted after the contract was signed", "status": "not_checked"})
        caption = _norm(post.get("caption") or "")
        names = {_norm(brand.get("name", "")), _norm((brand.get("public_handles") or {}).get("instagram", ""))} - {""}
        mentioned = any(n in caption for n in names)
        checks.append({"label": "The caption mentions the brand", "status": "passed" if mentioned else "failed", "detail": None if mentioned else f"No mention of {brand.get('name', 'the brand')} in the caption."})
    checks.append({"label": "Paid-partnership label added", "status": "not_checked", "detail": "Instagram's API doesn't show this label. The brand checks it on the post."})
    return {"source": SOURCE, "checked_at": checked, "checks": checks}
