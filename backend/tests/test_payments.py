"""Honest payments: nothing is funded, paid or verified unless that's what happened."""
import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import config
from app.main import app
from app.services import payments

SECRET = "test_secret"
WEBHOOK_SECRET = "whsec_test"


@pytest.fixture()
def razorpay(monkeypatch):
    """Razorpay test mode with a fake orders API. `calls` records each order request."""
    monkeypatch.setenv("RAZORPAY_KEY_ID", "rzp_test_key")
    monkeypatch.setenv("RAZORPAY_KEY_SECRET", SECRET)
    monkeypatch.setenv("RAZORPAY_WEBHOOK_SECRET", WEBHOOK_SECRET)
    config.get_settings.cache_clear()
    state = {"calls": [], "fail": False, "n": 0}

    def fake_post(url, **kw):
        state["calls"].append(kw["json"])
        if state["fail"]:
            raise httpx.ConnectError("down")
        state["n"] += 1
        req = httpx.Request("POST", url)
        return httpx.Response(200, json={"id": f"order_{state['n']}", "amount": kw["json"]["amount"]}, request=req)

    monkeypatch.setattr(payments.httpx, "post", fake_post)
    yield state
    config.get_settings.cache_clear()


def _sign(order_id: str, payment_id: str) -> str:
    return hmac.new(SECRET.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()


def _signed_contract(login):
    """Creator B accepts Tiffin Diaries' offer and both sign: ready to fund (₹1,500)."""
    b, tiffin = login("cr_b"), login("pg_tiffin")
    b.post("/api/deals/dl_b_tiffin/action", json={"action": "accept"})
    tiffin.post("/api/deals/dl_b_tiffin/action", json={"action": "sign"})
    return b, tiffin


def _checkout(actor, deal, order_id, payment_id, signature=None):
    return actor.post(
        f"/api/deals/{deal}/pay/verify",
        json={"razorpay_order_id": order_id, "razorpay_payment_id": payment_id, "razorpay_signature": signature or _sign(order_id, payment_id)},
    )


def test_a_failed_provider_call_is_an_error_not_a_simulated_payment(login, db, razorpay):
    _, tiffin = _signed_contract(login)
    razorpay["fail"] = True
    r = tiffin.post("/api/deals/dl_b_tiffin/pay")
    assert r.status_code == 502 and "no money has moved" in r.json()["detail"]
    assert db.deals.find_one({"_id": "dl_b_tiffin"})["stage"] == "contract"
    assert db.payments.count_documents({"ref_id": "dl_b_tiffin"}) == 0


def test_without_a_provider_outside_demo_mode_nothing_is_funded(login, db, monkeypatch):
    _, tiffin = _signed_contract(login)
    monkeypatch.setenv("DEMO_MODE", "0")
    config.get_settings.cache_clear()
    try:
        r = tiffin.post("/api/deals/dl_b_tiffin/pay")
        assert r.status_code == 503 and "no money has moved" in r.json()["detail"]
        assert db.deals.find_one({"_id": "dl_b_tiffin"})["stage"] == "contract"
    finally:
        monkeypatch.delenv("DEMO_MODE")
        config.get_settings.cache_clear()


def test_checkout_must_match_the_stored_order_and_is_used_once(login, db, razorpay):
    _, tiffin = _signed_contract(login)
    order = tiffin.post("/api/deals/dl_b_tiffin/pay").json()
    assert order["mode"] == "razorpay-test" and razorpay["calls"][0]["amount"] == 150_000
    # A double click reuses the open order.
    assert tiffin.post("/api/deals/dl_b_tiffin/pay").json()["order_id"] == order["order_id"]
    assert len(razorpay["calls"]) == 1
    # A made-up order, or a bad signature, is refused.
    assert _checkout(tiffin, "dl_b_tiffin", "order_999", "pay_1").status_code == 400
    assert _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_1", signature="bad").status_code == 400
    ok = _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_1")
    assert ok.status_code == 200 and ok.json()["stage"] == "escrow_funded"
    assert ok.json()["escrow"]["mode"] == "razorpay-test"
    # The same checkout reported twice is harmless; one payment never funds a second order.
    assert _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_1").status_code == 200
    db.payments.insert_one({"_id": "order_other", "mode": "razorpay-test", "kind": "deal", "ref_id": "dl_b_tiffin", "amount": 1500, "status": "created"})
    assert _checkout(tiffin, "dl_b_tiffin", "order_other", "pay_1").status_code == 409


def test_an_order_for_another_deal_or_amount_is_refused(login, db, razorpay):
    _, tiffin = _signed_contract(login)
    order = tiffin.post("/api/deals/dl_b_tiffin/pay").json()
    db.payments.update_one({"_id": order["order_id"]}, {"$set": {"ref_id": "dl_a_senpai"}})
    assert _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_2").status_code == 400
    db.payments.update_one({"_id": order["order_id"]}, {"$set": {"ref_id": "dl_b_tiffin", "amount": 999}})
    assert _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_2").status_code == 409
    assert db.deals.find_one({"_id": "dl_b_tiffin"})["stage"] == "contract"


def _webhook(client, event: dict, event_id: str, secret: str = WEBHOOK_SECRET):
    body = json.dumps(event).encode()
    sig = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return client.post("/api/payments/razorpay/webhook", content=body, headers={"x-razorpay-signature": sig, "x-razorpay-event-id": event_id, "content-type": "application/json"})


def _captured(order_id: str, payment_id: str, paise: int) -> dict:
    return {"event": "payment.captured", "payload": {"payment": {"entity": {"id": payment_id, "order_id": order_id, "amount": paise, "status": "captured"}}}}


def test_webhook_checks_its_signature_and_applies_each_event_once(client, login, db, razorpay):
    _, tiffin = _signed_contract(login)
    order = tiffin.post("/api/deals/dl_b_tiffin/pay").json()
    event = _captured(order["order_id"], "pay_w1", 150_000)
    assert _webhook(client, event, "evt_1", secret="wrong").status_code == 400
    assert db.deals.find_one({"_id": "dl_b_tiffin"})["stage"] == "contract"
    # The brand closed the checkout tab: the webhook funds the deal instead.
    r = _webhook(client, event, "evt_1")
    assert r.status_code == 200 and r.json() == {"ok": True}
    d = db.deals.find_one({"_id": "dl_b_tiffin"})
    assert d["stage"] == "escrow_funded" and d["escrow"]["ref"] == "pay_w1"
    events = len(d["timeline"])
    assert _webhook(client, event, "evt_1").json()["duplicate"] is True
    assert len(db.deals.find_one({"_id": "dl_b_tiffin"})["timeline"]) == events
    # A captured amount that doesn't match the order changes nothing.
    assert _webhook(client, _captured(order["order_id"], "pay_w2", 1), "evt_2").json()["ignored"] == "amount mismatch"


def test_webhook_needs_its_secret(client, db):
    r = client.post("/api/payments/razorpay/webhook", content=b"{}", headers={"x-razorpay-signature": "x"})
    assert r.status_code == 503


def test_real_payment_stops_at_payout_not_connected(login, db, razorpay):
    b, tiffin = _signed_contract(login)
    order = tiffin.post("/api/deals/dl_b_tiffin/pay").json()
    _checkout(tiffin, "dl_b_tiffin", order["order_id"], "pay_r1")
    b.post("/api/deals/dl_b_tiffin/action", json={"action": "submit_post", "url": "https://www.instagram.com/reel/R1/"})
    v = tiffin.post("/api/deals/dl_b_tiffin/action", json={"action": "approve"}).json()
    assert v["stage"] == "verified" and v["payout"]["status"] == "not_connected" and v["payouts"] == []
    assert any(a["kind"] == "payout_not_connected" for a in v["alerts"])
    assert db.invoices.find_one({"deal_id": "dl_b_tiffin"})["status"] == "pending"
    assert "paid" not in " ".join(e["note"].lower() for e in v["timeline"] if e["stage"] == "verified").replace("nothing has been paid out", "")


def test_brand_can_ask_for_a_revision(login, db):
    a, pixel = login("cr_a"), login("br_pixelforge")
    assert pixel.post("/api/deals/dl_a_pixelforge/action", json={"action": "request_revision", "note": ""}).status_code == 409
    v = pixel.post("/api/deals/dl_a_pixelforge/action", json={"action": "request_revision", "note": "Tag @pixelforge in the caption"}).json()
    assert v["stage"] == "escrow_funded" and v["revisions"][0]["reason"] == "Tag @pixelforge in the caption"
    creator_view = a.get("/api/deals/dl_a_pixelforge").json()
    assert creator_view["alerts"][0]["kind"] == "revision"
    v = a.post("/api/deals/dl_a_pixelforge/action", json={"action": "submit_post", "url": "https://www.instagram.com/reel/FIXED1/"}).json()
    assert v["stage"] == "live" and v["post_check"]["source"] == "not_connected"
    # Only the brand reviews; the creator can't approve their own post.
    assert a.post("/api/deals/dl_a_pixelforge/action", json={"action": "approve"}).status_code == 400


def test_fund_action_cant_be_called_directly(login, db):
    _, tiffin = _signed_contract(login)
    r = tiffin.post("/api/deals/dl_b_tiffin/action", json={"action": "fund"})
    assert r.status_code == 409
    assert db.deals.find_one({"_id": "dl_b_tiffin"})["stage"] == "contract"


def test_seeded_payouts_carry_no_bank_reference(db):
    for d in db.deals.find({"stage": "paid"}):
        assert d["payout"]["status"] == "simulated"
        assert all("utr" not in p and "upi" not in p for p in d["payouts"])


def test_health_reports_real_modes(client, db):
    modes = client.get("/api/health").json()["modes"]
    assert modes["payments"] == "simulated" and modes["payouts"] == "simulated"  # demo mode, no keys
    assert modes["social"] == "not_connected" and modes["post_checks"].startswith("brand review")


def test_social_connect_is_not_simulated(login, db, monkeypatch):
    me = login("cr_a")
    platforms = me.get("/api/creators/cr_a/connections").json()["platforms"]
    assert {p["status"] for p in platforms} == {"unavailable"}
    monkeypatch.setenv("DEMO_MODE", "0")
    config.get_settings.cache_clear()
    try:
        # Outside demo mode a real account can't fill its profile with sample insights.
        body = {"name": "Real Creator", "niche": "food", "audience_stage": "1k_10k", "income_goal": 10000, "languages": ["ta"], "city": "Chennai", "sample_insights": True}
        c = TestClient(app, headers={"X-Requested-With": "t"})
        c.post("/api/auth/signup", json={"email": "real@example.com", "password": "long enough", "name": "R", "role": "creator"})
        assert c.post("/api/creators", json=body).status_code == 422
    finally:
        monkeypatch.delenv("DEMO_MODE")
        config.get_settings.cache_clear()
