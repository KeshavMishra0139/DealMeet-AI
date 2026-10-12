"""Assistant actions: tools run as the signed-in user, sends and publishes need a
confirmation that expires and runs once, and the model only picks a tool."""
import time
from types import SimpleNamespace

import pytest

from app import config
from app.ai import llm
from app.services import assistant_tools as at

H = "lst_senpai_hoodie"


def _draft_campaign(b):
    from test_campaigns import COMPLETE

    return b.post("/api/brands/br_senpai/campaigns", json=COMPLETE).json()["id"]


def test_tools_are_listed_by_role(login, client):
    assert client.get("/api/assistant/tools").status_code == 401
    brand = {t["name"] for t in login("br_senpai").get("/api/assistant/tools").json()["tools"]}
    creator = {t["name"] for t in login("cr_a").get("/api/assistant/tools").json()["tools"]}
    assert "publish_campaign" in brand and "publish_campaign" not in creator and "draft_pitch" in creator
    assert login("cr_a").post("/api/assistant/tools/publish_campaign", json={"args": {"listing_id": H}}).status_code == 403
    assert login("cr_a").post("/api/assistant/tools/drop_database", json={"args": {}}).status_code == 404


def test_read_tools_run_directly(login):
    r = login("br_senpai").post("/api/assistant/tools/campaign_status", json={"args": {"listing_id": H}}).json()
    assert r["mode"] == "read" and r["result"]["status"] == "live" and "applications" in r["result"]
    price = login("cr_a").post("/api/assistant/tools/explain_price", json={"args": {}}).json()["result"]
    assert price["range"]["low"] < price["range"]["high"] and price["note"] == "An estimate, not a quote."


def test_a_brand_cant_act_on_another_brands_campaign(login, db):
    other = login("br_thalam")
    assert other.post("/api/assistant/tools/campaign_status", json={"args": {"listing_id": H}}).status_code == 403
    assert other.post("/api/assistant/tools/pause_campaign", json={"args": {"listing_id": H}}).status_code == 403
    assert db.listings.find_one({"_id": H})["status"] == "live"


def test_invalid_arguments_never_run(login):
    b = login("br_senpai")
    r = b.post("/api/assistant/tools/draft_campaign_brief", json={"args": {"title": "x"}})
    assert r.status_code == 422 and "draft_campaign_brief" in r.json()["detail"]
    assert b.post("/api/assistant/tools/campaign_status", json={"args": {}}).status_code == 422


def test_an_unconfirmed_proposal_does_nothing_and_a_confirmed_one_runs_once(login, db):
    b = login("br_senpai")
    lid = _draft_campaign(b)
    r = b.post("/api/assistant/tools/publish_campaign", json={"args": {"listing_id": lid}}).json()
    assert r["mode"] == "confirm" and r["proposal"]["expires_in_s"] == 600 and "Publish" in r["proposal"]["summary"]
    assert db.listings.find_one({"_id": lid})["status"] == "draft"  # nothing happened yet
    pid = r["proposal"]["id"]
    assert login("br_thalam").post(f"/api/assistant/proposals/{pid}/confirm").status_code == 404  # not theirs
    done = b.post(f"/api/assistant/proposals/{pid}/confirm").json()
    assert done["mode"] == "confirmed" and db.listings.find_one({"_id": lid})["status"] == "live"
    again = b.post(f"/api/assistant/proposals/{pid}/confirm")
    assert again.status_code == 409 and "done" in again.json()["detail"]
    actions = [e["action"] for e in db.audit.find({"proposal_id": pid})]
    assert "assistant_tool" in actions and "assistant_confirm" in actions


def test_proposals_expire_and_can_be_cancelled(login, db):
    b = login("br_senpai")
    pid = b.post("/api/assistant/tools/pause_campaign", json={"args": {"listing_id": H}}).json()["proposal"]["id"]
    db.assistant_proposals.update_one({"_id": pid}, {"$set": {"expires_ts": time.time() - 1}})
    assert b.post(f"/api/assistant/proposals/{pid}/confirm").status_code == 410
    assert db.listings.find_one({"_id": H})["status"] == "live"
    pid = b.post("/api/assistant/tools/pause_campaign", json={"args": {"listing_id": H}}).json()["proposal"]["id"]
    assert b.post(f"/api/assistant/proposals/{pid}/cancel").json()["status"] == "cancelled"
    assert b.post(f"/api/assistant/proposals/{pid}/confirm").status_code == 409
    assert db.listings.find_one({"_id": H})["status"] == "live"


def test_sending_a_pitch_needs_confirmation(login, db):
    c = login("cr_b")
    p = c.post("/api/assistant/tools/draft_pitch", json={"args": {"brand_id": "br_thalam"}}).json()
    assert p["mode"] == "draft" and p["result"]["status"] == "draft"
    prop = c.post("/api/assistant/tools/send_pitch", json={"args": {"pitch_id": p["result"]["id"]}}).json()
    assert db.pitches.find_one({"_id": p["result"]["id"]})["status"] == "draft"
    c.post(f"/api/assistant/proposals/{prop['proposal']['id']}/confirm")
    assert db.pitches.find_one({"_id": p["result"]["id"]})["status"] == "sent"


def test_messages_pick_a_tool_without_a_model(login, db):
    b = login("br_senpai")
    r = b.post("/api/assistant/act", json={"message": "Pause the winter hoodie drop"}).json()
    assert r["tool"] == "pause_campaign" and r["args"] == {"listing_id": H} and r["mode"] == "confirm" and r["chosen_by"] == "rules"
    assert db.listings.find_one({"_id": H})["status"] == "live"
    assert login("cr_a").post("/api/assistant/act", json={"message": "Explain my fair rate"}).json()["tool"] == "explain_price"
    assert login("cr_a").post("/api/assistant/act", json={"message": "Delete everything"}).json()["tool"] is None


class FakeModel:
    def __init__(self, choice):
        self.choice = choice
        self.messages = self

    def parse(self, **kw):
        return SimpleNamespace(stop_reason="end_turn", parsed_output=at.ToolChoice(**self.choice))


@pytest.fixture()
def model(monkeypatch, db):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "test")
    monkeypatch.setenv("AI_MODEL", "test-model")
    config.get_settings.cache_clear()
    db.ai_cache.delete_many({})

    def use(choice):
        monkeypatch.setattr(llm, "_client", FakeModel(choice))

    yield use
    config.get_settings.cache_clear()


def test_the_model_only_chooses_and_its_arguments_are_checked(login, model, db):
    b = login("br_thalam")
    # The model names another brand's campaign: the same ownership check refuses it.
    model({"tool": "pause_campaign", "args": {"listing_id": H}})
    assert b.post("/api/assistant/act", json={"message": "pause it"}).status_code == 403
    model({"tool": "draft_campaign_brief", "args": {"title": "ok"}})  # too short
    assert b.post("/api/assistant/act", json={"message": "new brief"}).status_code == 422
    model({"tool": "drop_everything", "args": {}})
    assert b.post("/api/assistant/act", json={"message": "drop it"}).json()["tool"] is None
    assert db.listings.find_one({"_id": H})["status"] == "live"
