"""Trust-first deal rail: escrow before posting, verification before payout."""
from datetime import date

import pytest

from app.services import deals as rail


def _act(client, deal, role, action, **kw):
    return client.post(f"/api/deals/{deal}/action", json={"role": role, "action": action, **kw})


def test_low_offer_counter_and_full_rail(client, db):
    v = client.get("/api/deals/dl_a_senpai?role=creator").json()
    assert v["alerts"][0]["kind"] == "low_offer" and "58%" in v["alerts"][0]["text"]
    assert _act(client, "dl_a_senpai", "creator", "counter", amount=17400).status_code == 200
    v = _act(client, "dl_a_senpai", "brand", "accept_counter").json()
    assert v["stage"] == "contract" and v["amount"] == 17400
    assert v["contract"]["signed_by_creator"] and v["contract"]["signed_by_brand"]
    # Posting before escrow is funded is refused.
    assert _act(client, "dl_a_senpai", "creator", "submit_post", url="https://www.instagram.com/reel/X1/").status_code == 409
    paid = client.post("/api/deals/dl_a_senpai/pay").json()
    assert paid["mode"] == "simulated" and paid["deal"]["stage"] == "escrow_funded"
    assert _act(client, "dl_a_senpai", "creator", "submit_post", url="https://example.com/x").status_code == 409
    assert _act(client, "dl_a_senpai", "creator", "submit_post", url="https://www.instagram.com/reel/X1/").json()["stage"] == "live"
    v = _act(client, "dl_a_senpai", "brand", "confirm").json()
    assert v["stage"] == "paid"
    assert v["payouts"][0]["amount"] == 17400 and v["payouts"][0]["utr"].startswith("SIM")
    assert all(c["ok"] for c in v["verification"]["checks"])
    inv = db.invoices.find_one({"deal_id": "dl_a_senpai"})
    assert inv["status"] == "paid"
    pdf = client.get(f"/api/invoices/{inv['_id']}.pdf")
    assert pdf.status_code == 200 and pdf.content[:4] == b"%PDF"


def test_escrow_needs_both_signatures(client, db):
    _act(client, "dl_b_tiffin", "creator", "accept")
    d = db.deals.find_one({"_id": "dl_b_tiffin"})
    assert d["stage"] == "contract" and d["contract"]["signed_by_creator"] and not d["contract"]["signed_by_brand"]
    assert _act(client, "dl_b_tiffin", "brand", "fund").status_code == 409
    _act(client, "dl_b_tiffin", "brand", "sign")
    assert client.post("/api/deals/dl_b_tiffin/pay").json()["deal"]["stage"] == "escrow_funded"


def test_auto_release_when_brand_goes_quiet(client, db, monkeypatch):
    v = client.get("/api/deals/dl_a_pixelforge?role=creator").json()
    assert v["stage"] == "live" and v["auto_release_on"] == "2026-10-09"
    monkeypatch.setattr(rail, "today", lambda: date(2026, 10, 9))
    v = client.get("/api/deals/dl_a_pixelforge?role=creator").json()
    assert v["stage"] == "paid" and v["verification"]["auto"]


def test_collective_one_payment_and_split(client, db):
    pack = client.post("/api/listings/lst_thalam_collective/collective", json={}).json()
    booked = client.post("/api/listings/lst_thalam_collective/collective/book", json={"member_ids": [m["id"] for m in pack["members"]]}).json()
    col = client.post(f"/api/collectives/{booked['id']}/fund").json()
    assert col["funded"]
    member = col["members"][0]
    # Collective splits are fixed: no counters.
    assert _act(client, member["deal_id"], "creator", "counter", amount=99999).status_code == 409
    v = _act(client, member["deal_id"], "creator", "accept").json()
    assert v["stage"] == "escrow_funded" and v["escrow"]["collective"]
    _act(client, member["deal_id"], "creator", "submit_post", url="https://www.instagram.com/reel/COL1/")
    col = client.post(f"/api/collectives/{booked['id']}/release").json()
    assert col["paid_out"] == member["price"]


def test_media_kit_and_public_booking(client, db):
    kit = client.get("/api/creators/cr_a/kit").json()
    assert kit["rates"][0]["value"] == "₹17K–18K"
    assert kit["has_simulated"] and kit["reference_note"]
    assert "said" not in kit["copy"]["bio"].lower()  # never quotes the reference creator
    assert client.get("/api/creators/cr_a/kit.pdf").content[:4] == b"%PDF"
    r = client.post("/api/public/creator.b/book", json={"brand_name": "Kadai Co", "email": "a@kadai.test", "budget": 1500, "deliverable": "reel"})
    assert r.status_code == 200
    d = db.deals.find_one({"creator_id": "cr_b", "source": "link_in_bio"})
    assert d["stage"] == "offer"
    assert db.brands.find_one({"_id": d["brand_id"]})["verified"] is False


@pytest.mark.parametrize("url", ["https://www.instagram.com/reel/Cx9_a-1/", "https://youtube.com/shorts/abc123", "https://youtu.be/abc123"])
def test_post_url_accepts_official_links(url):
    assert rail.POST_URL.match(url)
