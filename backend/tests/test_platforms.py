"""One dashboard per connected platform, in that platform's words, never mixed."""
from datetime import datetime, timedelta, timezone

from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)
from test_youtube_profile import _new_creator

from app.engines import metrics


def _instagram(db, cid: str, followers: int = 4_200) -> None:
    """Stores an Instagram account and reels as services/instagram.py's sync does."""
    now = datetime.now(timezone.utc)
    db.creators.update_one({"_id": cid}, {"$set": {"channels.instagram": {"username": "ravi.eats", "followers": followers, "reach_28d": 9_000, "views_28d": 40_000, "source": "instagram_api", "fetched_at": now.isoformat()}}})
    for i in range(5):
        db.posts.insert_one({"creator_id": cid, "platform": "instagram", "post_id": f"ig{i}", "caption": f"Reel {i} #breakfast", "media_product_type": "REELS",
                             "published_at": (now - timedelta(days=2 + i)).isoformat(), "views": 3_000 + i * 100, "likes": 90, "comments": 6, "saves": 40, "shares": 12, "source": "instagram_api"})
    db.posts.insert_one({"creator_id": cid, "platform": "instagram", "post_id": "photo", "caption": "A photo", "media_product_type": "FEED", "published_at": now.isoformat(), "views": None})


def test_a_youtube_creator_sees_one_youtube_dashboard_in_youtube_words(client, youtube, db):
    a, cid = _new_creator(client, db, niche="gaming", stage="1k_10k", channel=CHANNEL)
    d = a.get(f"/api/creators/{cid}/platforms").json()
    assert d["primary"] == "youtube" and [p["platform"] for p in d["platforms"]] == ["youtube"]
    yt = d["platforms"][0]
    assert yt["terms"]["posts"] == "videos" and yt["terms"]["audience"] == "subscribers"
    kpis = {k["key"]: k for k in yt["kpis"]}
    assert kpis["audience"]["label"] == "Subscribers" and kpis["audience"]["value"] == 21_300
    assert kpis["median_views"]["label"].endswith("videos") and kpis["post_count"]["value"] == 120
    assert {f["key"] for f in yt["formats"]} == {"shorts", "long"}
    text = " ".join(yt["insights"] + [k["label"] for k in yt["kpis"]])
    assert "reel" not in text.lower() and "follower" not in text.lower()
    assert len(yt["chart"]["recent"]) == 6 and yt["chart"]["audience"] == 21_300
    # The rest of the app gets the same words.
    assert a.get(f"/api/creators/{cid}").json()["terms"]["post"] == "video"
    assert a.get(f"/api/creators/{cid}/home").json()["context"]["terms"]["audience"] == "subscribers"


def test_an_instagram_creator_sees_instagram_words_and_saves(client, db):
    a, cid = _new_creator(client, db, niche="food", stage="1k_10k", platforms=["instagram"])
    _instagram(db, cid)
    d = a.get(f"/api/creators/{cid}/platforms").json()
    assert [p["platform"] for p in d["platforms"]] == ["instagram"]
    ig = d["platforms"][0]
    kpis = {k["key"]: k for k in ig["kpis"]}
    assert kpis["audience"]["label"] == "Followers" and kpis["audience"]["value"] == 4_200
    assert kpis["saves_shares_per_1k"]["value"] is not None and len(ig["posts"]) == 5  # the photo has no views
    assert "video" not in " ".join(ig["insights"]).lower()


def test_both_platforms_get_their_own_dashboards(client, youtube, db):
    a, cid = _new_creator(client, db, niche="food", stage="1k_10k", channel=CHANNEL)
    _instagram(db, cid)
    d = a.get(f"/api/creators/{cid}/platforms").json()
    by = {p["platform"]: p for p in d["platforms"]}
    assert set(by) == {"youtube", "instagram"}
    # Never mixed: each dashboard has only its own posts and audience.
    assert all(p["id"].startswith("ig") for p in by["instagram"]["posts"])
    assert not any(p["id"].startswith("ig") for p in by["youtube"]["posts"])
    assert by["youtube"]["chart"]["audience"] == 21_300 and by["instagram"]["chart"]["audience"] == 4_200
    # The profile's numbers come from YouTube here, so YouTube is first.
    assert d["primary"] == "youtube" == metrics.platform(db.creators.find_one({"_id": cid}))


def test_no_channel_means_no_dashboard_and_words_from_what_they_use(client, db):
    a, cid = _new_creator(client, db, niche="travel", stage="zero")
    d = a.get(f"/api/creators/{cid}/platforms").json()
    assert d["platforms"] == [] and d["primary"] is None
    assert d["terms"]["platform"] == "youtube"  # onboarding said YouTube only


def test_hidden_subscribers_and_youtube_analytics(client, youtube, db):
    youtube.hidden = True
    a, cid = _new_creator(client, db, channel=CHANNEL)
    db.creators.update_one({"_id": cid}, {"$set": {"channels.youtube.analytics": {
        "period_days": 28, "views": 50_000, "minutes_watched": 90_000, "average_view_duration_s": 140,
        "age_gender": [{"age": "18-24", "gender": "female", "percent": 30.0}, {"age": "18-24", "gender": "male", "percent": 25.0}, {"age": "25-34", "gender": "male", "percent": 45.0}],
        "countries": [{"country": "IN", "views": 40_000}, {"country": "US", "views": 10_000}]}}})
    yt = a.get(f"/api/creators/{cid}/platforms").json()["platforms"][0]
    assert {k["key"]: k for k in yt["kpis"]}["audience"]["hidden"] is True
    assert any("hides its subscriber count" in n for n in yt["notes"])
    assert yt["analytics"]["top_age"] == {"age": "18-24", "percent": 55} and yt["analytics"]["top_countries"][0] == {"country": "IN", "share": 80}


def test_only_the_owner_sees_the_dashboards(client, login, youtube, db):
    _, cid = _new_creator(client, db, channel=CHANNEL)
    assert client.get(f"/api/creators/{cid}/platforms").status_code == 401
    assert login("br_thalam").get(f"/api/creators/{cid}/platforms").status_code == 403
