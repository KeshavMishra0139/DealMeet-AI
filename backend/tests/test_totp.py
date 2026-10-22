"""Two-step sign-in for admins (services/totp.py)."""
import time
import uuid

import pytest
from cryptography.fernet import Fernet

from app import admin_cli, config
from app.services import auth as au
from app.services import totp
from conftest import Actor


@pytest.fixture()
def enc_key(monkeypatch):
    monkeypatch.setenv("TOKEN_ENC_KEY", Fernet.generate_key().decode())
    config.get_settings.cache_clear()
    yield
    config.get_settings.cache_clear()


def new_admin(client, db) -> Actor:
    user = au.new_user("admin", "Ops", email=f"ops-{uuid.uuid4().hex[:6]}@example.test")
    db.rate_limits.delete_many({})
    return Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))


def now_code(secret: str, steps_ahead: int = 0) -> str:
    return totp.code_at(secret, int(time.time() // totp.STEP) + steps_ahead)


def test_rfc6238_reference_codes():
    secret = "GEZDGNBVGY3TQOJQGEZDGNBVGY3TQOJQ"  # "12345678901234567890"
    assert totp.code_at(secret, 59 // 30) == "287082"
    assert totp.code_at(secret, 1111111109 // 30) == "081804"
    assert totp.code_at(secret, 1234567890 // 30) == "005924"
    assert totp.matching_step(secret, "287082", now=59) == 1
    assert totp.matching_step(secret, "287082", now=59 + 90) is None  # too old
    assert totp.matching_step(secret, "287082", now=59, after=1) is None  # already used


def test_admin_console_needs_two_step_sign_in(client, db, enc_key):
    a = new_admin(client, db)
    r = a.get("/api/admin/overview")
    assert r.status_code == 403 and "Turn on two-step sign-in" in r.json()["detail"]
    assert a.get("/api/auth/mfa").json() == {"required": True, "enabled": False, "passed": False, "can_set_up": True, "recovery_codes_left": 0}

    setup = a.post("/api/auth/mfa/setup").json()
    secret = setup["secret"]
    assert setup["uri"].startswith("otpauth://totp/DealMeet%20AI%3A") and f"secret={secret}" in setup["uri"]
    stored = db.users.find_one({"_id": a.user["id"]})
    assert secret not in str(stored)  # encrypted at rest
    assert a.post("/api/auth/mfa/enable", json={"code": "000000" if now_code(secret) != "000000" else "111111"}).status_code == 400
    codes = a.post("/api/auth/mfa/enable", json={"code": now_code(secret)}).json()["recovery_codes"]
    assert len(codes) == 8 and len(set(codes)) == 8
    assert not any(c in str(db.users.find_one({"_id": a.user["id"]})) for c in codes)  # hashes only
    # This session passed while turning it on.
    assert a.get("/api/admin/overview").status_code == 200
    assert a.post("/api/auth/mfa/setup").status_code == 409

    # A new sign-in asks again.
    b = Actor(client, au.create_session(a.user["id"], "test"), a.user)
    r = b.get("/api/admin/overview")
    assert r.status_code == 403 and "Enter the code" in r.json()["detail"]
    # The code used to turn it on can't be used again.
    assert b.post("/api/auth/mfa/verify", json={"code": now_code(secret)}).status_code == 400
    assert b.post("/api/auth/mfa/verify", json={"code": now_code(secret, 1)}).json()["ok"] is True
    assert b.get("/api/admin/overview").status_code == 200

    # A recovery code works once.
    c = Actor(client, au.create_session(a.user["id"], "test"), a.user)
    assert c.post("/api/auth/mfa/verify", json={"code": codes[0].upper()}).json()["recovery_codes_left"] == 7
    assert c.get("/api/admin/overview").status_code == 200
    d = Actor(client, au.create_session(a.user["id"], "test"), a.user)
    assert d.post("/api/auth/mfa/verify", json={"code": codes[0]}).status_code == 400
    actions = {e["action"] for e in db.audit.find({"user_id": a.user["id"]})}
    assert {"admin_2fa_enabled", "admin_2fa_passed", "admin_2fa_failed"} <= actions


def test_wrong_codes_pause_the_check(client, db, enc_key):
    a = new_admin(client, db)
    secret = a.post("/api/auth/mfa/setup").json()["secret"]
    a.post("/api/auth/mfa/enable", json={"code": now_code(secret)})
    b = Actor(client, au.create_session(a.user["id"], "test"), a.user)
    wrong = "abcd-0000"
    assert [b.post("/api/auth/mfa/verify", json={"code": wrong}).status_code for _ in range(5)] == [400] * 5
    # Even the right code waits now.
    assert b.post("/api/auth/mfa/verify", json={"code": now_code(secret, 1)}).status_code == 429


def test_only_admins_and_not_the_demo_admin(client, db, login, enc_key, monkeypatch):
    assert login("cr_a").get("/api/auth/mfa").status_code == 403
    monkeypatch.setenv("DEMO_ADMIN", "1")
    monkeypatch.setenv("DEMO_RESET_MINUTES", "0")
    config.get_settings.cache_clear()
    from app.seed.load import seed_all

    seed_all(db, force=True)  # the demo admin is seeded only with DEMO_ADMIN=1
    r = client.post("/api/auth/demo", json={"persona": "demo_admin", "cookie": False})
    assert r.status_code == 200, r.text
    demo = Actor(client, r.json()["token"], r.json()["user"])
    assert demo.get("/api/auth/mfa").json()["required"] is False
    assert demo.get("/api/admin/overview").status_code == 200
    monkeypatch.delenv("DEMO_ADMIN")
    config.get_settings.cache_clear()
    seed_all(db, force=True)


def test_set_up_needs_the_encryption_key(client, db, monkeypatch):
    monkeypatch.delenv("TOKEN_ENC_KEY", raising=False)
    config.get_settings.cache_clear()
    a = new_admin(client, db)
    assert a.get("/api/auth/mfa").json()["can_set_up"] is False
    r = a.post("/api/auth/mfa/setup")
    assert r.status_code == 503 and "TOKEN_ENC_KEY" in r.json()["detail"]
    config.get_settings.cache_clear()


def test_server_reset_turns_it_off_and_signs_out(client, db, enc_key, capsys):
    a = new_admin(client, db)
    secret = a.post("/api/auth/mfa/setup").json()["secret"]
    a.post("/api/auth/mfa/enable", json={"code": now_code(secret)})
    email = db.users.find_one({"_id": a.user["id"]})["email"]
    assert admin_cli.main(["reset-2fa", email]) == 0
    assert "totp" not in db.users.find_one({"_id": a.user["id"]})
    assert a.get("/api/auth/me").status_code == 401
    # Its data export never holds the secret.
    fresh = new_admin(client, db)
    s2 = fresh.post("/api/auth/mfa/setup").json()["secret"]
    fresh.post("/api/auth/mfa/enable", json={"code": now_code(s2)})
    assert s2 not in fresh.get("/api/auth/export").text
