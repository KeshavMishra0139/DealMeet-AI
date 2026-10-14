"""Sign in with YouTube or Instagram and the profile is set up from that account, no form;
brands get their form filled in from their name."""
import uuid
from dataclasses import replace
from types import SimpleNamespace

from conftest import Actor
from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)

from app.ai import brand_setup, llm
from app.config import get_settings
from app.services import auth as au
from app.services import instagram as ig


def _creator(client, **fields) -> Actor:
    user = au.new_user("creator", fields.pop("name", "Ravi"), email=f"r-{uuid.uuid4().hex[:8]}@example.test", **fields)
    return Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))


def test_a_youtube_sign_in_is_set_up_from_the_channel(client, youtube, db, monkeypatch):
    from app.services import youtube_analytics as yta

    seen = {}
    monkeypatch.setattr(yta, "connect", lambda cid, token: seen.update(cid=cid, token=token) or {})
    a = _creator(client, youtube_channel_id=CHANNEL)
    r = a.post("/api/creators/auto", json={"access_token": "ya29.test-access-token-123"})
    assert r.status_code == 200, r.text
    out = r.json()
    c = db.creators.find_one({"_id": out["id"]})
    assert c["name"] == "Test Kitchen" and c["handle"] == "testkitchen" and c["niche"] == "food"
    assert c["platforms"] == ["youtube"] and set(c["formats"]) == {"shorts", "long"}
    assert c["followers"] == 21_300 and c["city"] is None and c["auto_setup"]["source"] == "youtube"
    assert "city" in c["auto_setup"]["review"] and c["channels"]["youtube"]["channel_id"] == CHANNEL  # the channel is linked too
    assert seen == {"cid": out["id"], "token": "ya29.test-access-token-123"}  # Analytics in the same step
    assert any("Analytics connected" in n for n in out["notes"])
    assert a.get("/api/auth/me").json()["profile"]
    assert a.get(f"/api/creators/{out['id']}/home").status_code == 200  # no city is fine everywhere
    assert a.post("/api/creators/auto", json={}).status_code == 409  # once


def test_without_a_social_account_the_form_is_used(client, db):
    a = _creator(client)
    assert a.post("/api/creators/auto", json={}).status_code == 409


def test_an_instagram_sign_in_is_set_up_from_its_profile_and_captions(client, db, monkeypatch):
    a = _creator(client, name="ravi.cooks", instagram_uid="17841")
    db.connections.insert_one({"user_id": a.user["id"], "creator_id": None, "platform": "instagram", "ig_user_id": "17841", "token_enc": "x", "status": "connected"})
    monkeypatch.setattr(ig, "_token", lambda conn: "token")

    def graph(path, token, **params):
        if path == "me":
            return {"username": "ravi.cooks", "name": "Ravi Cooks", "account_type": "MEDIA_CREATOR", "followers_count": 4200, "media_count": 40}
        return {"data": [{"caption": c, "media_product_type": "REELS"} for c in ("Easy poha recipe for breakfast", "Masala dosa at home", "Dal tadka recipe")]}

    monkeypatch.setattr(ig, "_graph", graph)
    monkeypatch.setattr(ig, "sync", lambda cid: {})
    out = a.post("/api/creators/auto", json={}).json()
    c = db.creators.find_one({"_id": out["id"]})
    assert c["name"] == "Ravi Cooks" and c["handle"] == "ravi.cooks" and c["niche"] == "food"
    assert c["formats"] == ["reels"] and c["followers"] == 4200 and c["platforms"] == ["instagram"]


def _brand(client, email):
    user = au.new_user("brand", "Anita", email=email)
    return Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))


def test_a_brand_form_is_filled_from_its_company_email_and_name(client, db):
    b = _brand(client, f"anita-{uuid.uuid4().hex[:4]}@thalamfoods.in")
    assert b.get("/api/brands/setup/hints").json() == {"name": "Thalamfoods", "website": "https://thalamfoods.in"}
    s = b.post("/api/brands/setup/suggest", json={"name": "Thalam Foods", "website": "thalamfoods.in"}).json()
    assert s["niches"] == ["food"] and s["by_ai"] is False and s["website"] == "https://thalamfoods.in"
    assert s["languages"] and s["ages"] and s["budget_monthly"] in brand_setup.BUDGETS


def test_the_ai_suggestion_is_checked_against_the_apps_lists(client, db, monkeypatch):
    settings = replace(get_settings(), ai_api_key="test-key", ai_model="test-model")
    monkeypatch.setattr(llm, "get_settings", lambda: settings)
    draft = brand_setup.BrandDraft(category="Budget earbuds", description="Earbuds and speakers.", niches=["tech", "gaming", "music"],
                                   ages=["18-24", "99+"], gender="male", languages=["hi", "xx"], budget_monthly=130_000, goal="World domination", known=True)
    monkeypatch.setattr(llm, "_get_client", lambda: SimpleNamespace(messages=SimpleNamespace(parse=lambda **kw: SimpleNamespace(stop_reason="end_turn", parsed_output=draft))))
    db.ai_cache.delete_many({})
    b = _brand(client, "team@example.test")
    s = b.post("/api/brands/setup/suggest", json={"name": "Taal Audio"}).json()
    assert s["by_ai"] and s["known"] and s["category"] == "Budget earbuds"
    assert s["niches"] == ["tech", "gaming"] and s["ages"] == ["18-24"] and s["languages"] == ["hi"]
    assert s["budget_monthly"] == 150_000 and s["goal"] == "Awareness"


def test_cities_cover_every_state_and_union_territory_with_delhi_ncr_first(client):
    from app.seed.catalog import CITIES

    states = {s for s, _ in CITIES.values()}
    assert len(states) == 36  # 28 states and 8 union territories
    assert {"Uttar Pradesh", "Delhi", "Haryana", "Ladakh", "Sikkim", "Puducherry"} <= states
    cities = client.get("/api/meta").json()["cities"]
    ncr = [c["name"] for c in cities if c["group"] == "Delhi NCR"]
    assert cities[0]["group"] == "Delhi NCR" and set(ncr) == {"Delhi", "Noida", "Greater Noida", "Ghaziabad", "Gurugram", "Faridabad"}
    assert {"Lucknow", "Kanpur", "Varanasi"} <= {c["name"] for c in cities if c["group"] == "Uttar Pradesh"}
