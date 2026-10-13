"""Fan Proof, the AI Pitch Builder and the Brand Fan Inbox."""
import json
from types import SimpleNamespace

import pytest

from app import config
from app.ai import llm
from app.engines.fair_price import fair_price
from app.services import fan_proof as fp
from app.services import fan_proof_hooks
from app.services import pitches as pt

THALAM = {"_id": "br_thalam", "name": "Thalam Foods", "public_handles": {"instagram": "@thalamfoods"}}
PRIVATE = ("email", "phone", "income_history", "income_goal", "manual", "creator_id", "facts_text")


def _post(text, platform="instagram", source="instagram_api", at="2025-03-14T10:00:00+00:00", n=1):
    base = {"platform": platform, "source": source, "published_at": at, "permalink": f"https://example.test/p/{n}"}
    return {**base, "title": text, "description": ""} if platform == "youtube" else {**base, "caption": text}


# ------------------------------------------------------------------ Fan Proof
def test_fan_proof_matches_handles_and_hashtags_but_not_paid_posts():
    posts = [
        _post("Morning chai with @thalamfoods masala", n=1),
        _post("My go-to #ThalamFoods sambar", n=2),
        _post("#adventure day, packed @thalamfoods snacks", n=3),  # #adventure isn't #ad
        _post("Weekend recipe", platform="youtube", source="youtube_api", n=4) | {"description": "Spices from #thalamfoods"},
        _post("#ad Thanks @thalamfoods for the hamper", n=5),
        _post("Paid partnership with @thalamfoods", n=6),
        _post("#collab with #thalamfoods", n=7),
        _post("#Sponsored: @thalamfoods", n=8),
        _post("Big fan of #thalamfoodsfan pages", n=9),  # a different tag
        _post("@thalamfoods.official is a parody", n=10),  # a different handle
        _post("Typed in: love @thalamfoods", source="manual", n=11),  # only API posts count
        _post("Sample: love @thalamfoods", source="synthetic", n=12),
    ]
    found = fp.mentions(posts, THALAM)
    assert sorted(p["permalink"][-1] for p in found) == ["1", "2", "3", "4"]


def test_fan_proof_is_stored_per_platform_recomputed_and_deleted_on_disconnect(db):
    db.brands.update_one({"_id": "br_thalam"}, {"$set": {"public_handles": {"instagram": "@thalamfoods"}}})
    rows = [
        {"creator_id": "cr_b", "platform": "instagram", "post_id": "a", "caption": "Breakfast with @thalamfoods", "published_at": "2025-03-02T08:00:00+00:00", "permalink": "https://instagram.test/a", "source": "instagram_api"},
        {"creator_id": "cr_b", "platform": "instagram", "post_id": "b", "caption": "More #thalamfoods please", "published_at": "2025-06-02T08:00:00+00:00", "permalink": "https://instagram.test/b", "source": "instagram_api"},
        {"creator_id": "cr_b", "platform": "instagram", "post_id": "c", "caption": "#ad @thalamfoods", "published_at": "2024-01-02T08:00:00+00:00", "permalink": "https://instagram.test/c", "source": "instagram_api"},
    ]
    db.posts.insert_many(rows)
    assert fp.recompute("cr_b", "instagram") == 1
    s = fp.summary("cr_b", "br_thalam")
    assert s["label"] == "Fan since March 2025 · 2 unpaid mentions" and s["links"] == ["https://instagram.test/a", "https://instagram.test/b"]
    assert "following" not in json.dumps(s).lower()
    db.posts.delete_one({"post_id": "a"})
    fp.recompute("cr_b", "instagram")
    assert fp.summary("cr_b", "br_thalam")["count"] == 1
    fan_proof_hooks.on_disconnect("cr_b", "instagram")
    assert fp.summary("cr_b", "br_thalam") is None


def test_linking_youtube_builds_fan_proof_and_unlinking_removes_it(login, youtube, db):
    db.brands.update_one({"_id": "br_thalam"}, {"$set": {"public_handles": {}}})
    youtube.videos[0]["snippet"]["description"] = "Cooked with #ThalamFoods masala"
    b = login("cr_b")
    assert b.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 200
    assert fp.summary("cr_b", "br_thalam")["platforms"] == ["youtube"]
    b.delete("/api/creators/cr_b/youtube/link")
    assert fp.summary("cr_b", "br_thalam") is None


# ------------------------------------------------------------------ pitch builder
def _draft(actor, cid="cr_b", brand="br_thalam", lang="en"):
    r = actor.post(f"/api/creators/{cid}/pitches", json={"brand_id": brand, "lang": lang})
    assert r.status_code == 200, r.text
    return r.json()


def test_pitches_are_the_creators_own(client, login):
    assert client.post("/api/creators/cr_b/pitches", json={"brand_id": "br_thalam"}).status_code == 401
    assert login("cr_a").post("/api/creators/cr_b/pitches", json={"brand_id": "br_thalam"}).status_code == 403
    assert login("br_thalam").post("/api/creators/cr_b/pitches", json={"brand_id": "br_thalam"}).status_code == 403
    p = _draft(login("cr_b"))
    a = login("cr_a")
    assert a.post(f"/api/creators/cr_a/pitches/{p['id']}/send").status_code == 404  # not theirs
    assert login("cr_b").post("/api/creators/cr_b/pitches", json={"brand_id": "br_nope"}).status_code == 404
    assert login("cr_b").post("/api/creators/cr_b/pitches", json={"brand_id": "br_thalam", "lang": "fr"}).status_code == 422


def test_a_draft_uses_your_facts_and_the_fair_price_engine(login, db):
    d = _draft(login("cr_b"))
    assert d["status"] == "draft" and d["written_by"] == "template" and len(d["content_ideas"]) == 3
    assert len(d["pitch"].split()) <= 150 and "Thalam Foods" in d["pitch"]
    assert all(f["source"] in ("instagram_api", "youtube_api", "manual", "synthetic") for f in d["facts"])
    c, b = db.creators.find_one({"_id": "cr_b"}), db.brands.find_one({"_id": "br_thalam"})
    assert d["suggested_price_range"]["range"] == fair_price(c, b, {"deliverables": [{"kind": "reel", "count": 1}]}, with_model=False)["range"]
    assert d["suggested_price_range"]["estimate"] is True
    hi = _draft(login("cr_b"), lang="hi")
    assert any("ऀ" <= ch <= "ॿ" for ch in hi["pitch"])


class FakeModel:
    def __init__(self, out):
        self.out = out
        self.messages = self

    def parse(self, **kw):
        return SimpleNamespace(stop_reason="end_turn", parsed_output=pt.PitchCopy.model_construct(**self.out))


@pytest.fixture()
def model(monkeypatch, db):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AI_MODEL", "test-model")
    config.get_settings.cache_clear()
    db.ai_cache.delete_many({})

    def use(out):
        monkeypatch.setattr(llm, "_client", FakeModel(out))

    yield use
    config.get_settings.cache_clear()


IDEAS = ["A breakfast reel with the masala", "A Sunday sambar story", "A spice-box tour"]


def test_the_price_range_never_comes_from_the_model(login, model, db):
    model({"subject": "Sambar season with Thalam", "pitch": "I cook South Indian breakfasts for families and would love to feature your masala in my next reel. Can we talk? It would be ₹2,00,000.", "content_ideas": IDEAS})
    d = _draft(login("cr_b"))
    assert d["written_by"] == "template"  # quoted a number that isn't in the facts
    model({"subject": "Sambar season with Thalam", "pitch": "I cook South Indian breakfasts for families and would love to feature your masala in my next reel. Can we talk?", "content_ideas": IDEAS})
    d = _draft(login("cr_b"))
    assert d["written_by"] == "ai" and d["subject"] == "Sambar season with Thalam"
    c, b = db.creators.find_one({"_id": "cr_b"}), db.brands.find_one({"_id": "br_thalam"})
    assert d["suggested_price_range"]["range"] == fair_price(c, b, {"deliverables": [{"kind": "reel", "count": 1}]}, with_model=False)["range"]


def test_model_pitches_that_promise_or_run_long_fall_back(login, model):
    model({"subject": "Guaranteed viral", "pitch": "This will go viral for sure, guaranteed results for your masala launch with my audience.", "content_ideas": IDEAS})
    assert _draft(login("cr_b"))["written_by"] == "template"
    model({"subject": "A long one", "pitch": " ".join(["word"] * 151), "content_ideas": IDEAS})
    assert _draft(login("cr_b"))["written_by"] == "template"


def test_edits_keep_to_your_numbers_and_the_copy_rules(login):
    b = login("cr_b")
    d = _draft(b)
    url = f"/api/creators/cr_b/pitches/{d['id']}"
    assert b.patch(url, json={"pitch": "My reels are guaranteed to go viral for your brand, every single time."}).status_code == 422
    r = b.patch(url, json={"pitch": "My reels get 2,000,000 views each and I would love to work with Thalam."})
    assert r.status_code == 422 and "2,000,000" in r.json()["detail"]
    ok = b.patch(url, json={"pitch": "I make 2 breakfast reels a week in Tamil and would love to work with Thalam Foods."})
    assert ok.status_code == 200 and "breakfast reels" in ok.json()["pitch"]


# ------------------------------------------------------------------ sending, share links, weekly limit
def test_sending_to_a_brand_on_the_platform_lands_in_its_inbox_only(login):
    b = login("cr_b")
    d = _draft(b)
    sent = b.post(f"/api/creators/cr_b/pitches/{d['id']}/send").json()
    assert sent["status"] == "sent" and sent["share"] is None and sent["duplicate"] is False
    assert b.post(f"/api/creators/cr_b/pitches/{d['id']}/send").json()["duplicate"] is True
    again = _draft(b)
    assert b.post(f"/api/creators/cr_b/pitches/{again['id']}/send").status_code == 409  # one open pitch per brand
    assert [p["id"] for p in login("br_thalam").get("/api/brands/br_thalam/fan-inbox").json()["items"]] == [d["id"]]
    assert login("br_senpai").get("/api/brands/br_senpai/fan-inbox").json()["items"] == []
    assert login("br_senpai").get("/api/brands/br_thalam/fan-inbox").status_code == 403


def test_a_brand_not_on_the_platform_gets_a_revocable_share_link(client, login):
    b = login("cr_b")
    d = _draft(b, brand="br_unc_notebook")
    sent = b.post(f"/api/creators/cr_b/pitches/{d['id']}/send").json()
    assert sent["status"] == "shared" and len(sent["share"]["slug"]) >= 16
    page = client.get(f"/api/p/{sent['share']['slug']}").json()
    assert page["pitch"] == d["pitch"] and page["creator"]["handle"]
    assert not any(f'"{k}"' in json.dumps(page) for k in PRIVATE)
    b.post(f"/api/creators/cr_b/pitches/{d['id']}/revoke")
    assert client.get(f"/api/p/{sent['share']['slug']}").status_code == 404
    assert client.get("/api/p/not-a-real-slug").status_code == 404


def test_five_sent_pitches_a_week(login, db):
    b = login("cr_b")
    brands = [x["_id"] for x in db.brands.find({"kind": "brand", "claimed": True, "_id": {"$regex": "^br_"}}).limit(6)]
    codes = [b.post(f"/api/creators/cr_b/pitches/{_draft(b, brand=bid)['id']}/send").status_code for bid in brands]
    assert codes == [200] * 5 + [429]
    assert b.get("/api/creators/cr_b/pitches").json()["sent_this_week"] == 5


# ------------------------------------------------------------------ the Brand Fan Inbox
def test_inbox_sorts_filters_and_accepting_makes_an_offer(login, db):
    for cid in ("cr_b", "cr_a"):
        c = login(cid)
        c.post(f"/api/creators/{cid}/pitches/{_draft(c, cid=cid)['id']}/send")
    t = login("br_thalam")
    items = t.get("/api/brands/br_thalam/fan-inbox").json()["items"]
    assert len(items) == 2 and items[0]["fit"] >= items[1]["fit"]
    db.connections.insert_one({"_id": "cn_t", "creator_id": "cr_b", "user_id": "us_cr_b", "platform": "instagram", "status": "connected"})
    only = t.get("/api/brands/br_thalam/fan-inbox", params={"connected_only": "true"}).json()["items"]
    assert [i["creator"]["id"] for i in only] == ["cr_b"]
    pid = next(i["id"] for i in items if i["creator"]["id"] == "cr_b")
    assert login("br_senpai").post(f"/api/fan-inbox/{pid}/accept", json={}).status_code == 404
    acc = t.post(f"/api/fan-inbox/{pid}/accept", json={"amount": 6_000}).json()
    assert acc["status"] == "accepted" and acc["deal_id"]
    deal = db.deals.find_one({"_id": acc["deal_id"]})
    assert deal["stage"] == "offer" and deal["amount"] == 6_000 and deal["brand_id"] == "br_thalam" and deal["creator_id"] == "cr_b"
    assert t.post(f"/api/fan-inbox/{pid}/accept", json={}).json()["duplicate"] is True
    assert t.post(f"/api/fan-inbox/{pid}/decline", json={}).status_code == 409
    other = next(i["id"] for i in items if i["creator"]["id"] == "cr_a")
    assert t.post(f"/api/fan-inbox/{other}/decline", json={"note": "Not this season"}).json()["status"] == "declined"
    notes = login("cr_a").get("/api/creators/cr_a/pitches").json()["notifications"]
    assert notes and "Thanks for your pitch to Thalam Foods" in notes[0]["text"]


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


def test_a_regional_language_pitch_needs_the_ai_and_says_what_it_got(login):
    # No AI here: a Tamil pitch comes back in English, and says Tamil was asked for.
    ta = _draft(login("cr_b"), lang="ta")
    assert ta["lang"] == "en" and ta["lang_requested"] == "ta" and ta["written_by"] == "template"
    assert ta["pitch"].startswith("Hi ")
