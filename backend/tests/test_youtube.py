"""Real YouTube data through the Data API (faked here), the public Worth lookup and linking."""
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import config
from app.services import youtube_public as yt

CHANNEL = "UC" + "a" * 22


def _video(i: int, views: int, seconds: int, days_ago: int, title: str = "") -> dict:
    published = (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat().replace("+00:00", "Z")
    return {
        "id": f"v{i}",
        "snippet": {"title": title or f"Video {i}", "description": "", "publishedAt": published},
        "statistics": {"viewCount": str(views), "likeCount": "10", "commentCount": "2"},
        "contentDetails": {"duration": f"PT{seconds // 60}M{seconds % 60}S"},
    }


class FakeYouTube:
    """Answers channels, playlistItems and videos like the YouTube Data API v3."""

    def __init__(self):
        self.calls: list[str] = []
        self.hidden = False
        self.fail: str | None = None
        self.videos = (
            [_video(i, 10_000 + i * 1_000, 45, 5 + i) for i in range(5)]  # 5 Shorts
            + [_video(10 + i, 50_000, 600, 10 + i) for i in range(4)]  # 4 long videos
            + [_video(99, 900_000, 40, 1)]  # yesterday's Short: still climbing, not counted
        )

    def get(self, url, params=None, timeout=None):
        endpoint = url.rsplit("/", 1)[-1]
        self.calls.append(endpoint)
        req = httpx.Request("GET", url)
        if self.fail == "network":
            raise httpx.ConnectError("down")
        if self.fail == "quota":
            return httpx.Response(403, json={"error": {"errors": [{"reason": "quotaExceeded"}]}}, request=req)
        if endpoint == "channels":
            if params.get("forHandle") == "@nobody":
                return httpx.Response(200, json={"items": []}, request=req)
            stats = {"viewCount": "5000000", "videoCount": "120", "subscriberCount": "21300", "hiddenSubscriberCount": self.hidden}
            item = {
                "id": CHANNEL,
                "snippet": {"title": "Test Kitchen", "customUrl": "@testkitchen", "thumbnails": {"default": {"url": "https://i.ytimg.com/x.jpg"}}},
                "statistics": stats,
                "topicDetails": {"topicCategories": ["https://en.wikipedia.org/wiki/Food"]},
                "contentDetails": {"relatedPlaylists": {"uploads": "UU" + "a" * 22}},
            }
            return httpx.Response(200, json={"items": [item]}, request=req)
        if endpoint == "playlistItems":
            start, size = int(params.get("pageToken") or 0), int(params.get("maxResults") or 5)
            page = {"items": [{"contentDetails": {"videoId": v["id"]}} for v in self.videos[start : start + size]]}
            if start + size < len(self.videos):
                page["nextPageToken"] = str(start + size)
            return httpx.Response(200, json=page, request=req)
        if endpoint == "videos":
            ids = params["id"].split(",")
            return httpx.Response(200, json={"items": [v for v in self.videos if v["id"] in ids]}, request=req)
        raise AssertionError(f"unexpected endpoint {endpoint}")


@pytest.fixture()
def youtube(monkeypatch, db):
    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    config.get_settings.cache_clear()
    db.yt_cache.delete_many({})
    db.rate_limits.delete_many({})
    fake = FakeYouTube()
    monkeypatch.setattr(yt.httpx, "get", fake.get)
    yield fake
    config.get_settings.cache_clear()


def test_public_preview_prices_shorts_and_long_videos_on_median_views(client, youtube):
    r = client.post("/api/youtube/preview", json={"handle": "@testkitchen"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["source"] == "youtube_api" and d["fetched_at"]
    assert d["channel"]["subscribers"] == 21_300 and d["niche"] == "food"
    shorts, long = d["prices"]["shorts"], d["prices"]["long"]
    assert shorts["enough_data"] and shorts["videos"] == 5 and shorts["median_views"] == 12_000  # yesterday's Short excluded
    assert long["median_views"] == 50_000
    assert any("aren't counted yet" in w for w in shorts["why"])
    assert "Subscribers don't set the price" in shorts["why"][0]
    assert 3 <= len(shorts["why"]) <= 5
    # Priced on views, not subscribers: 12,000 views x Rs 140 per 1,000 = Rs 1,680.
    assert shorts["per_video"] == 1_680 and shorts["estimate"]["low"] < 1_680 < shorts["estimate"]["high"]
    assert "search" not in youtube.calls  # 100-unit search.list is never used


def test_lookups_are_cached_for_12_hours(client, youtube):
    client.post("/api/youtube/preview", json={"handle": "@testkitchen"})
    n = len(youtube.calls)
    client.post("/api/youtube/preview", json={"handle": "@testkitchen"})
    assert len(youtube.calls) == n


def test_public_lookups_are_rate_limited_per_ip(client, youtube):
    from app.routers.youtube import PREVIEW_PER_HOUR

    codes = [client.post("/api/youtube/preview", json={"handle": "@testkitchen"}).status_code for _ in range(PREVIEW_PER_HOUR + 1)]
    assert codes[-1] == 429 and set(codes[:-1]) == {200}


@pytest.mark.parametrize(
    "setup,handle,status,text",
    [
        (None, "@nobody", 404, "No YouTube channel found"),
        ("quota", "@testkitchen", 503, "quota"),
        ("network", "@testkitchen", 502, "Couldn't reach YouTube"),
        (None, "not a handle!", 422, "YouTube handle"),
    ],
)
def test_failures_have_clear_messages(client, youtube, setup, handle, status, text):
    youtube.fail = setup
    r = client.post("/api/youtube/preview", json={"handle": handle})
    assert r.status_code == status and text in r.json()["detail"]


def test_hidden_subscribers_and_too_few_videos(client, youtube):
    youtube.hidden = True
    youtube.videos = youtube.videos[:2]
    d = client.post("/api/youtube/preview", json={"handle": "@testkitchen"}).json()
    assert d["channel"]["subscribers"] is None and any("hides its subscriber count" in n for n in d["notes"])
    assert d["prices"]["shorts"]["enough_data"] is False and "Not enough recent Shorts" in d["prices"]["shorts"]["reason"]
    assert "estimate" not in d["prices"]["shorts"]


def test_not_configured_says_so(client, db, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    config.get_settings.cache_clear()
    db.yt_cache.delete_many({})
    r = client.post("/api/youtube/preview", json={"handle": "@testkitchen"})
    assert r.status_code == 503 and "YOUTUBE_API_KEY" in r.json()["detail"]


def test_channel_urls_work_as_input():
    assert yt.parse_query("https://www.youtube.com/@testkitchen/videos") == {"forHandle": "@testkitchen"}
    assert yt.parse_query(f"youtube.com/channel/{CHANNEL}") == {"id": CHANNEL}


def test_linking_saves_posts_and_a_daily_snapshot(login, youtube, db):
    a = login("cr_b")
    r = a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["linked"] and d["channel"]["source"] == "youtube_api" and d["channel"]["ownership_verified"] is False
    assert d["status"]["status"] == "linked"
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "youtube", "source": "youtube_api"}) == 10
    snap = db.metric_snapshots.find_one({"creator_id": "cr_b", "platform": "youtube"})
    assert snap["subscribers"] == 21_300 and snap["source"] == "youtube_api" and snap["fetched_at"]
    # Linking again the same day updates the one snapshot.
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    assert db.metric_snapshots.count_documents({"creator_id": "cr_b", "platform": "youtube"}) == 1
    # The same channel can't be linked to a second profile.
    assert login("cr_a").post("/api/creators/cr_a/youtube/link", json={"handle": "@testkitchen"}).status_code == 409
    # Unlinking removes the posts and snapshots.
    assert a.delete("/api/creators/cr_b/youtube/link").json()["linked"] is False
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "youtube"}) == 0
    assert db.metric_snapshots.count_documents({"creator_id": "cr_b", "platform": "youtube"}) == 0


def test_only_the_owner_links_a_channel(client, login, youtube):
    assert client.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 401
    assert login("cr_a").post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 403
    assert login("br_thalam").get("/api/creators/cr_b/youtube").status_code == 403


def test_a_channel_posting_dozens_a_day_is_priced_on_older_videos(client, youtube):
    # A TV network: 80 clips in the last 2 days, then its older uploads.
    youtube.videos = (
        [_video(4000, 0, 0, 0, title="Live now")]
        + [_video(1000 + i, 2_000_000, 300, 1) for i in range(80)]
        + [_video(2000 + i, 400_000, 30, 4 + i // 10) for i in range(40)]
        + [_video(3000 + i, 800_000, 900, 4 + i // 10) for i in range(40)]
    )
    youtube.videos[0]["snippet"]["liveBroadcastContent"] = "live"
    r = yt.channel_report("@testkitchen")
    assert len(r["videos"]) == 30  # the newest 30 still shown
    shorts, long = r["prices"]["shorts"], r["prices"]["long"]
    assert shorts["enough_data"] and shorts["median_views"] == 400_000
    assert long["enough_data"] and long["median_views"] == 800_000 and long["videos"] == 29  # 150 read: 1 live, 80 new, 40 Shorts, 29 long
    assert all(v["post_id"] != "v4000" for v in r["videos"])  # the live stream isn't counted
    assert youtube.calls.count("playlistItems") == 3  # stopped once enough settled videos were in
