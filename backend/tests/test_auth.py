"""Accounts, sessions and server-side permissions."""
import re
import time

import pytest
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient

from app.main import app
from app.services import auth as au

from conftest import APP_HEADER

# Routes anyone may call without signing in.
PUBLIC = {
    ("GET", "/api/health"),
    ("GET", "/api/meta"),
    ("POST", "/api/auth/signup"),
    ("POST", "/api/auth/login"),
    ("POST", "/api/auth/firebase"),
    ("POST", "/api/auth/logout"),
    ("GET", "/api/auth/personas"),
    ("POST", "/api/auth/demo"),
    ("POST", "/api/demo/reset"),
    ("GET", "/api/demo/compare"),
    ("GET", "/api/public/{handle}"),
    ("POST", "/api/public/{handle}/book"),
    ("POST", "/api/payments/razorpay/webhook"),  # proves itself with Razorpay's signature
    ("POST", "/api/youtube/preview"),  # public, rate-limited per IP
    ("GET", "/api/connect/instagram/consent"),
    ("GET", "/api/connect/instagram/callback"),  # proves itself with the signed, single-use state
    ("GET", "/api/directory/brands"),  # the public brand directory
    ("GET", "/api/directory/facets"),
    ("GET", "/api/directory/brands/{slug}"),
    ("POST", "/api/directory/brands/{slug}/removal-request"),  # anyone may ask; rate-limited per IP
}


def _private_routes():
    for r in app.routes:
        if not isinstance(r, APIRoute) or not r.path.startswith("/api/"):
            continue
        for m in r.methods - {"HEAD", "OPTIONS"}:
            if (m, r.path) not in PUBLIC:
                yield m, r.path


def _fill(path: str) -> str:
    return re.sub(r"\{[^}]+\}", "x1", path)


def fresh_client() -> TestClient:
    return TestClient(app, headers=APP_HEADER)


def test_every_private_route_needs_a_session(client, db):
    routes = sorted(set(_private_routes()))
    assert len(routes) > 40
    for method, path in routes:
        r = client.request(method, _fill(path), json={})
        assert r.status_code == 401, (method, path, r.status_code, r.text[:120])


def test_public_routes_are_the_only_open_ones(client, db):
    assert client.get("/api/health").status_code == 200
    assert client.get("/api/public/creator.a").status_code == 200


@pytest.mark.parametrize(
    "who,method,path",
    [
        ("cr_b", "GET", "/api/creators/cr_a"),
        ("cr_b", "GET", "/api/creators/cr_a/home"),
        ("cr_b", "GET", "/api/creators/cr_a/money"),
        ("cr_b", "GET", "/api/creators/cr_a/privacy"),
        ("cr_b", "POST", "/api/creators/cr_a/privacy"),
        ("cr_b", "GET", "/api/creators/cr_a/export"),
        ("cr_b", "GET", "/api/creators/cr_a/kit"),
        ("cr_b", "GET", "/api/creators/cr_a/deals"),
        ("cr_b", "GET", "/api/deals/dl_a_senpai"),
        ("cr_b", "POST", "/api/deals/dl_a_senpai/action"),
        ("br_senpai", "GET", "/api/creators/cr_a/home"),  # a brand isn't the creator
        ("br_thalam", "GET", "/api/brands/br_senpai/console"),
        ("br_thalam", "GET", "/api/brands/br_senpai"),
        ("br_thalam", "GET", "/api/listings/lst_senpai_hoodie/matches"),
        ("br_thalam", "POST", "/api/listings/lst_senpai_hoodie/collective"),
        ("br_thalam", "GET", "/api/brands/br_senpai/creators/cr_a"),
        ("br_thalam", "GET", "/api/deals/dl_a_senpai"),
        ("br_thalam", "POST", "/api/deals/dl_a_senpai/pay"),
        ("cr_a", "POST", "/api/deals/dl_a_senpai/pay"),  # only the brand side funds
        ("cr_a", "POST", "/api/brands/br_senpai/campaigns"),
        ("br_senpai", "POST", "/api/offers"),  # another brand's campaign, below
    ],
)
def test_another_accounts_records_are_403(login, who, method, path):
    body = {"action": "accept"} if path.endswith("/action") else {}
    if path == "/api/offers":
        body = {"creator_id": "cr_b", "listing_id": "lst_thalam_sambar", "amount": 1500}
    if path.endswith("/campaigns"):
        body = {"title": "Test campaign", "summary": "A test campaign summary", "niches": ["food"], "languages": ["hi"]}
    r = login(who).client.request(method, path, json=body, headers=login(who).headers)
    assert r.status_code == 403, (who, path, r.text)


def test_deal_side_comes_from_the_session_not_the_body(login, db):
    a = login("cr_a")
    # Creator A can't accept their own counter as the brand.
    a.post("/api/deals/dl_a_senpai/action", json={"action": "counter", "amount": 17000})
    r = a.post("/api/deals/dl_a_senpai/action", json={"role": "brand", "action": "accept_counter"})
    assert r.status_code == 403
    # Without a role, the action runs as the session's side; a brand-only action is refused.
    assert a.post("/api/deals/dl_a_senpai/action", json={"action": "accept_counter"}).status_code == 400
    assert db.deals.find_one({"_id": "dl_a_senpai"})["stage"] == "offer"


def test_signup_signin_signout_with_a_cookie(db):
    c = fresh_client()
    r = c.post("/api/auth/signup", json={"email": "Meera@Example.com", "password": "correct horse", "name": "Meera", "role": "creator"})
    assert r.status_code == 200, r.text
    assert "token" not in r.json()  # the browser keeps it in an HttpOnly cookie
    cookie = r.headers["set-cookie"]
    assert "httponly" in cookie.lower() and "samesite=lax" in cookie.lower()
    me = c.get("/api/auth/me").json()
    assert me["user"]["role"] == "creator" and me["user"]["email"] == "meera@example.com" and me["user"]["creator_id"] is None
    assert "password_hash" not in str(me)
    user = db.users.find_one({"email": "meera@example.com"})
    assert user["password_hash"].startswith("scrypt$") and "correct horse" not in str(user)
    assert c.post("/api/auth/logout").status_code == 200
    assert c.get("/api/auth/me").status_code == 401
    # Only the token's hash is stored.
    assert all(len(s["_id"]) == 64 for s in db.sessions.find({"user_id": user["_id"]}))
    assert c.post("/api/auth/login", json={"email": "meera@example.com", "password": "correct horse"}).status_code == 200
    assert c.get("/api/auth/me").status_code == 200


def test_signup_validation_and_duplicates(db):
    c = fresh_client()
    ok = {"email": "dup@example.com", "password": "long enough", "name": "Dup", "role": "brand"}
    assert c.post("/api/auth/signup", json=ok).status_code == 200
    assert c.post("/api/auth/signup", json=ok).status_code == 409
    assert c.post("/api/auth/signup", json={**ok, "email": "x@y.z", "role": "admin"}).status_code == 422  # admin is server-only
    assert c.post("/api/auth/signup", json={**ok, "email": "short@y.z", "password": "short"}).status_code == 422
    assert c.post("/api/auth/signup", json={**ok, "email": "not-an-email"}).status_code == 422


def test_wrong_passwords_are_throttled(db):
    c = fresh_client()
    c.post("/api/auth/signup", json={"email": "t@example.com", "password": "right password", "name": "T", "role": "creator"})
    for _ in range(au.MAX_FAILED_LOGINS):
        assert c.post("/api/auth/login", json={"email": "t@example.com", "password": "wrong"}).status_code == 401
    assert c.post("/api/auth/login", json={"email": "t@example.com", "password": "right password"}).status_code == 429


def test_expired_and_revoked_sessions_are_rejected(client, login, db):
    a = login("cr_a")
    assert a.get("/api/creators/cr_a/home").status_code == 200
    db.sessions.update_one({"_id": au.hash_token(a.token)}, {"$set": {"expires_at": int(time.time()) - 1}})
    r = a.get("/api/creators/cr_a/home")
    assert r.status_code == 401 and "expired" in r.json()["detail"]
    b = login("cr_b")
    client.post("/api/auth/logout", headers=b.headers)
    assert b.get("/api/creators/cr_b/home").status_code == 401


def test_sessions_expire_after_72_hours(login, db):
    a = login("cr_a")
    s = db.sessions.find_one({"_id": au.hash_token(a.token)})
    assert s["expires_at"] - s["created_at"] == 72 * 3600


def test_suspended_accounts_are_refused(login, db):
    a = login("cr_a")
    db.users.update_one({"_id": a.user["id"]}, {"$set": {"suspended": True}})
    assert a.get("/api/creators/cr_a/home").status_code == 403


def test_cookie_writes_need_the_app_header(db):
    c = TestClient(app)  # no X-Requested-With
    r = c.post("/api/auth/signup", json={"email": "csrf@example.com", "password": "long enough", "name": "C", "role": "creator"})
    assert r.status_code == 403
    c.headers.update(APP_HEADER)
    assert c.post("/api/auth/signup", json={"email": "csrf@example.com", "password": "long enough", "name": "C", "role": "creator"}).status_code == 200
    del c.headers["X-Requested-With"]
    assert c.post("/api/creators/cr_a/privacy", json={}).status_code == 403  # cookie alone can't write


def test_onboarding_links_the_profile_to_the_account_once(login, db):
    me = login("new_creator")
    body = {"name": "Linked", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["ta"], "city": "Chennai"}
    cid = me.post("/api/creators", json=body).json()["id"]
    assert db.users.find_one({"_id": me.user["id"]})["creator_id"] == cid
    assert me.get(f"/api/creators/{cid}/home").status_code == 200
    assert me.post("/api/creators", json=body).status_code == 409
    assert login("new_brand").post("/api/creators", json=body).status_code == 403  # brands can't make creator profiles


def test_writes_and_sign_ins_are_audited_without_secrets(login, db):
    db.audit.delete_many({})
    c = fresh_client()
    c.post("/api/auth/signup", json={"email": "audit@example.com", "password": "secret words", "name": "A", "role": "creator"})
    login("cr_b").post("/api/creators/cr_b/privacy", json={"discoverable": True})
    actions = [e["action"] for e in db.audit.find({})]
    assert "signup" in actions and "signin" in actions and "write" in actions
    write = db.audit.find_one({"action": "write", "path": "/api/creators/cr_b/privacy"})
    assert write["user_id"] == "us_cr_b" and write["status"] == 200
    assert "secret words" not in str(list(db.audit.find({})))


def test_demo_routes_are_off_outside_demo_mode(client, db, monkeypatch):
    from app import config

    monkeypatch.setenv("DEMO_MODE", "0")
    config.get_settings.cache_clear()
    try:
        assert client.get("/api/auth/personas").status_code == 404
        assert client.post("/api/auth/demo", json={"persona": "cr_a"}).status_code == 404
        assert client.post("/api/demo/reset").status_code == 404
        assert client.get("/api/health").json()["demo_mode"] is False
        # Without demo mode a visitor signs in before booking.
        r = client.post("/api/public/creator.b/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 2000})
        assert r.status_code == 401
    finally:
        monkeypatch.delenv("DEMO_MODE")
        config.get_settings.cache_clear()


def test_demo_reset_keeps_persona_sessions_and_drops_sandbox_accounts(client, login, db):
    a = login("cr_a")
    new = login("new_creator")
    client.post("/api/demo/reset")
    assert a.get("/api/creators/cr_a/home").status_code == 200
    assert new.get("/api/auth/me").status_code == 401
    assert db.users.find_one({"_id": new.user["id"]}) is None


def test_admin_is_granted_only_from_the_server(db):
    from app import admin_cli

    c = fresh_client()
    c.post("/api/auth/signup", json={"email": "ops@example.com", "password": "long enough", "name": "Ops", "role": "creator"})
    assert admin_cli.main(["grant", "nobody@example.com"]) == 1
    assert admin_cli.main(["grant", "ops@example.com"]) == 0
    assert c.get("/api/auth/me").status_code == 401  # granting signs the account out
    c.post("/api/auth/login", json={"email": "ops@example.com", "password": "long enough"})
    assert c.get("/api/auth/me").json()["user"]["role"] == "admin"
    assert admin_cli.main(["revoke", "ops@example.com"]) == 0
    assert db.users.find_one({"email": "ops@example.com"})["role"] == "creator"
