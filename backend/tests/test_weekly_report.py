"""The creator's weekly report: real records aggregated per week, each labelled by source."""
from datetime import timedelta

from app.config import today

URL = "/api/creators/cr_b/weekly-report"


def _day(n: int) -> str:
    """Today minus n days, as the timestamps records carry."""
    return f"{(today() - timedelta(days=n)).isoformat()}T12:00:00+05:30"


def test_only_the_creator_sees_their_report(client, login, db):
    assert client.get(URL).status_code == 401
    assert login("cr_a").get(URL).status_code == 403
    assert login("br_thalam").get(URL).status_code == 403
    r = login("cr_b").get(URL).json()
    assert r["week"]["end"] == today().isoformat() and r["week"]["start"] == (today() - timedelta(days=6)).isoformat()


def test_brand_views_count_real_profile_opens_by_week(login, db):
    db.consent_audit.delete_many({"creator_id": "cr_b"})
    me = login("cr_b")
    assert me.get(URL).json()["profile_views"] == {"this": 0, "last": 0, "brands": 0, "source": "dealmeet"}
    # A brand opening the profile is what logs a view.
    assert login("br_thalam").get("/api/brands/br_thalam/creators/cr_b").status_code == 200
    db.consent_audit.insert_one({"_id": "au_old", "creator_id": "cr_b", "lister_id": "br_senpai", "action": "viewed", "scopes": [], "at": _day(9), "actor": "lister"})
    db.consent_audit.insert_one({"_id": "au_older", "creator_id": "cr_b", "lister_id": "br_senpai", "action": "viewed", "scopes": [], "at": _day(14), "actor": "lister"})
    v = me.get(URL).json()["profile_views"]
    assert v == {"this": 1, "last": 1, "brands": 1, "source": "dealmeet"}  # 14 days ago is outside both weeks


def test_offers_and_payouts_add_up_per_week(login, db):
    db.deals.delete_many({"creator_id": "cr_b"})
    base = {"creator_id": "cr_b", "brand_id": "br_thalam", "kind": "single", "deliverables": [], "listing_id": None}
    db.deals.insert_many([
        {**base, "_id": "dl_t1", "amount": 4000, "stage": "offer", "created_at": _day(0), "timeline": [{"stage": "offer", "at": _day(0)}]},
        {**base, "_id": "dl_t2", "amount": 2500, "stage": "offer", "created_at": _day(6), "timeline": [{"stage": "offer", "at": _day(6)}]},
        {**base, "_id": "dl_t3", "amount": 9000, "stage": "paid", "created_at": _day(20), "payout": {"status": "simulated"},
         "timeline": [{"stage": "offer", "at": _day(20)}, {"stage": "paid", "at": _day(2)}]},
        {**base, "_id": "dl_t4", "amount": 1200, "stage": "offer", "created_at": _day(7), "source": "synthetic", "timeline": []},
    ])
    r = login("cr_b").get(URL).json()
    assert r["offers"] == {"this": 2, "last": 1, "value": 6500, "last_value": 1200, "source": "synthetic"}  # dl_t4 is sample data
    assert r["paid"] == {"this": 9000, "last": 0, "deals": 1, "simulated": True, "source": "dealmeet"}


def test_reach_is_views_on_reels_posted_each_week(login, db):
    c = db.creators.find_one({"_id": "cr_b"})
    start, prev = (today() - timedelta(days=6)).isoformat(), (today() - timedelta(days=13)).isoformat()
    this = [x for x in c["reels"] if start <= x["date"] <= today().isoformat()]
    last = [x for x in c["reels"] if prev <= x["date"] < start]
    r = login("cr_b").get(URL).json()["reach"]
    assert r["reels"] == len(this) and r["this"] == sum(x["views"] for x in this)
    assert r["last_reels"] == len(last) and r["last"] == sum(x["views"] for x in last)
    assert r["source"] == "synthetic"
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"reels": []}})
    assert login("cr_b").get(URL).json()["reach"] is None  # no reels: no reach block, not a zero


def test_follower_change_comes_from_platform_snapshots(login, db):
    me = login("cr_b")
    assert me.get(URL).json()["followers"] == []
    for n, followers in ((1, 2150), (5, 2120), (10, 2010)):
        db.metric_snapshots.insert_one({"creator_id": "cr_b", "platform": "instagram", "date": (today() - timedelta(days=n)).isoformat(), "followers": followers, "source": "instagram_api"})
    assert me.get(URL).json()["followers"] == [{"platform": "instagram", "now": 2150, "before": 2010, "source": "instagram_api"}]


def test_a_quiet_week_says_so(login, db):
    db.consent_audit.delete_many({"creator_id": "cr_b"})
    db.deals.delete_many({"creator_id": "cr_b"})
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"reels": []}})
    assert login("cr_b").get(URL).json()["quiet"] is True
