"""Acceptance checks across areas: no session, an expired session, another account,
invalid input, and a new marketplace with no data (demo mode off).

Each area's own suite covers its happy path, failed external calls and duplicate
requests; this file checks the same guarantees hold across all of them."""
import time

import pytest

from app.services import auth as au

# (area, method, path, a valid-looking body, the owner persona, a persona that isn't the owner)
AREAS = [
    ("profile", "PATCH", "/api/creators/cr_a/profile", {"bio": "Anime edits in Hindi."}, "cr_a", "cr_b"),
    ("campaigns", "PATCH", "/api/campaigns/lst_senpai_hoodie", {"title": "Winter drop: anime hoodies"}, "br_senpai", "br_thalam"),
    ("campaign status", "POST", "/api/campaigns/lst_senpai_hoodie/status", {"action": "pause"}, "br_senpai", "br_thalam"),
    ("matching", "GET", "/api/listings/lst_senpai_hoodie/matches", None, "br_senpai", "br_thalam"),
    ("shortlist", "PUT", "/api/campaigns/lst_senpai_hoodie/shortlist/cr_g01", {}, "br_senpai", "br_thalam"),
    ("contracts", "POST", "/api/deals/dl_a_senpai/action", {"action": "decline"}, "cr_a", "cr_b"),
    ("payments", "POST", "/api/deals/dl_a_senpai/pay", {}, "br_senpai", "br_thalam"),
    ("rates", "PUT", "/api/creators/cr_a/rates/reel", {"amount": 9000}, "cr_a", "cr_b"),
    ("media kit", "POST", "/api/creators/cr_a/kit/versions", {}, "cr_a", "cr_b"),
    ("pitches", "POST", "/api/creators/cr_b/pitches", {"brand_id": "br_thalam", "lang": "en"}, "cr_b", "cr_a"),
    ("dream brands", "PUT", "/api/creators/cr_a/dream-brands/br_thalam", {}, "cr_a", "cr_b"),
    ("brand profile", "PATCH", "/api/brands/br_senpai/profile", {"description": "Anime merch."}, "br_senpai", "br_thalam"),
    ("youtube link", "POST", "/api/creators/cr_a/youtube/link", {"handle": "@someone"}, "cr_a", "cr_b"),
    ("instagram oauth", "GET", "/api/connect/instagram/start", None, "cr_a", None),
    ("assistant tools", "POST", "/api/assistant/tools/explain_price", {"args": {}}, "cr_a", None),
    ("reports", "POST", "/api/reports", {"target_type": "profile", "target_id": "cr_b", "reason": "spam"}, "cr_a", None),
    ("admin", "GET", "/api/admin/overview", None, None, "cr_a"),
]
IDS = [a[0] for a in AREAS]


def _send(client, method, path, body, headers=None):
    return client.request(method, path, json=body if body is not None else None, headers=headers or {})


@pytest.mark.parametrize("area,method,path,body,owner,other", AREAS, ids=IDS)
def test_no_session_is_401(client, db, area, method, path, body, owner, other):
    assert _send(client, method, path, body).status_code == 401


@pytest.mark.parametrize("area,method,path,body,owner,other", AREAS, ids=IDS)
def test_an_expired_session_is_401(client, db, area, method, path, body, owner, other):
    user = db.users.find_one({"creator_id": owner} if (owner or "").startswith("cr_") else {"brand_id": owner}) if owner else au.new_user("admin", "Ops")
    token = au.create_session(user["_id"], "test")
    db.sessions.update_one({"_id": au.hash_token(token)}, {"$set": {"expires_at": time.time() - 1}})
    r = _send(client, method, path, body, {"Authorization": f"Bearer {token}"})
    assert r.status_code == 401 and "expired" in r.json()["detail"]


@pytest.mark.parametrize("area,method,path,body,owner,other", [a for a in AREAS if a[5]], ids=[a[0] for a in AREAS if a[5]])
def test_another_account_is_403(login, area, method, path, body, owner, other):
    a = login(other)
    assert _send(a.client, method, path, body, a.headers).status_code == 403


INVALID = [
    ("cr_a", "PATCH", "/api/creators/cr_a/profile", {"bio": "x" * 5000}),
    ("br_senpai", "PATCH", "/api/campaigns/lst_senpai_hoodie", {"title": ""}),
    ("br_senpai", "POST", "/api/campaigns/lst_senpai_hoodie/status", {"action": "explode"}),
    ("cr_a", "POST", "/api/deals/dl_a_senpai/action", {"action": "counter", "amount": -5}),
    ("cr_a", "PUT", "/api/creators/cr_a/rates/reel", {"amount": "lots"}),
    ("cr_a", "PUT", "/api/creators/cr_a/rates/billboard", {"amount": 9000}),
    ("cr_b", "POST", "/api/creators/cr_b/pitches", {"brand_id": "br_thalam", "lang": "klingon"}),
    ("cr_a", "POST", "/api/creators/cr_a/youtube/link", {"handle": "not a handle!"}),
    ("cr_a", "POST", "/api/reports", {"target_type": "profile", "target_id": "cr_b", "reason": "dislike"}),
    ("br_senpai", "PATCH", "/api/brands/br_senpai/profile", {"website": "javascript:alert(1)"}),
]


@pytest.mark.parametrize("persona,method,path,body", INVALID, ids=[f"{m} {p}" for _, m, p, _ in INVALID])
def test_invalid_input_is_a_clear_4xx(login, persona, method, path, body):
    a = login(persona)
    r = _send(a.client, method, path, body, a.headers)
    assert r.status_code in (400, 404, 409, 422) and r.json().get("detail")


# ------------------------------------------------------------------ demo mode off, nothing seeded
def test_a_new_marketplace_with_no_listings_works(client, db):
    """Outside demo mode nothing is seeded: a new creator's pages must work with no
    listings at all (the duplicate-listing check used to fail on an empty marketplace)."""
    from app.services import cache
    from fastapi.testclient import TestClient

    from app.main import app

    for name in ("listings", "brands", "deals", "applications"):
        db[name].delete_many({})
    cache.clear_runtime()
    c = TestClient(app, headers={"X-Requested-With": "tests"})
    assert c.post("/api/auth/signup", json={"email": f"new-{time.time()}@example.test", "password": "a long password", "name": "New", "role": "creator"}).status_code == 200
    r = c.post("/api/creators", json={"name": "New Kitchen", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["ta"], "city": "Chennai"})
    assert r.status_code == 200, r.text
    cid = r.json()["id"]
    for path in ("home", "opportunities", "money", "roadmap"):
        assert c.get(f"/api/creators/{cid}/{path}").status_code == 200, path


def test_writes_persist_for_a_new_session(login, client, db):
    """What one session writes, a fresh sign-in reads back from the database."""
    a = login("cr_b")
    assert a.patch("/api/creators/cr_b/profile", json={"bio": "Tamil breakfasts, every morning."}).status_code == 200
    again = login("cr_b")
    assert again.get("/api/creators/cr_b/profile").json()["creator"]["bio"] == "Tamil breakfasts, every morning."
    assert db.creators.find_one({"_id": "cr_b"})["bio"] == "Tamil breakfasts, every morning."
