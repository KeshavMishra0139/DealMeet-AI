"""Creator sign-in with Instagram and YouTube: providers faked at the HTTP layer, sessions,
one-time login codes, one identity per account, and data attached at onboarding."""
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import instagram as ig
from app.services import social_signin

from conftest import APP_HEADER
from test_firebase import firebase  # noqa: F401  (fixture)
from test_instagram import LONG, instagram  # noqa: F401  (fixture)
from test_youtube import CHANNEL, FakeYouTube

ONBOARDING = {"name": "Meera", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["ta"], "city": "Chennai"}


def fresh() -> TestClient:
    return TestClient(app, headers=APP_HEADER)


# ------------------------------------------------------------------ Instagram
def _start(c: TestClient, next_path: str | None = None) -> str:
    r = c.get("/api/auth/instagram/start", params={"next": next_path} if next_path else None)
    assert r.status_code == 200, r.text
    q = parse_qs(urlparse(r.json()["url"]).query)
    assert q["redirect_uri"] == ["https://jodidar.test/api/connect/instagram/callback"]
    return q["state"][0]


def _callback(c: TestClient, state: str, code: str = "GOOD-CODE", **extra) -> str:
    r = c.get("/api/connect/instagram/callback", params={"code": code, "state": state, **extra}, follow_redirects=False)
    assert r.status_code == 302
    return r.headers["location"]


def _login_code(location: str) -> str:
    assert location.startswith("https://jodidar.test/login/complete?code="), location
    return parse_qs(urlparse(location).query)["code"][0]


def _instagram_sign_in(next_path: str | None = None) -> tuple[TestClient, dict]:
    c = fresh()
    code = _login_code(_callback(c, _start(c, next_path)))
    r = c.post("/api/auth/oauth/complete", json={"code": code})
    assert r.status_code == 200, r.text
    assert "httponly" in r.headers["set-cookie"].lower()
    return c, r.json()


def test_instagram_sign_in_needs_the_server_set_up(client, db):
    r = client.get("/api/auth/instagram/start")
    assert r.status_code == 503 and "isn't set up" in r.json()["detail"]
    assert "instagram" not in client.get("/api/health").json()["modes"]["auth"]


def test_first_instagram_sign_in_creates_a_creator_with_a_pending_connection(client, instagram, db):
    assert "instagram" in client.get("/api/health").json()["modes"]["auth"]
    c, body = _instagram_sign_in("/creator/money")
    user = body["user"]
    assert user["role"] == "creator" and user["creator_id"] is None and user["name"] == "meera.kitchen"
    assert user["providers"] == ["instagram"] and body["next"] == "/creator/money"
    assert c.get("/api/auth/me").json()["user"]["id"] == user["id"]
    conn = db.connections.find_one({"user_id": user["id"], "platform": "instagram"})
    assert conn["creator_id"] is None and conn["ig_user_id"] == "17841"
    assert LONG not in str(conn) and ig.crypto.decrypt(conn["token_enc"]) == LONG
    assert db.users.find_one({"_id": user["id"]})["instagram_uid"] == "17841"


def test_onboarding_attaches_the_instagram_account_and_uses_its_numbers(client, instagram, db):
    c, body = _instagram_sign_in()
    r = c.post("/api/creators", json=ONBOARDING)
    assert r.status_code == 200, r.text
    assert r.json()["notes"] == []
    cid = r.json()["id"]
    creator = db.creators.find_one({"_id": cid})
    assert creator["followers"] == 5_400 and creator["provenance"]["followers"] == "real"
    assert creator["channels"]["instagram"]["username"] == "meera.kitchen"
    assert db.connections.find_one({"user_id": body["user"]["id"]})["creator_id"] == cid


def test_signing_in_again_returns_the_same_account(client, instagram, db):
    _, first = _instagram_sign_in()
    _, second = _instagram_sign_in()
    assert first["user"]["id"] == second["user"]["id"]
    assert db.users.count_documents({"instagram_uid": "17841"}) == 1


def test_login_codes_are_single_use_and_short_lived(client, instagram, db):
    c = fresh()
    code = _login_code(_callback(c, _start(c)))
    assert db.login_codes.find_one({"_id": code}) is None  # only the hash is stored
    assert c.post("/api/auth/oauth/complete", json={"code": code}).status_code == 200
    assert c.post("/api/auth/oauth/complete", json={"code": code}).status_code == 400  # replayed
    code2 = _login_code(_callback(c, _start(c)))
    db.login_codes.update_many({}, {"$set": {"expires": time.time() - 1}})
    r = c.post("/api/auth/oauth/complete", json={"code": code2})
    assert r.status_code == 400 and "expired" in r.json()["detail"]


def test_a_login_link_only_works_in_the_browser_that_started_it(client, instagram, db):
    starter = fresh()
    code = _login_code(_callback(starter, _start(starter)))
    victim = fresh()  # someone sent this link: no cookie from the start
    r = victim.post("/api/auth/oauth/complete", json={"code": code})
    assert r.status_code == 400 and "another browser" in r.json()["detail"]
    assert victim.get("/api/auth/me").status_code == 401


def test_sign_in_states_are_single_use_and_never_finish_a_connection(client, login, instagram, db):
    c = fresh()
    state = _start(c)
    assert state.startswith(ig.SIGNIN_MARK)
    _callback(c, state)
    assert "already%20used" in _callback(c, state)
    nonce, _, _ = _start(c).partition(".")
    assert "isn%27t%20valid" in _callback(c, f"{nonce}.{'0' * 32}")  # forged signature
    # A connection state can't be replayed as a sign-in, and the reverse.
    connect_state = login("cr_b").get("/api/connect/instagram/start?json=1").json()["url"]
    connect_state = parse_qs(urlparse(connect_state).query)["state"][0]
    assert "isn%27t%20valid" in _callback(c, ig.SIGNIN_MARK + connect_state)


def test_cancelled_instagram_sign_in_signs_nobody_in(client, instagram, db):
    c = fresh()
    location = _callback(c, _start(c), code="", error="access_denied", error_reason="user_denied")
    assert location.startswith("https://jodidar.test/login?role=creator&error=") and "cancelled" in location
    assert db.users.count_documents({"instagram_uid": {"$exists": True}}) == 0


def test_a_creator_who_connected_instagram_signs_in_to_the_same_account(client, login, instagram, db):
    b = login("cr_b")
    connect = b.get("/api/connect/instagram/start?json=1").json()["url"]
    assert "connected" in _callback(client, parse_qs(urlparse(connect).query)["state"][0])
    # Accounts that connected before sign-in existed are found through the connection.
    db.users.update_one({"_id": b.user["id"]}, {"$unset": {"instagram_uid": ""}})
    _, body = _instagram_sign_in()
    assert body["user"]["id"] == b.user["id"] and body["user"]["creator_id"] == "cr_b"


def test_one_instagram_account_signs_in_to_one_dealmeet_account(client, login, instagram, db):
    _instagram_sign_in()  # 17841 now signs in to a new creator account
    b = login("cr_b")
    connect = b.get("/api/connect/instagram/start?json=1").json()["url"]
    location = _callback(client, parse_qs(urlparse(connect).query)["state"][0])
    assert "ig=error" in location and "another%20DealMeet%20account" in location
    assert db.connections.count_documents({"creator_id": "cr_b"}) == 0


def test_disconnecting_keeps_instagram_as_the_only_way_in(client, instagram, db):
    c, body = _instagram_sign_in()
    c.post("/api/creators", json=ONBOARDING)
    assert c.post("/api/connect/instagram/disconnect").status_code == 200
    assert db.users.find_one({"_id": body["user"]["id"]})["instagram_uid"] == "17841"
    _, again = _instagram_sign_in()  # signing in again reconnects the same account
    assert again["user"]["id"] == body["user"]["id"]
    assert db.connections.count_documents({"user_id": body["user"]["id"], "platform": "instagram"}) == 1


def test_suspended_accounts_cant_sign_in_with_instagram(client, instagram, db):
    _, body = _instagram_sign_in()
    db.users.update_one({"_id": body["user"]["id"]}, {"$set": {"suspended": True}})
    c = fresh()
    location = _callback(c, _start(c))
    assert "error=" in location and "suspended" in location


# ------------------------------------------------------------------ YouTube
GOOGLE_SUB = "google-sub-1"
ACCESS = "ya29.youtube-access-token"


class FakeGoogle(FakeYouTube):
    """tokeninfo and channels?mine=true with the user's token; everything else is the
    Data API with the server's key (FakeYouTube)."""

    def __init__(self):
        super().__init__()
        self.sub = GOOGLE_SUB
        self.scope = "openid email https://www.googleapis.com/auth/youtube.readonly"
        self.has_channel = True

    def get(self, url, params=None, headers=None, timeout=None):
        req = httpx.Request("GET", url)
        if url == social_signin.TOKENINFO:
            if params["access_token"] != ACCESS:
                return httpx.Response(400, json={"error": "invalid_token"}, request=req)
            return httpx.Response(200, json={"sub": self.sub, "scope": self.scope, "expires_in": "3500"}, request=req)
        if headers and headers.get("Authorization"):
            assert url == social_signin.CHANNELS and params["mine"] == "true"
            assert headers["Authorization"] == f"Bearer {ACCESS}"
            items = [{"id": CHANNEL, "snippet": {"title": "Test Kitchen", "customUrl": "@testkitchen"}}] if self.has_channel else []
            return httpx.Response(200, json={"items": items}, request=req)
        return super().get(url, params=params, timeout=timeout)


@pytest.fixture()
def google(monkeypatch, firebase, db):  # noqa: F811
    from firebase_admin import auth

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    config.get_settings.cache_clear()
    for name in ("yt_cache", "rate_limits"):
        db[name].delete_many({})
    claims = {"uid": "fb-yt-1", "email": "meera@example.com", "email_verified": True, "name": "Meera", "firebase": {"sign_in_provider": "google.com", "identities": {"google.com": [GOOGLE_SUB]}}}
    monkeypatch.setattr(auth, "verify_id_token", lambda token, app=None, check_revoked=False: dict(claims))
    fake = FakeGoogle()
    fake.claims = claims
    monkeypatch.setattr(social_signin.httpx, "get", fake.get)
    yield fake
    config.get_settings.cache_clear()


def _yt(c: TestClient, access: str = ACCESS):
    return c.post("/api/auth/youtube", json={"id_token": "t" * 40, "access_token": access})


def test_youtube_sign_in_needs_the_server_set_up(client, db):
    r = _yt(client)
    assert r.status_code == 503 and "isn't set up" in r.json()["detail"]
    assert "youtube" not in client.get("/api/health").json()["modes"]["auth"]


def test_first_youtube_sign_in_creates_a_creator_and_links_the_channel_at_onboarding(client, google, db):
    assert "youtube" in client.get("/api/health").json()["modes"]["auth"]
    c = fresh()
    r = _yt(c)
    assert r.status_code == 200, r.text
    user = r.json()["user"]
    assert user["role"] == "creator" and user["name"] == "Test Kitchen" and set(user["providers"]) == {"firebase", "youtube"}
    assert db.users.find_one({"_id": user["id"]})["youtube_channel_id"] == CHANNEL
    cid = c.post("/api/creators", json=ONBOARDING).json()["id"]
    yt = db.creators.find_one({"_id": cid})["channels"]["youtube"]
    assert yt["channel_id"] == CHANNEL and yt["ownership_verified"] is True and yt["subscribers"] == 21_300
    assert db.posts.count_documents({"creator_id": cid, "platform": "youtube"}) > 0


def test_youtube_sign_in_links_the_channel_to_an_existing_profile(client, google, db):
    c = fresh()
    _yt(c)
    cid = c.post("/api/creators", json=ONBOARDING).json()["id"]
    db.creators.update_one({"_id": cid}, {"$unset": {"channels.youtube": ""}})
    r = _yt(c)
    assert r.status_code == 200 and "note" not in r.json()
    assert db.creators.find_one({"_id": cid})["channels"]["youtube"]["ownership_verified"] is True


def test_the_access_token_must_belong_to_the_google_account_that_signed_in(client, google, db):
    google.sub = "someone-else"
    r = _yt(fresh())
    assert r.status_code == 401 and "different Google account" in r.json()["detail"]
    assert db.users.count_documents({"firebase_uid": "fb-yt-1"}) == 0  # nothing created


def test_youtube_scope_and_a_google_sign_in_are_required(client, google, db):
    google.scope = "openid email"
    assert _yt(fresh()).status_code == 403
    google.scope = "https://www.googleapis.com/auth/youtube.readonly"
    google.claims["firebase"] = {"sign_in_provider": "phone", "identities": {}}
    assert _yt(fresh()).status_code == 401
    assert _yt(fresh(), access="ya29.not-a-real-token-xx").status_code == 401


def test_a_google_account_without_a_channel_still_signs_in_and_is_told(client, google, db):
    google.has_channel = False
    r = _yt(fresh())
    assert r.status_code == 200 and "doesn't have a YouTube channel" in r.json()["note"]
    assert "youtube_channel_id" not in db.users.find_one({"_id": r.json()["user"]["id"]})


def test_one_channel_links_to_one_dealmeet_account(client, google, db):
    _yt(fresh())
    google.claims["uid"] = "fb-yt-2"  # another Google account that manages the same channel
    google.claims["email"] = "other@example.com"
    r = _yt(fresh())
    assert r.status_code == 200 and "already linked to another DealMeet account" in r.json()["note"]
    assert db.users.count_documents({"youtube_channel_id": CHANNEL}) == 1


def test_a_brand_account_keeps_its_role(client, google, db):
    fresh().post("/api/auth/signup", json={"email": "meera@example.com", "password": "long enough", "name": "Meera", "role": "brand"})
    r = _yt(fresh())
    assert r.status_code == 200 and r.json()["user"]["role"] == "brand"
    assert "brand account" in r.json()["note"]
    assert db.users.count_documents({"youtube_channel_id": CHANNEL}) == 0
