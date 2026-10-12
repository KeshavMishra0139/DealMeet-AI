"""The AI growth coach: own data only, sources on every number, no promises, goals."""
from types import SimpleNamespace

import pytest

from app import config
from app.ai import llm
from app.routers.assistant import ASK_PER_HOUR
from app.services import coach


def _ask(actor, q):
    r = actor.post("/api/assistant/ask", json={"question": q})
    assert r.status_code == 200, r.text
    return r.json()


def test_only_creators_ask_about_their_own_data(client, login, db):
    assert client.post("/api/assistant/ask", json={"question": "Are my views growing?"}).status_code == 401
    assert login("br_senpai").post("/api/assistant/ask", json={"question": "Are my views growing?"}).status_code == 403
    assert login("cr_a").post("/api/assistant/ask", json={"question": "x"}).status_code == 422


def test_answers_list_the_numbers_used_and_their_sources(login, db):
    d = _ask(login("cr_a"), "Are my views growing?")
    assert d["intent"] == "trend" and d["trend_known"] is True
    assert d["answer"] and d["uncertain"] and d["written_by"] == "template"
    keys = {f["key"]: f for f in d["used"]}
    assert keys["median_views"]["source"] in ("manual", "synthetic") and keys["trend"]["value"]
    assert "median of" in d["answer"]


def test_fewer_than_six_posts_means_no_trend(login, db):
    me = login("new_creator")
    me.post("/api/creators", json={"name": "Tiny", "niche": "food", "audience_stage": "under_1k", "income_goal": 5000, "languages": ["ta"], "city": "Chennai"})
    d = _ask(me, "Is my reach going up?")
    assert d["trend_known"] is False and "can't tell a trend" in d["answer"]


def test_price_answers_use_the_fair_price_engine(login, db):
    d = _ask(login("cr_a"), "What should I charge for a reel?")
    fair = next(f for f in d["used"] if f["key"] == "fair")
    assert "₹" in fair["value"] and "estimate" in fair["label"].lower()
    assert "fair rate" in d["answer"] and "estimate" in d["uncertain"].lower()


def test_answers_are_cached_and_rate_limited(login, db):
    db.rate_limits.delete_many({})
    a = login("cr_b")
    assert _ask(a, "Which brands fit me now?")["cached"] is False
    assert _ask(a, "Which brands fit me now?")["cached"] is True
    codes = [a.post("/api/assistant/ask", json={"question": "Where are my deals?"}).status_code for _ in range(ASK_PER_HOUR)]
    assert codes[-1] == 429


class FakeModel:
    def __init__(self, answer):
        self.answer = answer
        self.messages = self

    def parse(self, **kw):
        return SimpleNamespace(stop_reason="end_turn", parsed_output=coach.CoachAnswer(**self.answer))


@pytest.fixture()
def model(monkeypatch, db):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AI_MODEL", "test-model")
    config.get_settings.cache_clear()
    db.ai_cache.delete_many({})
    db.coach_answers.delete_many({})

    def use(answer):
        monkeypatch.setattr(llm, "_client", FakeModel(answer))

    yield use
    config.get_settings.cache_clear()


def test_a_model_answer_that_promises_falls_back_to_the_template(login, model):
    model({"answer": "You will go viral and earnings are guaranteed.", "uncertain": "None."})
    assert _ask(login("cr_a"), "Are my views growing?")["written_by"] == "template"


def test_a_model_answer_with_invented_numbers_falls_back(login, model):
    model({"answer": "Your views grew 812% to 4,000,000.", "uncertain": "Small sample."})
    assert _ask(login("cr_a"), "Are my views growing?")["written_by"] == "template"


def test_a_grounded_model_answer_is_used(login, model):
    model({"answer": "Your recent posts look steady. Keep posting your best format.", "uncertain": "Six posts is a small sample."})
    d = _ask(login("cr_a"), "Are my views growing?")
    assert d["written_by"] == "ai" and d["used"]


def test_make_me_a_plan_sets_measurable_goals_and_tracks_progress(login, db):
    b = login("cr_b")
    b.get("/api/creators/cr_b/home")
    plan = b.post("/api/assistant/plan").json()
    assert plan["total"] == 3 and plan["done"] == 0
    for g in plan["goals"]:
        assert g["metric"] and g["target"] >= 1 and g["deadline"] > "2026-10-08"
    # Ticking a move off counts.
    first = plan["goals"][0]
    b.post(f"/api/creators/cr_b/moves/{first['move_id']}", json={"action": "done", "result": "worked"})
    after = b.get("/api/creators/cr_b/goals").json()["plan"]
    assert next(g for g in after["goals"] if g["move_id"] == first["move_id"])["done"] is True


def test_new_data_recalculates_the_plan_and_says_what_changed(login, db):
    me = login("new_creator")
    cid = me.post("/api/creators", json={"name": "Asha", "niche": "food", "audience_stage": "1k_10k", "income_goal": 5000, "languages": ["hi"], "city": "Pune"}).json()["id"]
    me.get(f"/api/creators/{cid}/home")
    me.post("/api/assistant/plan")
    me.post(f"/api/creators/{cid}/manual-metrics", json={"platform": "instagram", "followers": 9000, "avg_views": 20000})
    changes = me.get(f"/api/creators/{cid}/goals").json()["plan"]["data_changes"]
    assert changes and changes[-1]["reason"] == "New self-reported numbers"
    assert any(x.startswith("Followers:") for x in changes[-1]["changes"])
    assert any(x.startswith("Fair rate:") for x in changes[-1]["changes"])
