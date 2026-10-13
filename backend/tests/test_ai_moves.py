"""The AI words each week's moves for the creator; the engine still picks them and their numbers."""
import pytest
from test_ai_fallback import fake_ai  # noqa: F401  (fixture)
from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)
from test_youtube_profile import _new_creator

from app.ai import llm
from app.ai import moves as ai_moves
from app.ai.moves import MoveCopy, MovesCopy


@pytest.fixture()
def ai_on(fake_ai, monkeypatch, db):
    settings = llm.get_settings()
    monkeypatch.setattr(ai_moves, "get_settings", lambda: settings)
    monkeypatch.setattr(ai_moves, "personalize_soon", lambda plan_id: None)  # the tests call it directly
    db.ai_cache.delete_many({})
    return fake_ai


def _plan(a, cid, db):
    a.get(f"/api/creators/{cid}/home")
    return db.plans.find_one({"creator_id": cid}, sort=[("week", -1)])


def _copy(plan, **over):
    return MovesCopy(moves=[
        MoveCopy(id=m["id"], title=over.get("title", f"Fitness move {i}"), reason=over.get("reason", "Your workout videos are where people watch most."),
                 title_hi=over.get("title_hi", "फ़िटनेस के लिए कदम"), reason_hi="आपके वर्कआउट वीडियो सबसे ज़्यादा देखे जाते हैं।")
        for i, m in enumerate(plan["moves"], 1)
    ])


def test_the_ai_rewords_the_weeks_moves_in_english_and_hindi(client, youtube, db, ai_on):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    plan = _plan(a, cid, db)
    kinds = [m["kind"] for m in plan["moves"]]
    ai_on["output"] = _copy(plan)
    assert ai_moves.personalize(plan["_id"])
    moves = a.get(f"/api/creators/{cid}/home").json()["plan"]["moves"]
    assert [m["kind"] for m in moves] == kinds  # the engine's choice stands
    assert moves[0]["title"] == "Fitness move 1" and moves[0]["hi"]["title"] == "फ़िटनेस के लिए कदम" and moves[0]["written_by"] == "ai"
    assert not ai_moves.personalize(plan["_id"])  # already worded: no second call


def test_wording_that_breaks_the_rules_keeps_the_templates(client, youtube, db, ai_on):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    plan = _plan(a, cid, db)
    before = [m["title"] for m in plan["moves"]]
    for bad in ({"reason": "This gets you 987654 more views."}, {"title_hi": "Not Hindi at all"}):
        db.ai_cache.delete_many({})
        ai_on["output"] = _copy(plan, **bad)
        assert not ai_moves.personalize(plan["_id"])
    ai_on["output"] = MovesCopy(moves=_copy(plan).moves[:1])  # a move missing
    db.ai_cache.delete_many({})
    assert not ai_moves.personalize(plan["_id"])
    assert [m["title"] for m in db.plans.find_one({"_id": plan["_id"]})["moves"]] == before


def test_a_move_already_acted_on_keeps_its_words(client, youtube, db, ai_on):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    plan = _plan(a, cid, db)
    first = plan["moves"][0]
    db.plans.update_one({"_id": plan["_id"], "moves.id": first["id"]}, {"$set": {"moves.$.status": "done"}})
    open_moves = [m for m in plan["moves"] if m["id"] != first["id"]]
    ai_on["output"] = MovesCopy(moves=[MoveCopy(id=m["id"], title="New words", reason="Because of your recent videos.", title_hi="नए शब्द", reason_hi="आपके हाल के वीडियो की वजह से।") for m in open_moves])
    assert ai_moves.personalize(plan["_id"])
    saved = {m["id"]: m for m in db.plans.find_one({"_id": plan["_id"]})["moves"]}
    assert saved[first["id"]]["title"] == first["title"] and all(saved[m["id"]]["title"] == "New words" for m in open_moves)


def test_no_ai_no_change_and_no_hourly_cap_by_default(client, youtube, db):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    plan = _plan(a, cid, db)
    assert not ai_moves.personalize(plan["_id"])
    assert llm.MAX_CALLS_PER_HOUR == 0 and all(llm._allow_call() for _ in range(500))
