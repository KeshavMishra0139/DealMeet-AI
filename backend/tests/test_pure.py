"""Pure functions behind two rules, checked directly on the in-memory database
(USE_MOCK_DB=1): the median-views pricing input and the pitch limit. Fan Proof matching
has its pure-function test in test_pitches.py
(test_fan_proof_matches_handles_and_hashtags_but_not_paid_posts)."""
import time
from datetime import datetime, timedelta, timezone

from app.services import pitches
from app.services import youtube_public as yt


def _video(views, days_ago, fmt="shorts"):
    return {"views": views, "format": fmt, "published_at": (datetime.now(timezone.utc) - timedelta(days=days_ago)).isoformat()}


# ------------------------------------------------------------------ median-views pricing input
def test_shorts_are_told_apart_by_length_and_tag():
    assert yt._seconds("PT59S") == 59 and yt._seconds("PT2M30S") == 150 and yt._seconds("P1DT1H") == 90_000 and yt._seconds(None) == 0
    assert yt.video_format(60, "Quick upma", "") == "shorts"
    assert yt.video_format(150, "Quick upma", "") == "long"
    assert yt.video_format(150, "Quick upma #Shorts", "") == "shorts"
    assert yt.video_format(181, "Quick upma #shorts", "") == "long"


def test_the_price_uses_the_median_of_settled_videos_per_format():
    videos = [_video(1_000, 10), _video(2_000, 9), _video(90_000, 8), _video(3_000, 7), _video(500_000, 1)]  # one outlier, one too new
    videos += [_video(40_000, 12, "long")] * 2
    p = yt.prices_for(videos, "food")
    assert p["shorts"]["enough_data"] and p["shorts"]["videos"] == 4
    assert p["shorts"]["median_views"] == 2_500  # the median, so one big video doesn't set the price
    assert any("last 3 days" in r for r in p["shorts"]["why"])  # the newest video isn't counted yet
    assert p["long"] == {**p["long"], "enough_data": False, "videos": 2}  # long videos are priced on their own, and 2 aren't enough
    assert any("Subscribers don't set the price" in r for r in p["shorts"]["why"])


# ------------------------------------------------------------------ the pitch limit
def test_only_pitches_sent_in_the_last_7_days_count(db):
    now = time.time()
    db.pitches.insert_many([{"_id": f"pt_t{i}", "creator_id": "cr_b", "status": "sent", "sent_ts": now - i * 3600} for i in range(4)])
    db.pitches.insert_one({"_id": "pt_old", "creator_id": "cr_b", "status": "sent", "sent_ts": now - 8 * 86_400})
    db.pitches.insert_one({"_id": "pt_other", "creator_id": "cr_a", "status": "sent", "sent_ts": now})
    assert pitches.sent_this_week("cr_b") == 4 < pitches.PER_WEEK
    db.pitches.insert_one({"_id": "pt_t9", "creator_id": "cr_b", "status": "sent", "sent_ts": now})
    assert pitches.sent_this_week("cr_b") == pitches.PER_WEEK == 5
