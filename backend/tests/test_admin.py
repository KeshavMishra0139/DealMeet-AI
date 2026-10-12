"""The admin console: server-only role, reasons on every action, audit, and user reports."""
import dataclasses
import time

import pytest

from app.services import admin as adm

WHY = "Reported for fake follower numbers twice."


# ------------------------------------------------------------------ who can use it
@pytest.mark.parametrize(
    "method,path",
    [
        ("GET", "/api/admin/overview"),
        ("GET", "/api/admin/accounts"),
        ("POST", "/api/admin/accounts/us_cr_b/suspend"),
        ("GET", "/api/admin/campaigns"),
        ("POST", "/api/admin/campaigns/lst_senpai_hoodie/close"),
        ("GET", "/api/admin/reports"),
        ("GET", "/api/admin/audit"),
    ],
)
def test_admin_routes_are_admin_only(client, login, method, path):
    assert client.request(method, path, json={"reason": WHY}).status_code == 401
    for persona in ("cr_a", "br_senpai"):
        assert login(persona).client.request(method, path, json={"reason": WHY}, headers=login(persona).headers).status_code == 403


def test_overview_shows_what_needs_attention(admin, db):
    for _ in range(5):
        db.login_failures.insert_one({"_id": f"lf{_}", "email": "someone@example.com", "at": time.time()})
    db.connections.insert_one({"_id": "cn_x", "creator_id": "cr_a", "user_id": "us_cr_a", "platform": "instagram", "status": "error", "last_error": "Token expired"})
    o = admin.get("/api/admin/overview").json()
    assert o["accounts"]["by_role"]["creator"] >= 2 and o["accounts"]["by_role"]["admin"] >= 1
    assert {"email": "someone@example.com", "failures": 5} in o["locked"]
    assert any(e["error"] == "Token expired" for e in o["connection_errors"])
    assert o["campaigns"]["live"] >= 1 and o["health"]["status"] == "ok"
    assert "payments" in o and o["reports"]["open"] == 0


# ------------------------------------------------------------------ suspend / restore
def test_suspending_needs_a_reason_signs_out_and_is_audited(admin, login, db):
    b = login("cr_b")
    assert b.get("/api/auth/me").status_code == 200
    assert admin.post("/api/admin/accounts/us_cr_b/suspend", json={}).status_code == 422
    assert admin.post("/api/admin/accounts/us_cr_b/suspend", json={"reason": "bad"}).status_code == 422
    assert admin.post("/api/admin/accounts/us_nobody/suspend", json={"reason": WHY}).status_code == 404
    r = admin.post("/api/admin/accounts/us_cr_b/suspend", json={"reason": WHY}).json()
    assert r["suspended"] is True and r["suspended_reason"] == WHY
    assert b.get("/api/auth/me").status_code == 401  # signed out everywhere
    assert login_refused(b.client)
    assert db.audit.find_one({"action": "admin_suspend", "target_user": "us_cr_b", "reason": WHY, "user_id": admin.user["id"]})
    listed = admin.get("/api/admin/accounts", params={"suspended": "true"}).json()["items"]
    assert [u["_id"] for u in listed] == ["us_cr_b"]
    assert not any(k in str(listed) for k in ("password_hash", "firebase_uid"))
    assert admin.post("/api/admin/accounts/us_cr_b/restore", json={"reason": "Checked: the numbers were real."}).json()["suspended"] is False
    assert login("cr_b").get("/api/auth/me").status_code == 200
    assert db.audit.find_one({"action": "admin_restore", "target_user": "us_cr_b"})


def login_refused(client) -> bool:
    return client.post("/api/auth/demo", json={"persona": "cr_b", "cookie": False}).status_code == 403


def test_admins_cant_be_suspended_from_the_console(admin):
    assert admin.post(f"/api/admin/accounts/{admin.user['id']}/suspend", json={"reason": WHY}).status_code == 409


def test_account_search(admin):
    items = admin.get("/api/admin/accounts", params={"q": "senpai", "role": "brand"}).json()["items"]
    assert "br_senpai" in [u["brand_id"] for u in items] and all(u["role"] == "brand" and "senpai" in (u["name"] + u["brand_id"]).lower() for u in items)
    assert admin.get("/api/admin/accounts", params={"role": "superuser"}).status_code == 422


# ------------------------------------------------------------------ campaigns
def test_closing_a_campaign_needs_a_reason(admin, client, db):
    rows = admin.get("/api/admin/campaigns", params={"status": "live"}).json()["items"]
    assert "lst_senpai_hoodie" in {r["id"] for r in rows}
    assert admin.post("/api/admin/campaigns/lst_senpai_hoodie/close", json={}).status_code == 422
    assert admin.post("/api/admin/campaigns/lst_nope/close", json={"reason": WHY}).status_code == 404
    assert admin.post("/api/admin/campaigns/lst_senpai_hoodie/close", json={"reason": "Misleading brief."}).json()["status"] == "closed"
    assert db.audit.find_one({"action": "admin_close_campaign", "listing_id": "lst_senpai_hoodie", "reason": "Misleading brief."})
    assert "lst_senpai_hoodie" not in {r["id"] for r in admin.get("/api/admin/campaigns", params={"status": "live"}).json()["items"]}


# ------------------------------------------------------------------ user reports
def test_reports_need_a_session_valid_input_and_a_visible_target(client, login):
    a = login("cr_a")
    body = {"target_type": "campaign", "target_id": "lst_senpai_hoodie", "reason": "scam_or_fraud"}
    assert client.post("/api/reports", json=body).status_code == 401
    assert a.post("/api/reports", json={**body, "reason": "i_dont_like_it"}).status_code == 422
    assert a.post("/api/reports", json={**body, "target_type": "comment"}).status_code == 422
    assert a.post("/api/reports", json={**body, "target_id": "lst_nope"}).status_code == 404
    assert a.post("/api/reports", json={**body, "details": "x" * 501}).status_code == 422
    r = a.post("/api/reports", json={**body, "details": "Asks for a deposit first."}).json()
    assert r["status"] == "open" and r["duplicate"] is False
    assert a.post("/api/reports", json=body).json() == {**r, "duplicate": True}
    assert login("br_senpai").post("/api/reports", json=body).status_code == 409  # not your own


def test_profiles_can_be_reported_but_not_your_own(login):
    a = login("cr_a")
    assert a.post("/api/reports", json={"target_type": "profile", "target_id": "cr_b", "reason": "fake_numbers"}).status_code == 200
    assert a.post("/api/reports", json={"target_type": "profile", "target_id": "cr_a", "reason": "fake_numbers"}).status_code == 409
    assert a.post("/api/reports", json={"target_type": "profile", "target_id": "br_thalam", "reason": "spam"}).status_code == 200


def test_deals_only_by_their_parties(login):
    body = {"target_type": "deal", "target_id": "dl_a_senpai", "reason": "harassment"}
    assert login("cr_b").post("/api/reports", json=body).status_code == 403
    assert login("br_thalam").post("/api/reports", json=body).status_code == 403
    assert login("cr_a").post("/api/reports", json=body).status_code == 200
    assert login("br_senpai").post("/api/reports", json=body).status_code == 200


def test_pitches_only_by_the_brand_they_were_sent_to(login):
    b = login("cr_b")
    d = b.post("/api/creators/cr_b/pitches", json={"brand_id": "br_thalam", "lang": "en"}).json()
    body = {"target_type": "pitch", "target_id": d["id"], "reason": "spam"}
    assert login("br_thalam").post("/api/reports", json=body).status_code == 404  # still a draft
    b.post(f"/api/creators/cr_b/pitches/{d['id']}/send")
    assert login("br_senpai").post("/api/reports", json=body).status_code == 404
    assert login("br_thalam").post("/api/reports", json=body).status_code == 200


def test_five_reports_a_day(login):
    a = login("cr_a")
    targets = ["cr_b", "br_thalam", "br_senpai", "cr_g01", "cr_g02", "cr_g05"]
    codes = [a.post("/api/reports", json={"target_type": "profile", "target_id": t, "reason": "spam"}).status_code for t in targets]
    assert codes == [200] * adm.REPORTS_PER_DAY + [429]


def test_resolving_a_report_needs_a_reason(admin, login, db):
    a = login("cr_a")
    rid = a.post("/api/reports", json={"target_type": "profile", "target_id": "cr_b", "reason": "fake_numbers"}).json()["id"]
    login("br_thalam").post("/api/reports", json={"target_type": "profile", "target_id": "cr_b", "reason": "fake_numbers"})
    o = admin.get("/api/admin/overview").json()
    assert o["reports"]["open"] == 2 and {"profile_id": "cr_b", "open_reports": 2} in o["suspicious"]
    assert admin.get("/api/admin/reports").json()["items"][0]["target_id"] == "cr_b"
    url = f"/api/admin/reports/{rid}/resolve"
    assert a.post(url, json={"resolution": "no_action", "reason": WHY}).status_code == 403
    assert admin.post(url, json={"resolution": "no_action"}).status_code == 422
    assert admin.post(url, json={"resolution": "banned", "reason": WHY}).status_code == 422
    done = admin.post(url, json={"resolution": "no_action", "reason": "Numbers match their connected account."}).json()
    assert done["status"] == "resolved" and done["resolution"] == "no_action"
    assert admin.post(url, json={"resolution": "no_action", "reason": WHY}).status_code == 409
    assert admin.post("/api/admin/reports/rp_nope/resolve", json={"resolution": "no_action", "reason": WHY}).status_code == 404
    assert db.audit.find_one({"action": "admin_resolve_report", "report_id": rid})


# ------------------------------------------------------------------ audit log
def test_audit_viewer_filters_and_never_shows_secrets(admin, client, login, db):
    since = time.time()
    c = client.__class__(client.app, headers=dict(client.headers))
    c.post("/api/auth/signup", json={"email": "aud@example.com", "password": "very secret words", "name": "Aud", "role": "creator"})
    admin.post("/api/admin/accounts/us_cr_b/suspend", json={"reason": WHY})
    db.audit.insert_one({"_id": "ev_planted", "ts": time.time(), "action": "planted", "user_id": None, "token": "tok_should_not_show", "nested": {"key_secret": "s3cr3t"}})
    day = time.strftime("%Y-%m-%d", time.gmtime(since))
    items = admin.get("/api/admin/audit", params={"since": day}).json()["items"]
    actions = {e["action"] for e in items}
    assert {"signup", "admin_suspend", "planted"} <= actions
    blob = str(items)
    assert "very secret words" not in blob and "tok_should_not_show" not in blob and "s3cr3t" not in blob
    only = admin.get("/api/admin/audit", params={"action": "admin_", "user_id": admin.user["id"]}).json()["items"]
    assert only and all(e["action"].startswith("admin_") and e["user_id"] == admin.user["id"] for e in only)
    assert admin.get("/api/admin/audit", params={"since": "yesterday"}).status_code == 422
    assert admin.get("/api/admin/audit", params={"action": "a.*"}).status_code == 422
    assert admin.get("/api/admin/audit", params={"limit": 501}).status_code == 422


def test_redact_is_recursive():
    out = adm.redact({"action": "x", "password_hash": "h", "detail": {"access_token": "t", "ok": 1}, "ts": 1.0})
    assert out == {"action": "x", "password_hash": "[redacted]", "detail": {"access_token": "[redacted]", "ok": 1}, "ts": 1.0}


# ------------------------------------------------------------------ demo admin persona
def test_demo_admin_is_off_unless_the_server_turns_it_on(client, db, monkeypatch):
    from app import config
    from app.routers import auth as auth_router
    from app.seed import load

    assert "demo_admin" not in {p["id"] for p in client.get("/api/auth/personas").json()}
    assert client.post("/api/auth/demo", json={"persona": "demo_admin", "cookie": False}).status_code == 404
    on = dataclasses.replace(config.get_settings(), demo_admin=True)
    monkeypatch.setattr(auth_router, "get_settings", lambda: on)
    monkeypatch.setattr(load, "get_settings", lambda: on)
    load.seed_all(db, force=True)
    assert "demo_admin" in {p["id"] for p in client.get("/api/auth/personas").json()}
    r = client.post("/api/auth/demo", json={"persona": "demo_admin", "cookie": False}).json()
    assert r["user"]["role"] == "admin"
    assert client.get("/api/admin/overview", headers={"Authorization": f"Bearer {r['token']}"}).status_code == 200


def test_demo_admin_never_on_a_shared_demo(monkeypatch):
    from app import config

    for env, expected in (({"DEMO_MODE": "1", "DEMO_ADMIN": "1", "DEMO_RESET_MINUTES": "0"}, True),
                          ({"DEMO_MODE": "1", "DEMO_ADMIN": "1", "DEMO_RESET_MINUTES": "30"}, False),
                          ({"DEMO_MODE": "0", "DEMO_ADMIN": "1", "DEMO_RESET_MINUTES": "0"}, False)):
        for k, v in env.items():
            monkeypatch.setenv(k, v)
        config.get_settings.cache_clear()
        assert config.get_settings().demo_admin is expected
    monkeypatch.undo()
    config.get_settings.cache_clear()
