"""Consent-based marketplace, brand matching and the Collective Builder."""
from app.engines.brand_matching import matches, redact
from app.engines.collective import build
from app.services import consent as cs
from app.services import creator_ctx as cc


def _get(db, coll, _id):
    return db[coll].find_one({"_id": _id})


def test_consent_scopes_and_revocation(db, client):
    a = _get(db, "creators", "cr_a")
    assert cs.scopes_for(a, "br_senpai") == {"stats": True, "demographics": False, "rate_card": True}
    # No grant: the creator's defaults apply.
    assert cs.scopes_for(a, "br_thalam") == {"stats": True, "demographics": False, "rate_card": False}
    # A revoked lister can't find the creator at all.
    assert cs.scopes_for(a, "xx_fameboost") is None
    cs.revoke("cr_a", "br_senpai")
    assert cs.scopes_for(_get(db, "creators", "cr_a"), "br_senpai") is None
    hoodie = _get(db, "listings", "lst_senpai_hoodie")
    ids = {m["id"] for m in matches(hoodie, _get(db, "brands", "br_senpai"))["items"]}
    assert "cr_a" not in ids
    actions = [x["action"] for x in db.consent_audit.find({"creator_id": "cr_a"})]
    assert "revoked" in actions


def test_undiscoverable_creator_is_hidden_everywhere(db, client):
    client.post("/api/creators/cr_b/privacy", json={"discoverable": False})
    thalam = _get(db, "brands", "br_thalam")
    listing = _get(db, "listings", "lst_thalam_collective")
    assert "cr_b" not in {m["id"] for m in matches(listing, thalam)["items"]}
    assert "cr_b" not in {m["id"] for m in build(listing, thalam)["members"]}
    assert client.get("/api/brands/br_thalam/creators/cr_b").status_code == 404


def test_brand_view_respects_scopes_and_logs_views(db, client):
    r = client.get("/api/brands/br_senpai/creators/cr_a?listing_id=lst_senpai_hoodie").json()
    assert r["stats"] is not None and r["rate_card"] is not None
    assert r["demographics"] is None
    # Without the demographics scope, reasons keep the conclusion but not the numbers.
    assert all("%" not in x for x in r["fit"]["reasons"])
    assert db.consent_audit.count_documents({"creator_id": "cr_a", "lister_id": "br_senpai", "action": "viewed"}) >= 2


def test_redaction():
    reasons = ["93% of the audience is in the target ages (18-24)", "Audience concentrated in Delhi, Mumbai"]
    assert redact(reasons, {"demographics": False}) == ["Audience ages match your target", "Audience is in your target regions"]
    assert redact(reasons, {"demographics": True}) == reasons


def test_collective_builder_constraints(db):
    thalam = _get(db, "brands", "br_thalam")
    listing = _get(db, "listings", "lst_thalam_collective")
    pack = build(listing, thalam)
    assert 10 <= pack["size"] <= 20
    assert pack["total"] <= pack["budget"]
    assert abs(sum(m["split"] for m in pack["members"]) - 1) < 0.01
    assert pack["combined_reach"] <= pack["raw_reach"]
    member_ids = {m["id"] for m in pack["members"]}
    # Engineered low-trust profiles are excluded automatically.
    assert not member_ids & {"cr_f08", "cr_f14"}
    assert {e["id"] for e in pack["excluded"] if e["reason"].startswith("Trust")} == {"cr_f08", "cr_f14"}
    # Raising the trust bar never adds members below it.
    strict = build(listing, thalam, trust_min=85)
    assert all(m["trust"]["score"] >= 85 for m in strict["members"])


def test_opting_in_puts_creator_b_in_the_pack(db, client):
    r = client.post(
        "/api/creators/cr_b/apply",
        json={"listing_id": "lst_thalam_collective", "scopes": {"stats": True, "demographics": True, "rate_card": False}},
    )
    assert r.json()["status"] == "opted_in"
    pack = client.post("/api/listings/lst_thalam_collective/collective", json={}).json()
    assert pack["size"] == 20
    b = next(m for m in pack["members"] if m["id"] == "cr_b")
    assert b["opted_in"] and b["price"] >= 1_500


def test_matches_rank_and_summary(db):
    senpai = _get(db, "brands", "br_senpai")
    m = matches(_get(db, "listings", "lst_senpai_hoodie"), senpai)
    assert m["items"][0]["id"] == "cr_a"
    assert m["summary"].startswith(f"{m['total']} creators fit;")
    assert m["items"][-1]["trust"]["score"] < 50  # weak trust signals ranked last


def test_brand_offer_reaches_creator(db, client):
    r = client.post("/api/offers", json={"brand_id": "br_thalam", "creator_id": "cr_b", "listing_id": "lst_thalam_sambar", "amount": 1500})
    assert r.status_code == 200
    offers = cc.pipeline(_get(db, "creators", "cr_b"))["offers"]
    assert any(o["brand"] == "Thalam Foods" for o in offers)


def test_booking_a_collective_creates_one_offer_per_member(db, client):
    pack = client.post("/api/listings/lst_senpai_collective/collective", json={}).json()
    ids = [m["id"] for m in pack["members"]]
    r = client.post("/api/listings/lst_senpai_collective/collective/book", json={"member_ids": ids}).json()
    assert r["members"] == len(ids)
    col = db.collectives.find_one({"_id": r["id"]})
    assert abs(sum(m["split"] for m in col["members"]) - 1) < 0.01
    assert db.deals.count_documents({"collective_id": r["id"], "stage": "offer"}) == len(ids)
