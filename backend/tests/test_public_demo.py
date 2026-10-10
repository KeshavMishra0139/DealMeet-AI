"""A public, shared demo: size and record limits, honest booking replies, and
fixes found before deploying."""
from fastapi.testclient import TestClient

from app.engines import spam
from app.main import app

FULL = "This shared demo is full"


def _onboard(client, **kw):
    body = {"name": "Cap Test", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["ta"], "city": "Chennai", **kw}
    return client.post("/api/creators", json=body)


def test_oversized_requests_are_refused(client, db):
    r = client.post("/api/ai/tag", content=b'{"captions": ["' + b"x" * 300_000 + b'"]}', headers={"content-type": "application/json"})
    assert r.status_code == 413
    assert _onboard(client, captions=["y" * 2201]).status_code == 422  # longer than an Instagram caption


def test_visitor_records_are_capped(client, db):
    db.creators.insert_many([{"_id": f"cr_fill_{i}", "created_by": "onboarding", "niche": "food", "handle": f"fill{i}", "name": "x"} for i in range(100)])
    r = _onboard(client)
    assert r.status_code == 429 and FULL in r.json()["detail"]


def test_unknown_api_paths_are_404_not_the_web_app(client, db):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and "text/html" not in r.headers.get("content-type", "")


def test_blank_captions_dont_break_onboarding(client, db):
    assert _onboard(client, captions=["   ", ""]).status_code == 200


def test_booking_reply_is_honest_and_the_email_is_not_kept(client, db):
    r = client.post("/api/public/creator.b/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 2000}).json()
    assert "Nothing is charged yet" in r["message"] and "held in escrow" not in r["message"]
    guest = db.brands.find_one({"_id": {"$regex": "^br_guest_"}})
    assert "contact" not in guest and "a@b.co" not in str(guest)


def test_guest_brand_doesnt_see_a_fair_price_the_creator_hides(client, db):
    client.post("/api/creators/cr_a/kit", json={"stats": True, "demographics": False, "rates": False})
    r = client.post("/api/public/creator.a/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 2000}).json()
    deal_id = r["track"].split("/brand/deals/")[1].split("?")[0]
    brand_view = client.get(f"/api/deals/{deal_id}?role=brand").json()
    assert brand_view["fair_total"] is None and not any(a["kind"] == "low_offer" for a in brand_view["alerts"])
    assert client.get(f"/api/deals/{deal_id}?role=creator").json()["fair_total"]


def test_either_side_can_cancel_before_escrow(client, db):
    r = client.post("/api/public/creator.b/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 2000}).json()
    deal_id = r["track"].split("/brand/deals/")[1].split("?")[0]
    client.post(f"/api/deals/{deal_id}/action", json={"role": "creator", "action": "accept"})
    v = client.get(f"/api/deals/{deal_id}?role=creator").json()
    assert any(a["id"] == "withdraw" for a in v["actions"])
    out = client.post(f"/api/deals/{deal_id}/action", json={"role": "creator", "action": "withdraw"}).json()
    assert out["stage"] == "declined"


def test_follower_price_needs_the_stats_scope(client, db):
    client.post("/api/creators/cr_a/consents/br_senpai", json={"scopes": {"stats": False, "demographics": False, "rate_card": False}})
    r = client.get("/api/brands/br_senpai/creators/cr_a?listing_id=lst_senpai_hoodie").json()
    assert r["fair"]["follower_price"] is None


def test_ordinary_brand_copy_is_not_flagged_as_spam():
    def hits(t):
        return [label for rx, label in spam.PATTERNS if rx.search(t)]

    assert hits("Work from home this season, show your followers our hoodie") == []
    assert hits("Buy 5k followers now") and hits("Earn 50,000 a week from home")


def test_invoice_late_advice_matches_what_the_app_does(client, db):
    alert = next(a for a in client.get("/api/creators/cr_a/home").json()["pipeline"]["alerts"] if a["kind"] == "invoice_late")
    assert "Download the invoice PDF" in alert["detail"] and "attached" not in alert["detail"]


def test_trust_says_when_its_inputs_are_sample_data(client, db):
    kit = client.get("/api/creators/cr_a/kit").json()
    assert "follower history" in kit["trust"]["simulated"]


def test_health_reports_a_shared_demo_only_when_auto_reset_is_on(client, db, monkeypatch):
    assert client.get("/api/health").json()["shared_demo"] is False
    from app import config

    monkeypatch.setenv("DEMO_RESET_MINUTES", "30")
    config.get_settings.cache_clear()
    try:
        assert TestClient(app).get("/api/health").json()["shared_demo"] is True
    finally:
        monkeypatch.delenv("DEMO_RESET_MINUTES")
        config.get_settings.cache_clear()
