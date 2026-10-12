"""Saved rates, the pricing form, the live media kit in English and Hindi, and saved kit versions."""
import hashlib

import pytest

from app import config
from app.ai import llm
from app.services import media_kit, pdf

NEW = {"name": "Asha", "niche": "food", "audience_stage": "1k_10k", "income_goal": 5000, "languages": ["hi"], "city": "Pune"}


def _new_creator(login, **kw):
    me = login("new_creator")
    cid = me.post("/api/creators", json={**NEW, **kw}).json()["id"]
    return me, cid


# ------------------------------------------------------------------ access
@pytest.mark.parametrize(
    "method,url,body",
    [
        ("GET", "/api/creators/cr_a/rates", None),
        ("GET", "/api/creators/cr_a/pricing/estimate?format=reel", None),
        ("PUT", "/api/creators/cr_a/rates/reel", {"amount": 9000}),
        ("GET", "/api/creators/cr_a/kit/versions", None),
        ("POST", "/api/creators/cr_a/kit/versions", {"headline": "Food reels in Tamil"}),
        ("PUT", "/api/creators/cr_a/kit/public-view", {"version_id": None}),
    ],
)
def test_rates_and_versions_are_owner_only(client, login, method, url, body):
    assert client.request(method, url, json=body).status_code == 401
    other = login("cr_b")
    assert other.client.request(method, url, json=body, headers=other.headers).status_code == 403


def test_invalid_input_is_refused(login):
    a = login("cr_a")
    assert a.get("/api/creators/cr_a/pricing/estimate", params={"format": "tweet"}).status_code == 422
    assert a.get("/api/creators/cr_a/pricing/estimate", params={"format": "reel", "count": 0}).status_code == 422
    assert a.client.put("/api/creators/cr_a/rates/reel", json={"amount": 50}, headers=a.headers).status_code == 422
    assert a.client.put("/api/creators/cr_a/rates/tweet", json={"amount": 5000}, headers=a.headers).status_code == 422
    assert a.get("/api/creators/cr_a/kit?lang=fr").status_code == 422
    assert a.post("/api/creators/cr_a/kit/versions", json={"headline": "x"}).status_code == 422
    assert a.post("/api/creators/cr_a/kit/versions", json={"headline": "Food reels", "sections": {"gossip": True}}).status_code == 422


# ------------------------------------------------------------------ the pricing form
def test_estimate_lists_the_metrics_it_used_and_their_sources(login):
    d = login("cr_a").get("/api/creators/cr_a/pricing/estimate", params={"format": "reel", "usage_rights_days": 30}).json()
    assert d["enough_data"] and d["range"]["low"] < d["range"]["high"]
    keys = {m["key"]: m for m in d["metrics"]}
    assert {"followers", "median_views", "engagement"} <= set(keys)
    assert all(m["source"] in ("instagram_api", "youtube_api", "manual", "synthetic") for m in d["metrics"])
    assert "median_views" not in {m["key"] for m in d["missing"]}
    assert d["terms"] == ["30 days of paid usage rights"]
    assert any("85/100" in a for a in d["assumptions"]) and d["steps"][0]["label"] == "Reach base"


def test_missing_metrics_are_named_not_invented(login):
    me, cid = _new_creator(login)
    d = me.get(f"/api/creators/{cid}/pricing/estimate", params={"format": "reel"}).json()
    assert d["enough_data"] and d["data_label"] == "Estimate from your follower count"
    missing = {m["key"]: m for m in d["missing"]}
    assert {"median_views", "engagement", "consistency"} <= set(missing)
    assert "follower count" in missing["median_views"]["effect"] and missing["median_views"]["fix"]
    # What onboarding generated is listed as sample data, never as the creator's own numbers.
    used = {m["key"]: m["source"] for m in d["metrics"]}
    assert used == {"followers": "synthetic", "audience": "synthetic"}


def test_no_audience_numbers_means_no_estimate(login):
    me, cid = _new_creator(login, audience_stage="zero")
    d = me.get(f"/api/creators/{cid}/pricing/estimate", params={"format": "reel"}).json()
    assert d["enough_data"] is False and d["range"] is None
    assert {"followers", "median_views"} <= {m["key"] for m in d["missing"]}


def test_youtube_formats_need_a_linked_channel(login):
    d = login("cr_b").get("/api/creators/cr_b/pricing/estimate", params={"format": "youtube_video"}).json()
    assert d["enough_data"] is False and d["missing"][0]["fix"] == "Link your YouTube channel"
    short = login("cr_b").get("/api/creators/cr_b/pricing/estimate", params={"format": "short"}).json()
    assert short["enough_data"] and "Priced like a reel" in short["assumptions"][0]


def test_youtube_formats_use_the_linked_channel(login, youtube):
    b = login("cr_b")
    assert b.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 200
    d = b.get("/api/creators/cr_b/pricing/estimate", params={"format": "youtube_video"}).json()
    assert d["enough_data"] and d["data_source"] == "youtube_api" and d["data_label"] == "Estimate from YouTube data"
    assert {m["key"]: m["source"] for m in d["metrics"]} == {"subscribers": "youtube_api", "median_views": "youtube_api"}
    # 50,000 median views x Rs 140 per 1,000 (cr_b's niche rate may differ; it's views-based either way).
    assert d["range"]["low"] < d["range"]["high"] and d["missing"][0]["key"] == "engagement"


# ------------------------------------------------------------------ saved rate cards
def test_saved_rates_sit_next_to_the_estimate(login, db):
    a = login("cr_a")
    r = a.client.put("/api/creators/cr_a/rates/reel", json={"amount": 20_000, "note": "Includes one revision"}, headers=a.headers)
    assert r.status_code == 200, r.text
    card = r.json()
    assert card["amount"] == 20_000 and card["source"] == "manual" and card["estimate_now"]["range"]["low"] > 0
    assert card["estimate_at_save"]["range"] == card["estimate_now"]["range"]
    # Saving again replaces it, so a repeated request changes nothing.
    a.client.put("/api/creators/cr_a/rates/reel", json={"amount": 20_000, "note": "Includes one revision"}, headers=a.headers)
    a.client.put("/api/creators/cr_a/rates/story", json={"amount": 4_000}, headers=a.headers)
    cards = a.get("/api/creators/cr_a/rates").json()["cards"]
    assert [c["format"] for c in cards] == ["reel", "story"]
    # The reel rate is the typical rate the rate gap compares with.
    assert db.creators.find_one({"_id": "cr_a"})["current_rate"] == 20_000
    kit = a.get("/api/creators/cr_a/kit").json()
    assert kit["rates_kind"] == "your_rate" and kit["from_rate"] == 4_000
    assert [r["value"] for r in kit["rates"]] == ["₹20,000", "₹4,000"]
    assert [r["label"] for r in a.get("/api/creators/cr_a/kit?lang=hi").json()["rates"]] == ["1 रील", "1 स्टोरी"]
    assert a.delete("/api/creators/cr_a/rates/story").json()["ok"]
    assert a.delete("/api/creators/cr_a/rates/story").status_code == 404


# ------------------------------------------------------------------ live kit in Hindi, and its PDF
def test_live_kit_in_hindi_with_sources(login):
    a = login("cr_a")
    k = a.get("/api/creators/cr_a/kit?lang=hi").json()
    assert k["lang"] == "hi" and k["stats"][0]["label"] == "फ़ॉलोअर्स"
    assert all(s["source"] in ("instagram_api", "youtube_api", "manual", "synthetic") for s in k["stats"])
    assert any("ऀ" <= ch <= "ॿ" for ch in k["copy"]["bio"])
    r = a.get("/api/creators/cr_a/kit.pdf?lang=hi")
    assert r.status_code == 200 and r.content[:4] == b"%PDF"
    assert b"NotoSansDevanagari" in r.content  # the Hindi font is embedded
    assert a.get("/api/creators/cr_a/kit.pdf").status_code == 200


def test_hindi_pdf_without_text_shaping_says_so(login, monkeypatch):
    monkeypatch.setattr(pdf, "can_shape", lambda: False)
    a = login("cr_a")
    r = a.get("/api/creators/cr_a/kit.pdf?lang=hi")
    assert r.status_code == 503 and "uharfbuzz" in r.json()["detail"]
    assert a.get("/api/creators/cr_a/kit.pdf").status_code == 200  # English still works


def test_a_failed_ai_call_falls_back_to_the_template(login, monkeypatch, db):
    class Down:
        messages = None

        def __getattr__(self, _):
            raise RuntimeError("down")

    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AI_MODEL", "test-model")
    config.get_settings.cache_clear()
    db.ai_cache.delete_many({})
    monkeypatch.setattr(llm, "_client", Down())
    try:
        k = login("cr_a").get("/api/creators/cr_a/kit?lang=hi").json()
        assert k["copy_source"] == "template" and "DealMeet" in k["copy"]["bio"]
    finally:
        config.get_settings.cache_clear()


# ------------------------------------------------------------------ saved versions
def _save(actor, **kw):
    body = {"headline": "Tamil food reels that people save", "bio": "Home cooking in Tamil.", **kw}
    return actor.post("/api/creators/cr_a/kit/versions", json=body)


def test_versions_never_change_and_keep_their_own_pdf(login, db):
    a = login("cr_a")
    r1 = _save(a)
    assert r1.status_code == 201, r1.text
    v1 = r1.json()
    # The same save again returns the same version.
    again = _save(a)
    assert again.status_code == 200 and again.json()["id"] == v1["id"] and again.json()["created"] is False
    v2 = _save(a, headline="Tamil home cooking", sections={"rates": False}, lang="hi").json()
    assert v2["number"] == 2 and v2["lang"] == "hi"
    listed = a.get("/api/creators/cr_a/kit/versions").json()["versions"]
    assert [v["number"] for v in listed] == [2, 1] and all(v["created_at"] for v in listed)

    before = a.get(f"/api/creators/cr_a/kit/versions/{v1['id']}").json()["kit"]
    # Change the data the live kit is built from: the saved version stays as it was.
    a.client.put("/api/creators/cr_a/rates/reel", json={"amount": 99_000}, headers=a.headers)
    db.creators.update_one({"_id": "cr_a"}, {"$set": {"name": "Renamed"}})
    after = a.get(f"/api/creators/cr_a/kit/versions/{v1['id']}").json()["kit"]
    assert after == before and after["copy"]["headline"] == "Tamil food reels that people save"
    assert after["version"]["number"] == 1
    pdf_bytes = a.get(f"/api/creators/cr_a/kit/versions/{v1['id']}/pdf").content
    assert pdf_bytes[:4] == b"%PDF" and hashlib.sha256(pdf_bytes).hexdigest() == v1["pdf_sha256"]
    # Sections switched off are left out of that version.
    assert a.get(f"/api/creators/cr_a/kit/versions/{v2['id']}").json()["kit"]["rates"] is None


def test_kit_text_cant_promise_results(login):
    r = _save(login("cr_a"), headline="Guaranteed viral reach for your brand")
    assert r.status_code == 422 and "promise" in r.json()["detail"]


def test_version_limit(login, monkeypatch):
    monkeypatch.setattr(media_kit, "MAX_VERSIONS", 2)
    a = login("cr_a")
    _save(a, headline="One")
    _save(a, headline="Two")
    assert _save(a, headline="Three").status_code == 409


def test_public_page_shows_the_chosen_version_within_sharing_settings(client, login):
    a = login("cr_a")
    handle = a.get("/api/creators/cr_a/kit").json()["handle"]
    assert client.get(f"/api/public/{handle}").json()["version"] is None  # live view by default
    v = _save(a).json()
    assert a.client.put("/api/creators/cr_a/kit/public-view", json={"version_id": v["id"]}, headers=a.headers).status_code == 200
    page = client.get(f"/api/public/{handle}").json()
    assert page["version"]["number"] == 1 and page["copy"]["headline"] == "Tamil food reels that people save"
    assert page["stats"] and "public" not in page
    # Turning stats off hides them on the page, even from a saved version.
    a.post("/api/creators/cr_a/kit", json={"stats": False, "demographics": False, "rates": False})
    page = client.get(f"/api/public/{handle}").json()
    assert page["stats"] is None and page["formats"] is None and page["rates"] is None
    # The published version can't be deleted; another creator's version can't be picked.
    assert a.delete(f"/api/creators/cr_a/kit/versions/{v['id']}").status_code == 409
    b = login("cr_b")
    assert b.client.put("/api/creators/cr_b/kit/public-view", json={"version_id": v["id"]}, headers=b.headers).status_code == 404
    # Back to the live view.
    a.client.put("/api/creators/cr_a/kit/public-view", json={"version_id": None}, headers=a.headers)
    assert client.get(f"/api/public/{handle}").json()["version"] is None
    assert a.delete(f"/api/creators/cr_a/kit/versions/{v['id']}").json()["ok"]


@pytest.fixture()
def youtube(monkeypatch, db):
    from test_youtube import FakeYouTube

    from app.services import youtube_public as yt

    monkeypatch.setenv("YOUTUBE_API_KEY", "test-key")
    config.get_settings.cache_clear()
    db.yt_cache.delete_many({})
    db.rate_limits.delete_many({})
    fake = FakeYouTube()
    monkeypatch.setattr(yt.httpx, "get", fake.get)
    yield fake
    config.get_settings.cache_clear()
