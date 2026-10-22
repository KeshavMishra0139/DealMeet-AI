"""Instagram connect (Business Login), faked at the HTTP layer: OAuth state, encrypted
tokens, sync, refresh, disconnect and deal post checks."""
import time
from urllib.parse import parse_qs, urlparse

import httpx
import pytest
from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import instagram as ig

from conftest import APP_HEADER

LONG = "IGAA-long-lived-secret-token"


class FakeInstagram:
    def __init__(self):
        self.followers = 5_400
        self.account_type = "MEDIA_CREATOR"
        self.expired = False
        self.rate_limited = False
        self.calls: list[str] = []
        now = int(time.time())
        self.media = [
            {
                "id": f"m{i}",
                "caption": f"Rava upma in 10 minutes #breakfast with @thalamfoods" if i == 0 else f"Reel {i} #breakfast",
                "media_type": "VIDEO",
                "media_product_type": "REELS",
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S+0000", time.gmtime(now - i * 86400)),
                "permalink": f"https://www.instagram.com/reel/CODE{i}/",
                "like_count": 400 + i,
                "comments_count": 20 + i,
            }
            for i in range(5)
        ]

    def _resp(self, url, body, status=200):
        return httpx.Response(status, json=body, request=httpx.Request("GET", url))

    def get(self, url, params=None, timeout=None):
        params = params or {}
        path = urlparse(url).path
        self.calls.append(path)
        if self.expired and "access_token" in params and params["access_token"] != "SHORT":
            return self._resp(url, {"error": {"message": "Error validating access token", "code": 190}}, 400)
        if self.rate_limited:
            return self._resp(url, {"error": {"message": "limit", "code": 4}}, 400)
        if path == "/access_token":
            assert params["grant_type"] == "ig_exchange_token" and params["access_token"] == "SHORT"
            return self._resp(url, {"access_token": LONG, "token_type": "bearer", "expires_in": 5_184_000})
        if path == "/refresh_access_token":
            return self._resp(url, {"access_token": LONG + "-refreshed", "expires_in": 5_184_000})
        assert path.startswith("/v25.0/"), path
        assert params.get("access_token", "").startswith(LONG)
        rest = path[len("/v25.0/"):]
        if rest == "me":
            return self._resp(url, {"user_id": "17841", "username": "meera.kitchen", "account_type": self.account_type, "followers_count": self.followers, "media_count": 120, "profile_picture_url": "https://x/p.jpg"})
        if rest == "me/media":
            return self._resp(url, {"data": self.media})
        if rest.endswith("/insights"):
            metric = params["metric"]
            if metric == "views,reach,saved,shares":
                i = int(rest.split("/")[0][1:])
                return self._resp(url, {"data": [{"name": n, "values": [{"value": v}]} for n, v in (("views", 9_000 + 1_000 * i), ("reach", 7_000), ("saved", 300), ("shares", 120))]})
            if metric == "reach,views":
                return self._resp(url, {"data": [{"name": "reach", "total_value": {"value": 61_000}}, {"name": "views", "total_value": {"value": 98_000}}]})
            if metric in ("follower_demographics", "engaged_audience_demographics"):
                assert params["timeframe"] == "this_month" and params["metric_type"] == "total_value"
                values = {
                    "age": [("18-24", 300), ("25-34", 500), ("45-54", 200)],
                    "gender": [("F", 700), ("M", 300)],
                    "city": [("Chennai, Tamil Nadu", 600), ("Madurai, Tamil Nadu", 400)],
                    "country": [("IN", 1000)],
                }[params["breakdown"]]
                results = [{"dimension_values": [k], "value": v} for k, v in values]
                return self._resp(url, {"data": [{"name": metric, "total_value": {"breakdowns": [{"dimension_keys": [params["breakdown"]], "results": results}]}}]})
        raise AssertionError(f"unexpected call {path} {params}")

    def post(self, url, data=None, timeout=None):
        assert url == ig.TOKEN_URL and data["grant_type"] == "authorization_code" and data["code"] == "GOOD-CODE"
        return httpx.Response(200, json={"data": [{"access_token": "SHORT", "user_id": "17841", "permissions": "instagram_business_basic,instagram_business_manage_insights"}]}, request=httpx.Request("POST", url))


@pytest.fixture()
def instagram(monkeypatch, db):
    monkeypatch.setenv("IG_APP_ID", "app123")
    monkeypatch.setenv("IG_APP_SECRET", "secret456")
    monkeypatch.setenv("IG_REDIRECT_URI", "https://jodidar.test/api/connect/instagram/callback")
    monkeypatch.setenv("FRONTEND_URL", "https://jodidar.test")
    monkeypatch.setenv("TOKEN_ENC_KEY", Fernet.generate_key().decode())
    config.get_settings.cache_clear()
    for name in ("connections", "oauth_states", "rate_limits", "posts", "metric_snapshots"):
        db[name].delete_many({})
    fake = FakeInstagram()
    monkeypatch.setattr(ig.httpx, "get", fake.get)
    monkeypatch.setattr(ig.httpx, "post", fake.post)
    yield fake
    config.get_settings.cache_clear()


def _start(actor) -> str:
    r = actor.get("/api/connect/instagram/start?json=1")
    assert r.status_code == 200, r.text
    q = parse_qs(urlparse(r.json()["url"]).query)
    assert q["scope"] == ["instagram_business_basic,instagram_business_manage_insights"] and q["response_type"] == ["code"]
    assert q["client_id"] == ["app123"] and q["redirect_uri"] == ["https://jodidar.test/api/connect/instagram/callback"]
    return q["state"][0]


def _callback(client, state, code="GOOD-CODE", **extra):
    r = client.get("/api/connect/instagram/callback", params={"code": code, "state": state, **extra}, follow_redirects=False)
    assert r.status_code == 302
    return r.headers["location"]


def test_consent_text_is_shown_first(client, instagram):
    c = client.get("/api/connect/instagram/consent").json()
    assert c["text"].startswith("We can see: your profile, posts, reach and audience age/gender/city.")
    assert "We can't: post, read your DMs or see your password." in c["text"]


def test_start_needs_a_creator_session(client, login, instagram):
    assert client.get("/api/connect/instagram/start?json=1").status_code == 401
    assert login("br_thalam").get("/api/connect/instagram/start?json=1").status_code == 403


def test_full_connection_encrypts_the_token_and_syncs(client, login, instagram, db):
    b = login("cr_b")
    location = _callback(client, _start(b))
    assert location == "https://jodidar.test/creator/connections?ig=connected"
    conn = db.connections.find_one({"creator_id": "cr_b", "platform": "instagram"})
    assert conn["token_enc"] != LONG and LONG not in str(conn) and ig.crypto.decrypt(conn["token_enc"]) == LONG
    assert conn["scopes"] == ig.SCOPES and conn["expires_at"] > time.time() + 59 * 86400
    data = b.get("/api/creators/cr_b/instagram").json()
    assert LONG not in str(data) and "token" not in str(data).lower().replace("tokens", "")
    acct = data["account"]
    assert acct["username"] == "meera.kitchen" and acct["source"] == "instagram_api" and acct["fetched_at"]
    assert acct["reach_28d"] == 61_000 and acct["demographics"]["gender"] == {"F": 700, "M": 300}
    assert data["status"]["status"] == "connected"
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "instagram", "source": "instagram_api"}) == 5
    # Connected reels now drive the profile: real views, saves and shares.
    c = db.creators.find_one({"_id": "cr_b"})
    assert c["insights_source"] == "instagram_api" and c["provenance"]["reels"] == "real" and len(c["reels"]) == 5
    assert c["reels"][0]["views"] == 9_000 and c["reels"][0]["saves"] == 300 and c["reels"][0]["topic"] == "Breakfast"
    assert c["audience"]["cities"][0]["name"] == "Chennai" and c["provenance"]["audience"] == "real"
    assert c["followers"] == 5_400
    fp = b.get("/api/creators/cr_b/fair-price").json()
    assert fp["data_label"] == "Estimate from Instagram data" and fp["estimate"]["low"] < fp["estimate"]["high"]


def test_state_is_signed_single_use_short_lived_and_tied_to_the_account(client, login, instagram, db):
    b = login("cr_b")
    state = _start(b)
    nonce, _, sig = state.partition(".")
    assert "msg=" in _callback(client, f"{nonce}.{'0' * 32}")  # forged signature
    assert "connected" in _callback(client, state)
    assert "already%20used" in _callback(client, state)  # single use
    state2 = _start(b)
    db.oauth_states.update_one({"_id": state2.split(".")[0]}, {"$set": {"expires": time.time() - 1}})
    assert "took%20too%20long" in _callback(client, state2)
    # Another signed-in account can't finish someone else's connection.
    state3 = _start(b)
    other = TestClient(app, headers=APP_HEADER)
    other.post("/api/auth/signup", json={"email": "x@example.com", "password": "long enough", "name": "X", "role": "creator"})
    r = other.get("/api/connect/instagram/callback", params={"code": "GOOD-CODE", "state": state3}, follow_redirects=False)
    assert "another%20account" in r.headers["location"]


def test_cancelled_login_connects_nothing(client, login, instagram, db):
    location = _callback(client, _start(login("cr_b")), code="", error="access_denied", error_reason="user_denied")
    assert "cancelled" in location and db.connections.count_documents({}) == 0


def test_small_accounts_get_no_demographics_and_say_why(client, login, instagram, db):
    instagram.followers = 60
    _callback(client, _start(login("cr_b")))
    acct = db.creators.find_one({"_id": "cr_b"})["channels"]["instagram"]
    assert acct["demographics"] is None and any("at least 100 followers" in n for n in acct["notes"])


def test_personal_accounts_are_told_to_switch(client, login, instagram, db):
    instagram.account_type = "PERSONAL"
    location = _callback(client, _start(login("cr_b")))
    assert "personal%20Instagram%20account" in location


def test_expired_token_marks_the_connection_and_asks_to_reconnect(client, login, instagram, db):
    b = login("cr_b")
    _callback(client, _start(b))
    instagram.expired = True
    r = b.post("/api/connect/instagram/sync")
    assert r.status_code == 409 and "Reconnect" in r.json()["detail"]
    assert db.connections.find_one({"creator_id": "cr_b"})["status"] == "expired"
    assert b.get("/api/creators/cr_b/connections").json()["platforms"][0]["status"] == "expired"


def test_rate_limits_are_a_clear_message(client, login, instagram):
    b = login("cr_b")
    _callback(client, _start(b))
    instagram.rate_limited = True
    r = b.post("/api/connect/instagram/sync")
    assert r.status_code == 429 and "limiting" in r.json()["detail"]


def test_tokens_near_expiry_are_refreshed(client, login, instagram, db):
    _callback(client, _start(login("cr_b")))
    now = time.time()
    db.connections.update_one({"creator_id": "cr_b"}, {"$set": {"refreshed_at": now - 2 * 86400, "expires_at": now + 5 * 86400}})
    assert ig.refresh_due() == 1
    conn = db.connections.find_one({"creator_id": "cr_b"})
    assert ig.crypto.decrypt(conn["token_enc"]) == LONG + "-refreshed" and conn["expires_at"] > now + 50 * 86400
    assert ig.refresh_due() == 0  # just refreshed


def test_disconnect_deletes_token_and_instagram_data(client, login, instagram, db):
    b = login("cr_b")
    before = db.creators.find_one({"_id": "cr_b"})
    _callback(client, _start(b))
    r = b.post("/api/connect/instagram/disconnect")
    assert r.status_code == 200 and r.json()["account"] is None
    assert db.connections.count_documents({"platform": "instagram"}) == 0
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "instagram"}) == 0
    assert db.metric_snapshots.count_documents({"creator_id": "cr_b", "platform": "instagram"}) == 0
    after = db.creators.find_one({"_id": "cr_b"})
    assert after["reels"] == before["reels"] and after["followers"] == before["followers"] and "pre_instagram" not in after
    assert after["insights_connected"]["instagram"] is False


def test_deal_post_is_checked_against_the_connected_account(client, login, instagram, db):
    b, thalam = login("cr_b"), login("br_thalam")
    _callback(client, _start(b))
    r = thalam.post("/api/offers", json={"creator_id": "cr_b", "listing_id": "lst_thalam_sambar", "amount": 2000})
    deal = r.json()["id"]
    b.post(f"/api/deals/{deal}/action", json={"action": "accept"})
    thalam.post(f"/api/deals/{deal}/action", json={"action": "sign"})
    db.deals.update_one({"_id": deal}, {"$set": {"contract.signed_by_creator": "2020-01-01T00:00:00+05:30", "contract.signed_by_brand": "2020-01-01T00:00:00+05:30"}})
    thalam.post(f"/api/deals/{deal}/pay")
    v = b.post(f"/api/deals/{deal}/action", json={"action": "submit_post", "url": "https://www.instagram.com/reel/CODE0/"}).json()
    checks = {c["label"]: c["status"] for c in v["post_check"]["checks"]}
    assert v["post_check"]["source"] == "instagram_api" and v["post_check"]["checked_at"]
    assert checks["Posted on the creator's connected account"] == "passed"
    assert checks["Posted after the contract was signed"] == "passed"
    assert checks["The caption mentions the brand"] == "passed"  # "@thalamfoods"
    assert checks["Paid-partnership label added"] == "not_checked"
    # A link that isn't on the connected account fails that check; the brand still decides.
    thalam.post(f"/api/deals/{deal}/action", json={"action": "request_revision", "note": "Use the right reel"})
    v = b.post(f"/api/deals/{deal}/action", json={"action": "submit_post", "url": "https://www.instagram.com/reel/NOTMINE/"}).json()
    assert {c["label"]: c["status"] for c in v["post_check"]["checks"]}["Posted on the creator's connected account"] == "failed"
    assert any(a["id"] == "approve" for a in thalam.get(f"/api/deals/{deal}").json()["actions"])


# ------------------------------------------------------------------ Meta's callbacks
def _signed(payload: dict, secret: str = "secret456") -> str:
    import base64
    import hashlib
    import hmac
    import json

    body = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
    sig = base64.urlsafe_b64encode(hmac.new(secret.encode(), body.encode(), hashlib.sha256).digest()).decode().rstrip("=")
    return f"{sig}.{body}"


def _meta():
    # Meta posts a form, with no session and no app header.
    return TestClient(app)


def test_meta_callbacks_check_the_signature(instagram, db):
    meta = _meta()
    forged = _signed({"algorithm": "HMAC-SHA256", "user_id": "17841400000000001"}, secret="not-the-secret")
    assert meta.post("/api/connect/instagram/deauthorize", data={"signed_request": forged}).status_code == 403
    assert meta.post("/api/connect/instagram/data-deletion", data={"signed_request": "garbage"}).status_code == 400
    no_user = _signed({"algorithm": "HMAC-SHA256"})
    assert meta.post("/api/connect/instagram/data-deletion", data={"signed_request": no_user}).status_code == 400
    assert meta.post("/api/connect/instagram/data-deletion").status_code == 422


def test_deauthorize_removes_the_token_and_instagram_data(client, login, instagram, db):
    b = login("cr_b")
    _callback(client, _start(b))
    ig_id = db.connections.find_one({"creator_id": "cr_b", "platform": "instagram"})["ig_user_id"]
    r = _meta().post("/api/connect/instagram/deauthorize", data={"signed_request": _signed({"algorithm": "HMAC-SHA256", "user_id": ig_id, "issued_at": 1})})
    assert r.status_code == 200
    assert db.connections.count_documents({"platform": "instagram"}) == 0
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "instagram"}) == 0
    assert db.creators.find_one({"_id": "cr_b"})["insights_connected"]["instagram"] is False
    assert db.audit.find_one({"action": "instagram_deauthorized", "user_id": b.user["id"]})


def test_data_deletion_deletes_unlinks_and_gives_a_status_page(client, login, instagram, db):
    b = login("cr_b")
    _callback(client, _start(b))
    ig_id = db.connections.find_one({"creator_id": "cr_b", "platform": "instagram"})["ig_user_id"]
    db.users.update_one({"_id": b.user["id"]}, {"$set": {"instagram_uid": ig_id}})
    r = _meta().post("/api/connect/instagram/data-deletion", data={"signed_request": _signed({"algorithm": "HMAC-SHA256", "user_id": ig_id})})
    assert r.status_code == 200
    body = r.json()
    code = body["confirmation_code"]
    assert body["url"] == f"https://jodidar.test/api/data-deletion?code={code}"
    assert db.connections.count_documents({"platform": "instagram"}) == 0
    assert "instagram_uid" not in db.users.find_one({"_id": b.user["id"]})
    rec = db.data_deletions.find_one({"_id": code})
    assert rec["status"] == "completed" and rec["found"] is True and ig_id not in str(rec)
    page = client.get("/api/data-deletion", params={"code": code})
    assert page.status_code == 200 and "Your Instagram data was deleted" in page.text and code in page.text
    assert client.get("/api/data-deletion", params={"code": "nope"}).status_code == 404


def test_data_deletion_for_an_unknown_account_still_confirms(instagram, db):
    r = _meta().post("/api/connect/instagram/data-deletion", data={"signed_request": _signed({"algorithm": "HMAC-SHA256", "user_id": "999"})})
    assert r.status_code == 200
    assert db.data_deletions.find_one({"_id": r.json()["confirmation_code"]})["found"] is False


def test_meta_callbacks_say_when_instagram_isnt_set_up(db):
    r = _meta().post("/api/connect/instagram/deauthorize", data={"signed_request": _signed({"algorithm": "HMAC-SHA256", "user_id": "1"})})
    assert r.status_code == 503
