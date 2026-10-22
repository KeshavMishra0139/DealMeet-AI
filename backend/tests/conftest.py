import os
import uuid

# The suite runs the sandbox: seeded personas, demo sign-in and the in-memory database.
os.environ.setdefault("DEMO_MODE", "1")
os.environ.setdefault("USE_MOCK_DB", "1")

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app import config  # noqa: E402

from app.db import get_db  # noqa: E402
from app.main import app  # noqa: E402
from app.seed.load import seed_all  # noqa: E402

APP_HEADER = {"X-Requested-With": "jodidar-tests"}


@pytest.fixture(scope="session")
def client():
    # The shared client never holds a session cookie: tests sign in with Bearer tokens.
    with TestClient(app, headers=APP_HEADER) as c:
        yield c


@pytest.fixture()
def db():
    d = get_db()
    seed_all(d, force=True)
    from app.services import cache

    cache.clear_runtime()
    return d


class Actor:
    """Requests made as one signed-in account (Bearer token)."""

    def __init__(self, client: TestClient, token: str, user: dict):
        self.client, self.token, self.user = client, token, user
        self.headers = {"Authorization": f"Bearer {token}"}

    def _kw(self, kw: dict) -> dict:
        kw["headers"] = {**self.headers, **kw.get("headers", {})}
        return kw

    def get(self, url, **kw):
        return self.client.get(url, **self._kw(kw))

    def post(self, url, **kw):
        return self.client.post(url, **self._kw(kw))

    def patch(self, url, **kw):
        return self.client.patch(url, **self._kw(kw))

    def delete(self, url, **kw):
        return self.client.delete(url, **self._kw(kw))


def sign_in(client: TestClient, persona: str) -> Actor:
    r = client.post("/api/auth/demo", json={"persona": persona, "cookie": False})
    assert r.status_code == 200, r.text
    body = r.json()
    return Actor(client, body["token"], body["user"])


@pytest.fixture()
def login(client, db):
    """login("cr_a") -> an Actor signed in as that demo profile's account."""
    return lambda persona: sign_in(client, persona)


@pytest.fixture()
def admin(client, db):
    """An admin account (the role is only ever granted on the server)."""
    from app.services import auth as au

    user = au.new_user("admin", "Ops Admin", email=f"ops-{uuid.uuid4().hex[:6]}@example.test")
    return Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))


class FakeSMTP:
    """Stands in for smtplib.SMTP: keeps each message instead of sending it."""

    sent: list = []

    def __init__(self, host, port, timeout=None, context=None):
        self.host, self.port = host, port

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def starttls(self, context=None):
        pass

    def login(self, user, password):
        pass

    def send_message(self, msg):
        FakeSMTP.sent.append(msg)


@pytest.fixture()
def smtp(monkeypatch, db):
    """Email switched on, sending to FakeSMTP.sent; links point at https://dealmeet.test."""
    from app.services import mailer

    monkeypatch.setenv("SMTP_HOST", "smtp.test")
    monkeypatch.setenv("EMAIL_FROM", "DealMeet AI <hello@dealmeet.test>")
    monkeypatch.setenv("FRONTEND_URL", "https://dealmeet.test")
    config.get_settings.cache_clear()
    FakeSMTP.sent = []
    monkeypatch.setattr(mailer.smtplib, "SMTP", FakeSMTP)
    for name in ("email_log", "email_optouts", "claim_codes", "rate_limits"):
        db[name].delete_many({})
    yield FakeSMTP
    config.get_settings.cache_clear()
