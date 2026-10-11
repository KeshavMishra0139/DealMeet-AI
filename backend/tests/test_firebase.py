"""Firebase sign-in: ID tokens are verified on the server before any account is used."""
import base64
import json
import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import firebase_auth

from conftest import APP_HEADER

PROJECT = "jodidar-test"


def _service_account() -> str:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    return json.dumps(
        {
            "type": "service_account",
            "project_id": PROJECT,
            "private_key_id": "test",
            "private_key": pem,
            "client_email": f"firebase-adminsdk@{PROJECT}.iam.gserviceaccount.com",
            "client_id": "1",
            "token_uri": "https://oauth2.googleapis.com/token",
        }
    )


@pytest.fixture()
def firebase(monkeypatch):
    monkeypatch.setenv("FIREBASE_SERVICE_ACCOUNT_JSON", _service_account())
    monkeypatch.setenv("FIREBASE_PROJECT_ID", PROJECT)
    config.get_settings.cache_clear()
    firebase_auth._app = None
    yield
    import firebase_admin

    if firebase_auth._app is not None:
        firebase_admin.delete_app(firebase_auth._app)
    firebase_auth._app = None
    config.get_settings.cache_clear()


@pytest.fixture()
def verified(monkeypatch, firebase):
    """Stands in for Google's signature check: returns these claims for any token."""
    from firebase_admin import auth

    claims = {"uid": "fb-uid-1", "email": "meera@example.com", "email_verified": True, "name": "Meera", "firebase": {"sign_in_provider": "google.com"}}
    monkeypatch.setattr(auth, "verify_id_token", lambda token, app=None, check_revoked=False: dict(claims))
    return claims


def _b64(d: dict) -> str:
    return base64.urlsafe_b64encode(json.dumps(d).encode()).decode().rstrip("=")


def _unsigned_token(**payload) -> str:
    now = int(time.time())
    body = {"iss": f"https://securetoken.google.com/{PROJECT}", "aud": PROJECT, "sub": "fb-uid-x", "iat": now, "exp": now + 3600, "auth_time": now, **payload}
    return f"{_b64({'alg': 'RS256', 'kid': 'abc', 'typ': 'JWT'})}.{_b64(body)}.{'x' * 40}"


def fresh() -> TestClient:
    return TestClient(app, headers=APP_HEADER)


def test_not_configured_says_so(client, db):
    r = client.post("/api/auth/firebase", json={"id_token": "x" * 40, "role": "creator"})
    assert r.status_code == 503 and "aren't configured" in r.json()["detail"]
    assert "firebase" not in client.get("/api/health").json()["modes"]["auth"]


def test_forged_token_is_refused(client, db, firebase):
    r = client.post("/api/auth/firebase", json={"id_token": "not-a-real-token-" + "x" * 30, "role": "creator"})
    assert r.status_code == 401
    assert db.users.count_documents({"firebase_uid": {"$exists": True}}) == 0


def test_token_from_another_firebase_project_is_refused(client, db, firebase):
    # Checked by the real Admin SDK, offline: the audience is another project.
    token = _unsigned_token(aud="someone-elses-project", iss="https://securetoken.google.com/someone-elses-project")
    r = client.post("/api/auth/firebase", json={"id_token": token, "role": "brand"})
    assert r.status_code == 401 and "couldn't be verified" in r.json()["detail"]


@pytest.mark.parametrize("error,detail", [("expired", "expired"), ("revoked", "revoked")])
def test_expired_and_revoked_tokens_are_refused(client, db, firebase, monkeypatch, error, detail):
    from firebase_admin import auth

    def boom(token, app=None, check_revoked=False):
        raise auth.ExpiredIdTokenError("expired", None) if error == "expired" else auth.RevokedIdTokenError("revoked")

    monkeypatch.setattr(auth, "verify_id_token", boom)
    r = client.post("/api/auth/firebase", json={"id_token": "t" * 40, "role": "creator"})
    assert r.status_code == 401 and detail in r.json()["detail"]


def test_first_sign_in_creates_the_account_and_a_session(db, verified):
    c = fresh()
    assert c.post("/api/auth/firebase", json={"id_token": "t" * 40}).status_code == 409  # pick a side first
    r = c.post("/api/auth/firebase", json={"id_token": "t" * 40, "role": "creator"})
    assert r.status_code == 200 and "httponly" in r.headers["set-cookie"].lower()
    me = c.get("/api/auth/me").json()["user"]
    assert me["role"] == "creator" and me["providers"] == ["firebase"] and me["email"] == "meera@example.com"
    assert db.users.count_documents({"firebase_uid": "fb-uid-1"}) == 1


def test_the_role_chosen_at_first_sign_in_cant_change(db, verified):
    c = fresh()
    c.post("/api/auth/firebase", json={"id_token": "t" * 40, "role": "creator"})
    r = c.post("/api/auth/firebase", json={"id_token": "t" * 40, "role": "brand"})
    assert r.status_code == 200 and r.json()["user"]["role"] == "creator" and "can't change" in r.json()["note"]
    assert db.users.find_one({"firebase_uid": "fb-uid-1"})["role"] == "creator"
    assert db.users.count_documents({"firebase_uid": "fb-uid-1"}) == 1


def test_a_verified_email_links_to_the_existing_password_account(db, verified):
    c = fresh()
    c.post("/api/auth/signup", json={"email": "meera@example.com", "password": "long enough", "name": "Meera", "role": "brand"})
    r = fresh().post("/api/auth/firebase", json={"id_token": "t" * 40, "role": "creator"})
    assert r.json()["user"]["role"] == "brand"  # the existing account keeps its role
    assert db.users.count_documents({"email": "meera@example.com"}) == 1
    assert db.users.find_one({"email": "meera@example.com"})["firebase_uid"] == "fb-uid-1"


def test_a_uid_alone_is_never_accepted(client, db, firebase):
    r = client.post("/api/auth/firebase", json={"uid": "fb-uid-1", "role": "creator"})
    assert r.status_code == 422
