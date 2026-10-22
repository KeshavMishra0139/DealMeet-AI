"""Signed-in devices, password change, password reset by email and email verification."""
import re
import time
import uuid

from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import auth as au
from app.services import credentials
from conftest import APP_HEADER

PHONE = "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Mobile Safari/537.36"
LAPTOP = "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_6) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.0 Safari/605.1.15"


def browser(ua: str = PHONE) -> TestClient:
    # Lower-case key: TestClient adds "user-agent: testclient" to the dict it's given unless
    # that exact key is there (and the shared APP_HEADER has picked one up that way).
    return TestClient(app, headers={"X-Requested-With": APP_HEADER["X-Requested-With"], "user-agent": ua})


def signup(ua: str = PHONE, password: str = "first password") -> tuple[TestClient, str]:
    c, email = browser(ua), f"asha-{uuid.uuid4().hex[:6]}@example.com"
    assert c.post("/api/auth/signup", json={"email": email, "password": password, "name": "Asha", "role": "creator"}).status_code == 200
    return c, email


def login(email: str, password: str, ua: str = LAPTOP) -> TestClient:
    c = browser(ua)
    assert c.post("/api/auth/login", json={"email": email, "password": password}).status_code == 200
    return c


def link_token(msg, path: str) -> str:
    return re.search(rf"https://dealmeet\.test{path}\?t=([\w-]+)", msg.get_content()).group(1)


# ------------------------------------------------------------------ devices
def test_device_labels():
    assert au.device_label(PHONE) == "Chrome on Android"
    assert au.device_label(LAPTOP) == "Safari on Mac"
    assert au.device_label("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 Edg/130.0") == "Edge on Windows"
    assert au.device_label("python-httpx/0.28") == "An app or script"
    assert au.device_label(None) == "An app or script"


def test_list_devices_and_sign_out_the_others(db):
    phone, email = signup()
    laptop = login(email, "first password")
    items = phone.get("/api/auth/sessions").json()["items"]
    assert [(i["device"], i["current"]) for i in items] == [("Chrome on Android", True), ("Safari on Mac", False)]
    assert all(re.fullmatch(r"[0-9a-f]{16}", i["id"]) and i["via"] == "password" for i in items)
    # Nothing in the list can sign anyone in: the ids are the start of a hash.
    assert not db.sessions.find_one({"_id": items[0]["id"]})

    assert phone.post("/api/auth/sessions/revoke-others").json() == {"revoked": 1}
    assert laptop.get("/api/auth/me").status_code == 401
    assert phone.get("/api/auth/me").status_code == 200
    assert [i["device"] for i in phone.get("/api/auth/sessions").json()["items"]] == ["Chrome on Android"]


def test_sign_out_one_device_and_only_your_own(db):
    phone, email = signup()
    laptop = login(email, "first password")
    other, _ = signup()
    laptop_id = next(i["id"] for i in phone.get("/api/auth/sessions").json()["items"] if not i["current"])
    # Another account can't sign this one's device out.
    assert other.post(f"/api/auth/sessions/{laptop_id}/revoke").status_code == 404
    assert phone.post(f"/api/auth/sessions/{laptop_id}/revoke").status_code == 200
    assert laptop.get("/api/auth/me").status_code == 401
    assert phone.post(f"/api/auth/sessions/{laptop_id}/revoke").status_code == 404
    assert phone.post("/api/auth/sessions/not-an-id/revoke").status_code == 422
    # Signing out this device from the list also clears its cookie.
    mine = phone.get("/api/auth/sessions").json()["items"][0]["id"]
    r = phone.post(f"/api/auth/sessions/{mine}/revoke")
    assert r.status_code == 200 and "jd_session=" in r.headers.get("set-cookie", "")
    assert phone.get("/api/auth/me").status_code == 401
    assert "session_revoked" in {e["action"] for e in db.audit.find({"user_id": {"$exists": True}})}


# ------------------------------------------------------------------ password change
def test_change_password_signs_out_other_devices_and_sends_a_notice(smtp, db):
    phone, email = signup()
    laptop = login(email, "first password")
    assert phone.post("/api/auth/password", json={"current": "wrong one", "new": "second password"}).status_code == 403
    smtp.sent.clear()
    assert phone.post("/api/auth/password", json={"current": "first password", "new": "second password"}).status_code == 200
    assert phone.get("/api/auth/me").status_code == 200
    assert laptop.get("/api/auth/me").status_code == 401
    assert browser().post("/api/auth/login", json={"email": email, "password": "first password"}).status_code == 401
    login(email, "second password")
    assert [m["Subject"] for m in smtp.sent] == ["Your DealMeet AI password was changed"]
    assert smtp.sent[0]["To"] == email


def test_accounts_without_a_password_have_none_to_change(db, login):
    r = login("cr_a").post("/api/auth/password", json={"current": "anything", "new": "something new"})
    assert r.status_code == 409


# ------------------------------------------------------------------ forgot and reset
def test_forgot_password_never_says_whether_an_account_exists(smtp, db):
    _, email = signup()
    smtp.sent.clear()
    anon = browser()
    a = anon.post("/api/auth/password/forgot", json={"email": "nobody-here@example.com"})
    b = anon.post("/api/auth/password/forgot", json={"email": email.upper()})
    assert a.status_code == b.status_code == 200 and a.json() == b.json()
    assert len(smtp.sent) == 1 and smtp.sent[0]["To"] == email
    token = link_token(smtp.sent[0], "/login/reset")
    # Only the hash is stored.
    doc = db.password_resets.find_one({"email": email})
    assert doc["_id"] == au.hash_token(token) and token not in str(doc)


def test_reset_sets_the_password_signs_out_everywhere_and_works_once(smtp, db):
    phone, email = signup()
    db.users.update_one({"email": email}, {"$set": {"email_verified": False}})
    browser().post("/api/auth/password/forgot", json={"email": email})
    token = link_token(smtp.sent[-1], "/login/reset")
    other = browser(LAPTOP)
    r = other.post("/api/auth/password/reset", json={"token": token, "password": "brand new password"})
    assert r.status_code == 200 and r.json()["user"]["email"] == email
    assert r.json()["user"]["email_verified"] is True  # the link reached the inbox
    assert other.get("/api/auth/me").status_code == 200  # signed in on this device
    assert phone.get("/api/auth/me").status_code == 401  # and out everywhere else
    login(email, "brand new password")
    assert browser().post("/api/auth/password/reset", json={"token": token, "password": "another password"}).status_code == 400
    assert smtp.sent[-1]["Subject"] == "Your DealMeet AI password was changed"


def test_reset_links_expire(smtp, db):
    _, email = signup()
    browser().post("/api/auth/password/forgot", json={"email": email})
    token = link_token(smtp.sent[-1], "/login/reset")
    db.password_resets.update_one({"_id": au.hash_token(token)}, {"$set": {"expires": time.time() - 1}})
    r = browser().post("/api/auth/password/reset", json={"token": token, "password": "brand new password"})
    assert r.status_code == 400 and "expired" in r.json()["detail"]


def test_forgot_password_is_limited_per_address(smtp, db):
    _, email = signup()
    anon = browser()
    codes = [anon.post("/api/auth/password/forgot", json={"email": email}).status_code for _ in range(4)]
    assert codes == [200, 200, 200, 429]


def test_without_email_set_up_reset_says_so(db):
    _, email = signup()
    r = browser().post("/api/auth/password/forgot", json={"email": email})
    assert r.status_code == 503 and "isn't set up" in r.json()["detail"]


def test_live_sites_never_build_links_from_the_host_header(monkeypatch):
    monkeypatch.setenv("DEMO_MODE", "0")
    monkeypatch.delenv("FRONTEND_URL", raising=False)
    config.get_settings.cache_clear()
    try:
        try:
            credentials._site("https://attacker.example/")
            raise AssertionError("expected a refusal")
        except Exception as e:
            assert getattr(e, "status_code", None) == 503
        monkeypatch.setenv("FRONTEND_URL", "https://dealmeet.in/")
        config.get_settings.cache_clear()
        assert credentials._site("https://attacker.example/") == "https://dealmeet.in"
    finally:
        config.get_settings.cache_clear()


# ------------------------------------------------------------------ email verification
def test_sign_up_sends_a_verification_link(smtp, db):
    c, email = signup()
    assert c.get("/api/auth/me").json()["user"]["email_verified"] is False
    msg = smtp.sent[-1]
    assert msg["To"] == email and msg["Subject"] == "Confirm your email for DealMeet AI"
    token = link_token(msg, "/verify-email")
    # The link works without being signed in.
    r = browser().post("/api/auth/email/verify", json={"token": token})
    assert r.status_code == 200 and r.json() == {"email": email, "role": "creator"}
    assert c.get("/api/auth/me").json()["user"]["email_verified"] is True
    assert browser().post("/api/auth/email/verify", json={"token": token}).status_code == 400
    assert c.post("/api/auth/email/resend").status_code == 409


def test_resend_replaces_the_earlier_link(smtp, db):
    c, email = signup()
    first = link_token(smtp.sent[-1], "/verify-email")
    r = c.post("/api/auth/email/resend")
    assert r.status_code == 200 and r.json() == {"sent_to": email}
    second = link_token(smtp.sent[-1], "/verify-email")
    assert browser().post("/api/auth/email/verify", json={"token": first}).status_code == 400
    assert browser().post("/api/auth/email/verify", json={"token": second}).status_code == 200


def test_deleting_the_account_removes_its_links(smtp, db):
    c, email = signup()
    user = db.users.find_one({"email": email})
    browser().post("/api/auth/password/forgot", json={"email": email})
    assert db.password_resets.count_documents({"user_id": user["_id"]}) == 1
    assert db.email_verifications.count_documents({"user_id": user["_id"]}) == 1
    assert c.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 200
    for name in ("password_resets", "email_verifications", "sessions"):
        assert db[name].count_documents({"user_id": user["_id"]}) == 0
