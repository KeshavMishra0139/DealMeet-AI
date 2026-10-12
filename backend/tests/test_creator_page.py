"""The full public creator page: data-backed badges, collaborations, case studies,
positioning, and the sharing settings."""
import json

PRIVATE = ("email", "phone", "income_history", "income_goal", "manual_history", "past_deals", "best_deal", "current_rate")


def _page(client, handle="creator.a"):
    r = client.get(f"/api/public/{handle}")
    assert r.status_code == 200, r.text
    return r.json()


def _complete(db, deal_id, submitted="2026-10-10T10:00:00+05:30"):
    """Mark a deal approved, with its post submitted at a given time."""
    d = db.deals.find_one({"_id": deal_id})
    timeline = d.get("timeline", []) + [{"stage": "live", "at": submitted, "note": "Post link submitted"}, {"stage": "verified", "at": "2026-10-12T10:00:00+05:30", "note": "Approved"}]
    db.deals.update_one({"_id": deal_id}, {"$set": {"stage": "verified", "timeline": timeline, "proof_url": "https://www.instagram.com/reel/ABC123/"}})


def test_the_page_follows_the_sharing_settings_and_keeps_private_fields_out(client, login):
    p = _page(client)
    assert p["niche_tags"][0] == "Anime edits" and p["estimate"]["label"] == "Estimated range" and p["estimate"]["range"]["low"] > 0
    assert p["top_posts"] == []  # nothing synced through the API for this sample profile
    assert not any(f'"{k}"' in json.dumps(p) for k in PRIVATE)
    a = login("cr_a")
    a.post("/api/creators/cr_a/kit", json={"stats": False, "demographics": False, "rates": False, "collabs": False})
    p = _page(client)
    assert p["top_posts"] is None and p["estimate"] is None and p["collaborations"] is None and p["case_studies"] is None and p["stats"] is None


def test_badges_only_appear_with_data(client, login, db):
    me = login("new_creator")
    me.post("/api/creators", json={"name": "Asha Rao", "niche": "food", "audience_stage": "1k_10k", "income_goal": 5000, "languages": ["hi"], "city": "Pune"})
    assert _page(client, "asha.rao")["badges"] == []
    db.connections.insert_one({"_id": "cn_x", "creator_id": "cr_a", "user_id": "us_cr_a", "platform": "instagram", "status": "connected"})
    keys = {b["key"] for b in _page(client)["badges"]}
    assert "connected" in keys and not any("paid" in b["label"].lower() for b in _page(client)["badges"])


def test_on_time_delivery_completed_count_and_brand_rating(client, login, db):
    a, s = login("cr_a"), login("br_senpai")
    _complete(db, "dl_a_senpai", submitted="2026-10-10T10:00:00+05:30")  # campaign deadline 2026-10-25
    badges = {b["key"]: b for b in _page(client)["badges"]}
    assert badges["completed"]["label"] == "Completed on DealMeet ×1"
    assert badges["on_time"]["label"].startswith("On time:")
    # Rating: the brand, once, after approval.
    assert a.post("/api/deals/dl_a_senpai/rating", json={"stars": 5}).status_code == 403
    assert s.post("/api/deals/dl_a_senpai/rating", json={"stars": 6}).status_code == 422
    assert s.post("/api/deals/dl_a_senpai/rating", json={"stars": 4, "note": "Great edit"}).status_code == 200
    assert s.post("/api/deals/dl_a_senpai/rating", json={"stars": 5}).status_code == 409
    assert {b["key"]: b for b in _page(client)["badges"]}["rating"]["label"] == "Brand rating 4.0/5"
    assert login("br_pixelforge").post("/api/deals/dl_a_pixelforge/rating", json={"stars": 5}).status_code == 409  # not approved yet
    assert _page(client)["collaborations"][0]["brand"] == "Senpai Supply Co."


def test_late_posts_lower_on_time_delivery(client, db):
    _complete(db, "dl_a_senpai", submitted="2026-10-30T10:00:00+05:30")  # after the 25 Oct deadline
    on_time = {b["key"]: b for b in _page(client)["badges"]}["on_time"]
    # The Pixelforge post (submitted on time, awaiting review) counts too.
    assert on_time["label"] == "On time: 1 of 2 posts" and on_time["percent"] == 50


def test_case_studies_use_predicted_views_and_label_where_actual_views_come_from(client, login, db):
    a = login("cr_a")
    assert a.post("/api/deals/dl_a_senpai/action", json={"action": "accept", "name": "Creator A"}).status_code == 200
    predicted = db.deals.find_one({"_id": "dl_a_senpai"})["predicted"]
    assert predicted["views"] > 0 and predicted["source"] in ("manual", "synthetic", "instagram_api")
    _complete(db, "dl_a_senpai")
    study = _page(client)["case_studies"][0]
    assert study["predicted_views"] == predicted["views"] and study["actual_views"] is None and "paid_in_days" not in study
    assert a.post("/api/deals/dl_a_senpai/results", json={"views": 41_000}).status_code == 200
    study = _page(client)["case_studies"][0]
    assert study["actual_views"] == 41_000 and study["actual_source"] == "manual"
    # Views from the connected account win over self-reported ones.
    db.posts.insert_one({"creator_id": "cr_a", "platform": "instagram", "post_id": "1789", "permalink": "https://www.instagram.com/reel/ABC123/", "views": 52_000, "source": "instagram_api"})
    study = _page(client)["case_studies"][0]
    assert study["actual_views"] == 52_000 and study["actual_source"] == "instagram_api"
    assert login("br_senpai").post("/api/deals/dl_a_senpai/results", json={"views": 1}).status_code == 403


def test_positioning_is_written_edited_and_shown_only_when_chosen(client, login):
    assert client.get("/api/creators/cr_a/branding").status_code == 401
    assert login("cr_b").post("/api/creators/cr_a/branding/regenerate").status_code == 403
    a = login("cr_a")
    assert a.get("/api/creators/cr_a/branding").json()["branding"] is None
    assert a.patch("/api/creators/cr_a/branding", json={"show_on_page": True}).status_code == 409  # write it first
    b = a.post("/api/creators/cr_a/branding/regenerate").json()["branding"]
    assert len(b["pillars"]) == 3 and len(b["bio_suggestions"]) == 2 and b["written_by"] == "template"
    assert _page(client)["positioning"] is None  # not shown until the creator chooses
    assert a.patch("/api/creators/cr_a/branding", json={"positioning": "Guaranteed viral anime edits for every brand"}).status_code == 422
    r = a.patch("/api/creators/cr_a/branding", json={"positioning": "Anime edits people rewatch, in Hindi and English", "show_on_page": True})
    assert r.status_code == 200 and r.json()["branding"]["edited"] is True
    assert _page(client)["positioning"] == "Anime edits people rewatch, in Hindi and English"
