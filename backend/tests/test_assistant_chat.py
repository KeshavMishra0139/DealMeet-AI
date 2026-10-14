"""The AI assistant window: one conversation for creators and brands, answering from the
account's own data and doing tasks only with the user's confirmation."""
from dataclasses import replace
from types import SimpleNamespace

import pytest

from app.ai import assistant, llm
from app.ai.assistant import ChatAction, ChatTurn
from app.config import get_settings


@pytest.fixture()
def model(monkeypatch, db):
    """A fake model: answers with state["out"] (or the next of state["outs"]) and records what it was sent."""
    settings = replace(get_settings(), ai_api_key="test-key", ai_model="test-model")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    state = {"out": None, "outs": [], "calls": []}

    class Messages:
        def parse(self, **kw):
            if kw["output_format"] is not ChatTurn:  # other AI copy (a pitch's text...): templates
                return SimpleNamespace(stop_reason="end_turn", parsed_output=None)
            state["calls"].append(kw)
            out = state["outs"].pop(0) if state["outs"] else state["out"]
            return SimpleNamespace(stop_reason="end_turn", parsed_output=out)

    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(messages=Messages()))
    return state


def _say(actor, text, cid=None):
    r = actor.post("/api/assistant/chat", json={"message": text, "conversation_id": cid})
    assert r.status_code == 200, r.text
    return r.json()


def test_without_ai_the_window_still_answers_from_the_creators_numbers(login, db):
    a = login("cr_a")
    state = a.get("/api/assistant/chat").json()
    assert state["conversation"] is None and state["starters"] and state["ai"] is False
    out = _say(a, "What should I charge a brand?")
    reply = out["messages"][1]
    assert reply["role"] == "assistant" and reply["written_by"] == "template" and "₹" in reply["text"]
    again = a.get("/api/assistant/chat").json()["conversation"]
    assert again["id"] == out["conversation_id"] and [m["role"] for m in again["messages"]] == ["user", "assistant"]


def test_a_brand_asks_to_pause_a_campaign_and_confirms_in_the_window(login, db):
    b = login("br_senpai")
    out = _say(b, "Pause the winter hoodie drop")
    action = out["messages"][1]["action"]
    assert action["status"] == "pending" and "Pause" in action["proposal"]["summary"]
    assert db.listings.find_one({"_id": "lst_senpai_hoodie"})["status"] != "paused"  # nothing happens before Confirm
    conv = b.post(f"/api/assistant/chat/{out['conversation_id']}/actions/{action['proposal']['id']}/confirm").json()["conversation"]
    assert conv["messages"][1]["action"]["status"] == "done" and conv["messages"][-1]["text"].startswith("Paused")
    from app.services import campaigns as camp

    assert camp.status_of(db.listings.find_one({"_id": "lst_senpai_hoodie"})) == "paused"
    # Someone else can't see or settle this conversation.
    other = login("br_thalam")
    assert other.post(f"/api/assistant/chat/{out['conversation_id']}/actions/{action['proposal']['id']}/confirm").status_code == 404
    assert other.post("/api/assistant/chat", json={"message": "hi", "conversation_id": out["conversation_id"]}).status_code == 404


def test_the_ai_replies_with_the_conversation_and_the_accounts_data(login, db, model):
    a = login("cr_a")
    model["out"] = ChatTurn(reply="Your views are steady. Want me to draft a pitch?", suggestions=["Yes, draft one", "How do I grow?"])
    first = _say(a, "How am I doing?")
    msg = first["messages"][1]
    assert msg["written_by"] == "ai" and msg["text"].startswith("Your views") and msg["suggestions"] == ["Yes, draft one", "How do I grow?"]
    sent = model["calls"][0]
    assert "DealMeet AI" in sent["system"] and "Median views" in sent["system"]  # the account's own numbers
    _say(a, "And what about my price?", first["conversation_id"])
    turns = model["calls"][1]["messages"]
    assert [t["role"] for t in turns] == ["user", "assistant", "user"] and turns[-1]["content"] == "And what about my price?"


def test_the_ai_drafts_a_pitch_by_brand_name_and_reports_the_result(login, db, model):
    a = login("cr_b")
    model["outs"] = [
        ChatTurn(reply="On it.", action=ChatAction(tool="draft_pitch", args_json='{"brand_id": "Thalam Foods", "lang": "en"}')),
        ChatTurn(reply="I drafted a pitch to Thalam Foods. It isn't sent: review it under Pitches."),
    ]
    out = _say(a, "Draft a pitch to Thalam Foods")
    msg = out["messages"][1]
    assert msg["action"]["tool"] == "draft_pitch" and msg["action"]["status"] == "done" and msg["action"]["link"] == "/creator/pitches"
    assert msg["text"].startswith("I drafted a pitch") and db.pitches.count_documents({"creator_id": "cr_b", "brand_id": "br_thalam", "status": "draft"}) >= 1
    assert "Result of draft_pitch" in model["calls"][1]["messages"][-1]["content"]


def test_a_brand_cannot_use_creator_tools(login, db, model):
    b = login("br_senpai")
    model["out"] = ChatTurn(reply="Sure.", action=ChatAction(tool="draft_pitch", args_json='{"brand_id": "br_thalam"}'))
    msg = _say(b, "Draft a pitch")["messages"][1]
    assert msg["action"] is None and db.pitches.count_documents({"brand_id": "br_thalam", "creator_id": None}) == 0


def test_invented_amounts_and_promises_fall_back_to_templates(login, db, model):
    a = login("cr_a")
    model["out"] = ChatTurn(reply="Charge ₹99,999 per reel.")
    msg = _say(a, "What should I charge?")["messages"][1]
    assert msg["written_by"] == "template" and msg["ai_status"] == "money" and "99,999" not in msg["text"]
    assert len(model["calls"]) == 2  # asked again once, then templates
    model["calls"].clear()
    model["out"] = ChatTurn(reply="Do this and you'll get guaranteed income.")
    msg = _say(a, "How do I earn more?")["messages"][1]
    assert msg["written_by"] == "template" and "guaranteed" not in msg["text"].lower()


def test_amounts_from_the_context_are_fine():
    ctx = "Fair rate per reel (estimate): ₹17K–18K. Your typical rate: ₹7,300."
    assert assistant.money_grounded("Ask for about ₹17,000 to ₹18K, not ₹7,300.", ctx)
    assert not assistant.money_grounded("Ask for ₹25,000.", ctx)
    assert assistant.rupees("Rs 1.2 lakh and INR 500") == [120000.0, 500.0]
    assert sorted(assistant.rupees("₹1,500–2,200 or ₹17–18K")) == [1500.0, 2200.0, 17000.0, 18000.0]
    assert assistant.rupees("your followers 5,000") == []


def test_conversations_are_deleted_with_the_account_or_on_request(client, db):
    from test_youtube_profile import _new_creator

    a, cid = _new_creator(client, db)
    _say(a, "Hi")
    assert db.chats.count_documents({"creator_id": cid}) == 1
    assert a.delete("/api/assistant/chats").json() == {"deleted": 1}
    _say(a, "Hi again")
    assert a.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 200
    assert db.chats.count_documents({"creator_id": cid}) == 0


def test_greetings_get_a_warm_reply_even_without_ai(login, db):
    for persona, word in (("cr_a", "fair price"), ("br_senpai", "campaign")):
        a = login(persona)
        for text in ("Hi", "hello", "Namaste"):
            reply = _say(a, text)["messages"][1]
            assert reply["text"].startswith("Hi") and "DealMeet AI" in reply["text"] and word in reply["text"], reply["text"]
        assert _say(a, "thanks")["messages"][1]["text"].startswith("You're welcome")
    # A question that starts with a greeting is still a question.
    assert "₹" in _say(login("cr_a"), "Hi, what should I charge a brand?")["messages"][1]["text"]


def test_openrouter_replies_with_line_breaks_inside_the_json_are_read(monkeypatch, db, client):
    import httpx

    from test_ai_fallback import openrouter  # noqa: F401
    settings = replace(get_settings(), ai_api_key=None, openrouter_api_key="or-key", ai_model="anthropic/test-model")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    raw = '{"reply": "Hi Ravi.\n\nHow can I help today?", "action": null, "suggestions": ["What should I charge?"]}'

    def post(url, headers=None, json=None, timeout=None):
        return httpx.Response(200, json={"choices": [{"message": {"content": raw}, "finish_reason": "stop"}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm.httpx, "post", post)
    out, status = llm.converse("t", "system", [{"role": "user", "content": "Hi"}], ChatTurn)
    assert status == "ai" and out.reply == "Hi Ravi.\n\nHow can I help today?"


def test_the_last_ai_failure_and_its_fix_show_on_health(monkeypatch, db, client):
    import httpx

    settings = replace(get_settings(), ai_api_key=None, openrouter_api_key="or-key", ai_model="anthropic/test-model")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)

    def post(url, headers=None, json=None, timeout=None):
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(llm.httpx, "post", post)
    assert llm.converse("assistant_chat", "system", [{"role": "user", "content": "Hi"}], ChatTurn) == (None, "failed")
    err = client.get("/api/health").json()["modes"]["ai_last_error"]
    assert err["reason"] == "OpenRouter error 402" and "credits" in err["hint"] and err["task"] == "assistant_chat"
