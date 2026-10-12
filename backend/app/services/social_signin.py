"""Creator sign-in with Instagram or YouTube.

- "Continue with Instagram" runs Instagram's official login (the same read-only
  Business Login as Connections) before anyone is signed in. The Instagram account
  is the sign-in identity (users.instagram_uid), and its token becomes the creator's
  Instagram connection.
- "Continue with YouTube" is a Google sign-in through Firebase that also asks for
  read-only YouTube access (youtube.readonly). The Google account is the sign-in
  identity (users.firebase_uid, as with "Continue with Google"); the access token is
  used once, to see which channel that Google account owns, and never stored. The
  channel is recorded as verified (users.youtube_channel_id) and linked to the profile.

Each identity signs in to one account, and a first sign-in creates a creator account.
Until the creator finishes onboarding there's no profile to attach data to, so
`attach_pending` runs at onboarding: it syncs the pending Instagram connection and
links the verified YouTube channel.

Instagram's login ends on the API's callback, which may not share an origin with the
web app, so the callback never sets the session cookie itself. It hands the browser a
one-time login code (2 minutes, stored hashed, used once) that the web app exchanges
at POST /api/auth/oauth/complete on its own origin. The exchange also needs the
short-lived cookie set when this browser started the sign-in, so a login link sent to
someone else can't sign them in to the sender's account (login CSRF).
"""
from __future__ import annotations

import hmac
import logging
import secrets
import time

import httpx
from fastapi import HTTPException
from pymongo.errors import DuplicateKeyError

from ..config import get_settings
from ..db import get_db
from . import auth as au
from . import instagram as ig
from . import youtube_public as yt

log = logging.getLogger("jodidar.social_signin")

LOGIN_CODE_TTL = 120
BINDING_COOKIE = "jd_signin"
SYNC_AFTER = 6 * 3600  # an Instagram sign-in refreshes data at most this often
TOKENINFO = "https://oauth2.googleapis.com/tokeninfo"
CHANNELS = "https://www.googleapis.com/youtube/v3/channels"
YOUTUBE_SCOPE = "https://www.googleapis.com/auth/youtube.readonly"


# ------------------------------------------------------------------ availability
def instagram_configured() -> bool:
    return ig.configured()


def youtube_configured() -> bool:
    """Needs Firebase (who signed in) and the YouTube Data API key (the channel's numbers)."""
    return get_settings().has_firebase and yt.configured()


# ------------------------------------------------------------------ one-time login codes
def new_binding() -> tuple[str, str]:
    """(cookie value for the browser starting a sign-in, hash kept with the sign-in)."""
    value = secrets.token_urlsafe(24)
    return value, au.hash_token(value)


def issue_login_code(user: dict, via: str, binding: str | None, next_path: str | None = None, note: str | None = None) -> str:
    code = secrets.token_urlsafe(32)
    get_db().login_codes.insert_one(
        {
            "_id": au.hash_token(code),
            "user_id": user["_id"],
            "via": via,
            "binding": binding,
            "next": next_path,
            "note": note,
            "expires": time.time() + LOGIN_CODE_TTL,
        }
    )
    return code


def redeem_login_code(code: str, cookie: str | None) -> dict:
    """The code's record, once, for the browser that started the sign-in. Deleted on first
    use, so a replayed code finds nothing."""
    doc = get_db().login_codes.find_one_and_delete({"_id": au.hash_token(code)})
    if not doc or doc["expires"] < time.time():
        raise HTTPException(400, "That sign-in link expired or was already used. Sign in again.")
    if not doc.get("binding") or not cookie or not hmac.compare_digest(doc["binding"], au.hash_token(cookie)):
        raise HTTPException(400, "That sign-in was started in another browser. Sign in again here.")
    return doc


# ------------------------------------------------------------------ Instagram
def instagram_signin(code: str) -> tuple[dict, str | None]:
    """The code from Instagram's login -> the creator account it signs in to, created on
    the first sign-in. Raises ig.IGError with a message safe to show."""
    grant = ig.exchange_code(code)
    who = ig.identity(grant["token"])
    grant["ig_user_id"] = who["ig_user_id"]
    user = ig.account_for(who["ig_user_id"])
    if user:
        if user.get("suspended"):
            raise ig.IGError("suspended", "This account is suspended. Contact support if you think this is a mistake.")
        if user.get("role") != "creator":
            raise ig.IGError("role", "This Instagram account is linked to a brand account. Sign in to it another way.")
        ig.claim_identity(user, who["ig_user_id"])
    else:
        name = (who.get("username") or "New creator")[:60]
        try:
            user = au.new_user("creator", name, instagram_uid=who["ig_user_id"])
        except DuplicateKeyError:  # the same Instagram account signed up a moment ago
            raise ig.IGError("taken", "This Instagram account was just used to sign up. Sign in again.") from None
        au.audit("signup", user["_id"], "creator", via="instagram")
    ig.save_connection(user, user.get("creator_id"), grant)
    note = None
    if user.get("creator_id"):
        conn = get_db().connections.find_one({"user_id": user["_id"], "platform": "instagram"}) or {}
        if (conn.get("last_sync_at") or 0) < time.time() - SYNC_AFTER:
            try:
                ig.sync(user["creator_id"])
            except ig.IGError as e:
                note = f"You're signed in, but your Instagram numbers didn't refresh: {e.message}"
    return user, note


# ------------------------------------------------------------------ YouTube
def google_ids(claims: dict) -> list[str]:
    """The Google account ids behind a verified Firebase token. Refuses any other provider."""
    fb = claims.get("firebase") or {}
    ids = (fb.get("identities") or {}).get("google.com") or []
    if fb.get("sign_in_provider") != "google.com" or not ids:
        raise HTTPException(401, "Continue with YouTube needs a Google sign-in. Try again.")
    return [str(i) for i in ids]


def _google(url: str, *, params: dict, token: str | None = None) -> httpx.Response:
    try:
        return httpx.get(url, params=params, headers={"Authorization": f"Bearer {token}"} if token else None, timeout=10)
    except httpx.HTTPError as e:
        log.warning("Google call failed: %s", type(e).__name__)  # never the URL or token
        raise HTTPException(502, "Couldn't reach YouTube right now. Try again in a minute.") from None


def owned_channel(access_token: str, ids: list[str]) -> dict | None:
    """The channel the signed-in Google account owns, or None when it has none. The token
    must belong to that same Google account and carry the YouTube scope; it's used here
    and dropped."""
    r = _google(TOKENINFO, params={"access_token": access_token})
    if r.status_code >= 400:
        raise HTTPException(401, "Google's sign-in expired before we could check your channel. Try again.")
    info = r.json()
    if str(info.get("sub") or "") not in ids:
        raise HTTPException(401, "That YouTube access belongs to a different Google account than the one that signed in. Try again.")
    if YOUTUBE_SCOPE not in (info.get("scope") or "").split():
        raise HTTPException(403, "YouTube access wasn't granted. Try again and allow DealMeet to see your YouTube account.")
    r = _google(CHANNELS, params={"part": "id,snippet", "mine": "true"}, token=access_token)
    if r.status_code == 401:
        raise HTTPException(401, "Google's sign-in expired before we could check your channel. Try again.")
    if r.status_code >= 400:
        raise HTTPException(502, f"YouTube returned an error ({r.status_code}). Try again later.")
    items = r.json().get("items") or []
    if not items:
        return None
    sn = items[0].get("snippet") or {}
    return {"channel_id": items[0]["id"], "title": sn.get("title"), "handle": sn.get("customUrl")}


def link_verified_channel(creator_id: str, channel_id: str) -> None:
    """Links the channel's public numbers to the profile, marked as owned: the creator
    proved it through Google. Raises HTTPException when YouTube can't be read."""
    db = get_db()
    c = db.creators.find_one({"_id": creator_id}, {"niche": 1}) or {}
    yt.save_for_creator(creator_id, yt.channel_report(channel_id, c.get("niche")))
    db.creators.update_one({"_id": creator_id}, {"$set": {"channels.youtube.ownership_verified": True}})


def claim_channel(user: dict, channel: dict) -> str | None:
    """Records the verified channel on a creator account and links it to the profile, if
    there is one. Returns a note when something wasn't linked, and why."""
    if user.get("role") != "creator":
        return "This is a brand account, so the YouTube channel wasn't linked."
    db = get_db()
    ch_id = channel["channel_id"]
    mine = user.get("youtube_channel_id")
    if mine and mine != ch_id:
        return f"This account is linked to a different YouTube channel, so {channel.get('title') or 'this channel'} wasn't linked."
    if not mine:
        if db.users.count_documents({"youtube_channel_id": ch_id, "_id": {"$ne": user["_id"]}}):
            return "That YouTube channel is already linked to another DealMeet account, so it wasn't linked here."
        try:
            db.users.update_one({"_id": user["_id"]}, {"$set": {"youtube_channel_id": ch_id}})
        except DuplicateKeyError:
            return "That YouTube channel is already linked to another DealMeet account, so it wasn't linked here."
        user["youtube_channel_id"] = ch_id
    creator_id = user.get("creator_id")
    if not creator_id:
        return None  # linked when onboarding creates the profile
    linked = ((db.creators.find_one({"_id": creator_id}, {"channels": 1}) or {}).get("channels") or {}).get("youtube")
    if linked and linked.get("channel_id") != ch_id:
        return f"Your profile shows a different channel ({linked.get('title')}). It wasn't changed; you can switch it in Connections."
    if linked:
        db.creators.update_one({"_id": creator_id}, {"$set": {"channels.youtube.ownership_verified": True}})
        return None
    try:
        link_verified_channel(creator_id, ch_id)
    except HTTPException as e:
        return f"You're signed in, but your channel's numbers couldn't be read: {e.detail}"
    return None


# ------------------------------------------------------------------ onboarding
def attach_pending(user: dict, creator_id: str) -> list[str]:
    """After onboarding creates the profile: sync the Instagram account and link the
    YouTube channel the creator signed in with. Returns a note for anything that
    couldn't be read; the profile is created either way."""
    db = get_db()
    notes: list[str] = []
    moved = db.connections.update_many({"user_id": user["_id"], "platform": "instagram", "creator_id": None}, {"$set": {"creator_id": creator_id}})
    if moved.modified_count:
        try:
            ig.sync(creator_id)
        except ig.IGError as e:
            notes.append(f"Instagram: {e.message}")
    if user.get("youtube_channel_id"):
        try:
            link_verified_channel(creator_id, user["youtube_channel_id"])
        except HTTPException as e:
            notes.append(f"YouTube: {e.detail}")
    return notes
