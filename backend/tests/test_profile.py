"""Creator profile: editing, completeness, brand-readiness, self-reported numbers and
collaboration preferences."""
import time
from datetime import datetime, timezone

from app.services.views import source_of


def _new_creator(login):
    me = login("new_creator")
    body = {"name": "Asha Bakes", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["hi"], "city": "Pune"}
    cid = me.post("/api/creators", json=body).json()["id"]
    return me, cid


def test_profile_is_owner_only(client, login, db):
    assert client.get("/api/creators/cr_b/profile").status_code == 401
    assert login("cr_a").get("/api/creators/cr_b/profile").status_code == 403
    assert login("br_thalam").patch("/api/creators/cr_b/profile", json={"bio": "x"}).status_code == 403


def test_editing_the_profile_persists_and_raises_completeness(login, db):
    me, cid = _new_creator(login)
    before = me.get(f"/api/creators/{cid}/profile").json()["completeness"]
    assert before["total"] == 10 and all(i["fix"] for i in before["items"] if not i["done"])
    r = me.patch(
        f"/api/creators/{cid}/profile",
        json={
            "bio": "Eggless bakes and quick Indian desserts, in Hindi, for home bakers.",
            "sub_niches": ["eggless cakes", "festive sweets", "eggless cakes"],
            "city": "Mumbai",
            "formats": ["reels", "shorts"],
            "collab_prefs": {"accepts": "paid", "min_fee": 3000, "avoid": ["alcohol"]},
        },
    )
    assert r.status_code == 200, r.text
    after = r.json()
    assert after["completeness"]["score"] > before["score"]
    c = db.creators.find_one({"_id": cid})
    assert c["sub_niches"] == ["eggless cakes", "festive sweets"] and c["region"] == "West" and c["collab_prefs"]["min_fee"] == 3000
    assert me.get(f"/api/creators/{cid}/profile").json()["collab_prefs"]["avoid"] == ["alcohol"]  # survives a reload


def test_invalid_profile_input_is_refused(login, db):
    me, cid = _new_creator(login)
    assert me.patch(f"/api/creators/{cid}/profile", json={"niche": "astrology"}).status_code == 422
    assert me.patch(f"/api/creators/{cid}/profile", json={"city": "Atlantis"}).status_code == 422
    assert me.patch(f"/api/creators/{cid}/profile", json={"languages": []}).status_code == 422
    assert me.patch(f"/api/creators/{cid}/profile", json={"collab_prefs": {"accepts": "sometimes"}}).status_code == 422
    assert me.patch(f"/api/creators/{cid}/profile", json={"bio": "x" * 401}).status_code == 422


def test_readiness_says_connect_to_check_without_a_connected_account(login, db):
    r = login("cr_b").get("/api/creators/cr_b/profile").json()["readiness"]
    status = {i["key"]: i["status"] for i in r["items"]}
    assert status["professional"] == "connect"
    assert {status[k] for k in ("consistency", "focus", "disclosure", "demographics")} == {"connect"}
    assert r["to_connect"] == 5 and "connect to check" in r["method"]


def test_readiness_from_connected_data(login, db):
    db.connections.insert_one({"_id": "cn_b", "creator_id": "cr_b", "user_id": "us_cr_b", "platform": "instagram", "status": "connected"})
    now = datetime.now(timezone.utc)
    for i in range(6):
        ts = datetime.fromtimestamp(now.timestamp() - i * 3 * 86400, tz=timezone.utc).isoformat()
        cap = "Ragi dosa #tiffin" + (" #ad with @thalamfoods" if i == 0 else "")
        db.posts.insert_one({"creator_id": "cr_b", "platform": "instagram", "post_id": f"p{i}", "caption": cap, "published_at": ts, "permalink": f"https://www.instagram.com/reel/P{i}/", "source": "instagram_api"})
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"channels.instagram": {"followers": 2100, "demographics": {"age": {"18-24": 10}}}}})
    r = login("cr_b").get("/api/creators/cr_b/profile").json()["readiness"]
    items = {i["key"]: i for i in r["items"]}
    assert items["professional"]["status"] == "passed" and items["professional"]["source"] == "instagram_api"
    assert items["consistency"]["status"] == "passed" and items["focus"]["status"] == "passed"
    assert items["disclosure"]["status"] == "passed" and items["demographics"]["status"] == "passed"


def test_self_reported_numbers_have_history_and_feed_the_price(login, db):
    me, cid = _new_creator(login)
    r = me.post(f"/api/creators/{cid}/manual-metrics", json={"platform": "instagram", "followers": 4100, "avg_views": 9000, "engagement_pct": 4.2})
    assert r.status_code == 200 and r.json()["applied"] is True
    me.post(f"/api/creators/{cid}/manual-metrics", json={"platform": "instagram", "followers": 4300, "avg_views": 9500})
    p = me.get(f"/api/creators/{cid}/profile").json()
    assert [h["followers"] for h in p["manual_history"]] == [4300, 4100] and all(h["source"] == "manual" for h in p["manual_history"])
    c = db.creators.find_one({"_id": cid})
    assert c["followers"] == 4300 and source_of(c, "followers") == "manual" and p["creator"]["sources"]["followers"] == "manual"
    fp = me.get(f"/api/creators/{cid}/fair-price").json()
    assert fp["data_label"] == "Estimate from self-reported numbers" and "9.5K average views you reported" in fp["steps"][0]["reason"]
    assert me.post(f"/api/creators/{cid}/manual-metrics", json={"platform": "tiktok", "followers": 1}).status_code == 422


def test_self_reported_numbers_never_replace_connected_ones(login, db):
    db.connections.insert_one({"_id": "cn_b2", "creator_id": "cr_b", "user_id": "us_cr_b", "platform": "instagram", "status": "connected"})
    before = db.creators.find_one({"_id": "cr_b"})["followers"]
    r = login("cr_b").post("/api/creators/cr_b/manual-metrics", json={"platform": "instagram", "followers": 999_999}).json()
    assert r["applied"] is False and "never replace" in r["note"]
    assert db.creators.find_one({"_id": "cr_b"})["followers"] == before
    assert db.manual_metrics.count_documents({"creator_id": "cr_b"}) == 1  # kept in the history


def test_collaboration_preferences_filter_opportunities(login, db):
    a = login("cr_a")
    before = a.get("/api/creators/cr_a/opportunities").json()
    a.patch("/api/creators/cr_a/profile", json={"collab_prefs": {"accepts": "both", "min_fee": 30_000, "avoid": ["hoodie"]}})
    after = a.get("/api/creators/cr_a/opportunities").json()
    reasons = " ".join(x["reason"] for x in after["hidden_by_prefs"])
    assert after["hidden_by_prefs"] and len(after["items"]) < len(before["items"])
    assert "below your minimum" in reasons or "which you avoid" in reasons


def test_private_fields_never_reach_brands_or_public_pages(client, login, db):
    a = login("cr_a")
    a.post("/api/creators/cr_a/manual-metrics", json={"platform": "youtube", "followers": 1234, "avg_views": 555})
    db.creators.update_one({"_id": "cr_a"}, {"$set": {"email": "secret@example.com", "phone": "+919999999999"}})
    for text in (
        login("br_senpai").get("/api/brands/br_senpai/creators/cr_a?listing_id=lst_senpai_hoodie").text,
        client.get("/api/public/creator.a").text,
    ):
        for private in ("secret@example.com", "+919999999999", "income_history", "manual_history", "engagement_pct", "earnings"):
            assert private not in text, private
