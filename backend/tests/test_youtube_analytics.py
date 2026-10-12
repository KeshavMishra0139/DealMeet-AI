"""YouTube Analytics through a creator's Google sign-in (faked at the HTTP layer)."""
import httpx
import pytest

from app.services import youtube_analytics as yta

from test_youtube import CHANNEL, FakeYouTube  # noqa: F401 - reuses the public-data fake
from test_youtube import youtube  # noqa: F401 - fixture

TOKEN = "ya29.google-access-token-xyz"


class FakeAnalytics:
    def __init__(self):
        self.channel_id = CHANNEL
        self.no_channel = False
        self.declined = False
        self.seen_tokens: list[str] = []

    def get(self, url, params=None, headers=None, timeout=None):
        self.seen_tokens.append((headers or {}).get("Authorization", ""))
        req = httpx.Request("GET", url)
        if self.declined and "youtubeanalytics" in url:
            return httpx.Response(403, json={"error": {"errors": [{"reason": "insufficientPermissions"}]}}, request=req)
        if url.endswith("/channels"):
            assert params["mine"] == "true"
            items = [] if self.no_channel else [{"id": self.channel_id, "snippet": {"title": "Someone Else" if self.channel_id != CHANNEL else "Test Kitchen"}}]
            return httpx.Response(200, json={"items": items}, request=req)
        assert params["ids"] == "channel==MINE"
        dims = params.get("dimensions")
        if dims is None:
            assert params["metrics"] == "views,estimatedMinutesWatched,averageViewDuration"
            rows = [[48_000, 96_000, 120]]
        elif dims == "ageGroup,gender":
            rows = [["age18-24", "female", 30.5], ["age25-34", "male", 22.0]]
        else:
            assert dims == "country" and params["sort"] == "-views"
            rows = [["IN", 40_000], ["AE", 3_000]]
        return httpx.Response(200, json={"rows": rows}, request=req)


@pytest.fixture()
def analytics(monkeypatch, youtube):
    """Both services call the one httpx module: OAuth calls (with a Bearer header) go to
    the Analytics fake, API-key calls to the public-data fake."""
    fake = FakeAnalytics()

    def get(url, params=None, headers=None, timeout=None):
        if headers and "Authorization" in headers:
            return fake.get(url, params=params, headers=headers, timeout=timeout)
        return youtube.get(url, params=params, timeout=timeout)

    monkeypatch.setattr(yta.httpx, "get", get)
    return fake


def _link(actor):
    assert actor.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 200


def test_connect_reads_28_days_and_verifies_ownership(login, analytics, db):
    b = login("cr_b")
    _link(b)
    r = b.post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    assert r.status_code == 200, r.text
    d = r.json()
    a = d["analytics"]
    assert a["views"] == 48_000 and a["minutes_watched"] == 96_000 and a["average_view_duration_s"] == 120
    assert a["age_gender"][0] == {"age": "18-24", "gender": "female", "percent": 30.5}
    assert a["countries"][0] == {"country": "IN", "views": 40_000}
    assert a["source"] == "youtube_api" and a["fetched_at"] and a["period_days"] == 28
    assert d["channel"]["ownership_verified"] is True and d["status"]["status"] == "connected"
    assert analytics.seen_tokens[0] == f"Bearer {TOKEN}"
    # The token is used once and never stored.
    for name in db.list_collection_names():
        assert TOKEN not in str(list(db[name].find({}))), name
    # A refresh of the public data keeps the analytics for the same channel.
    _link(b)
    assert b.get("/api/creators/cr_b/youtube").json()["analytics"]["views"] == 48_000


def test_another_channel_is_refused(login, analytics, db):
    b = login("cr_b")
    _link(b)
    analytics.channel_id = "UC" + "z" * 22
    r = b.post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    assert r.status_code == 409 and "isn't the channel linked here" in r.json()["detail"]
    assert db.creators.find_one({"_id": "cr_b"})["channels"]["youtube"]["ownership_verified"] is False


def test_no_channel_and_declined_scope(login, analytics):
    b = login("cr_b")
    _link(b)
    analytics.no_channel = True
    r = b.post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    assert r.status_code == 409 and "doesn't have a YouTube channel" in r.json()["detail"]
    analytics.no_channel = False
    analytics.declined = True
    r = b.post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    assert r.status_code == 403 and "allow both YouTube permissions" in r.json()["detail"]


def test_needs_a_linked_channel_first(login, analytics):
    r = login("cr_a").post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    assert r.status_code == 409 and "Link your YouTube channel" in r.json()["detail"]


def test_disconnect_deletes_the_snapshots(login, analytics, db):
    b = login("cr_b")
    _link(b)
    b.post("/api/connect/youtube/analytics", json={"access_token": TOKEN})
    d = b.delete("/api/connect/youtube/analytics").json()
    assert d["analytics"] is None and d["channel"]["ownership_verified"] is False and d["status"]["status"] == "linked"
    assert db.metric_snapshots.count_documents({"creator_id": "cr_b", "analytics": {"$exists": True}}) == 0


def test_only_creators_connect_their_own(client, login, analytics):
    assert client.post("/api/connect/youtube/analytics", json={"access_token": TOKEN}).status_code == 401
    assert login("br_thalam").post("/api/connect/youtube/analytics", json={"access_token": TOKEN}).status_code == 403
    assert login("cr_b").post("/api/connect/youtube/analytics", json={"access_token": "short"}).status_code == 422
