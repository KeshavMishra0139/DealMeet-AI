"""What brands and creators are told must match what the app actually does:
audience numbers stay hidden without consent, alerts describe real behaviour,
and data the demo generates is labelled simulated."""
import re

from app.engines.brand_matching import matches
from app.engines.fair_price import fit_reason
from app.engines.matching import redact_cautions

# Sentences that carry audience numbers (ages, languages, cities, gender).
AUDIENCE_NUMBERS = re.compile(r"\d+% of the audience|^All of the audience|Audience concentrated in|women, matching")


def _texts_with_numbers(texts):
    return [t for t in texts if AUDIENCE_NUMBERS.search(t)]


def test_cautions_lose_their_numbers_without_consent():
    cautions = [
        "45% of the audience is in the target ages (18-24)",
        "Only 30% of the audience speaks Tamil",
        "Audience is mostly outside South",
    ]
    assert redact_cautions(cautions, {"demographics": False}) == [
        "Audience ages only partly match your target",
        "Much of the audience speaks other languages",
        "Audience is mostly outside South",
    ]
    assert redact_cautions(cautions, {"demographics": True}) == cautions


def test_fit_step_reason_respects_scopes():
    fit = {"score": 97, "reasons": ["Makes anime edits", "93% of the audience is in the target ages (13-17)"], "cautions": []}
    assert fit_reason(fit) == "Fit 97/100. Makes anime edits; 93% of the audience is in the target ages (13-17)."
    assert fit_reason(fit, {"demographics": False}) == "Fit 97/100. Makes anime edits; Audience ages match your target."
    weak = {"score": 30, "reasons": [], "cautions": ["Only 20% of the audience speaks Tamil"]}
    assert fit_reason(weak, {"demographics": False}) == "Fit 30/100. Much of the audience speaks other languages."
    assert fit_reason({"score": 50, "reasons": [], "cautions": []}) == "Fit 50/100."


def test_brand_profile_hides_audience_numbers_without_consent(client, db):
    # Senpai has stats and rate card from Creator A, but not demographics.
    r = client.get("/api/brands/br_senpai/creators/cr_a?listing_id=lst_senpai_hoodie").json()
    assert r["scopes"]["demographics"] is False
    shown = [s["reason"] for s in r["fair"]["steps"]] + r["fit"]["reasons"] + r["fit"]["cautions"]
    assert _texts_with_numbers(shown) == []
    assert any("Audience ages match your target" in s["reason"] for s in r["fair"]["steps"] if s["key"] == "fit")


def test_brand_profile_shows_audience_numbers_with_consent(client, db):
    # Creator B shares demographics with Thalam Foods.
    r = client.get("/api/brands/br_thalam/creators/cr_b?listing_id=lst_thalam_collective").json()
    assert r["scopes"]["demographics"] is True
    fit_step = next(s for s in r["fair"]["steps"] if s["key"] == "fit")
    assert AUDIENCE_NUMBERS.search(fit_step["reason"])


def test_no_match_list_leaks_audience_numbers(db):
    checked = 0
    for listing in db.listings.find():
        brand = db.brands.find_one({"_id": listing["owner_id"]})
        if not brand:
            continue  # creator-to-creator collabs have no brand console
        for row in matches(listing, brand)["items"]:
            if row["scopes"].get("demographics"):
                continue
            checked += 1
            leaked = _texts_with_numbers(row["reasons"] + row["cautions"])
            assert leaked == [], (listing["_id"], row["id"], leaked)
    assert checked > 50


def test_late_confirmation_alerts_describe_real_behaviour(client, db):
    alert = next(a for a in client.get("/api/creators/cr_a/home").json()["pipeline"]["alerts"] if a["kind"] == "verify_late")
    assert "nudged" not in alert["detail"] and "overdue" in alert["detail"]
    deal = client.get("/api/deals/dl_a_pixelforge?role=brand").json()
    days = next(a for a in deal["alerts"] if a["kind"] == "verify_late")["detail"]
    left = re.search(r"in (\d+) day", days).group(1)
    console = client.get("/api/brands/br_pixelforge/console").json()
    item = next(n for n in console["needs_you"] if n["deal_id"] == "dl_a_pixelforge")
    assert f"auto-releases in {left} day" in item["detail"]


def test_declined_collective_shares_return_to_the_brand(client, db):
    pack = client.post("/api/listings/lst_thalam_collective/collective", json={}).json()
    booked = client.post("/api/listings/lst_thalam_collective/collective/book", json={"member_ids": [m["id"] for m in pack["members"]]}).json()
    col = client.post(f"/api/collectives/{booked['id']}/fund").json()
    assert col["refunded"] == 0
    first, second = col["members"][:2]
    for m in (first, second):
        client.post(f"/api/deals/{m['deal_id']}/action", json={"role": "creator", "action": "decline"})
    col = client.get(f"/api/collectives/{booked['id']}").json()
    assert col["refunded"] == first["price"] + second["price"]


def test_onboarding_sample_insights_are_labelled_simulated(client, db):
    body = {
        "name": "Test Creator",
        "niche": "food",
        "audience_stage": "1k_10k",
        "income_goal": 10000,
        "languages": ["ta"],
        "city": "Chennai",
        "connected": {"instagram": True},
    }
    cid = client.post("/api/creators", json=body).json()["id"]
    c = db.creators.find_one({"_id": cid})
    for field in ("reels", "audience", "follower_history", "comment_insights", "followers"):
        assert c["provenance"].get(field) == "simulated", field
    home = client.get(f"/api/creators/{cid}/home").json()
    assert home["rate_gap"] is None or "high" != home["rate_gap"].get("confidence")
    money = client.get(f"/api/creators/{cid}/money").json()
    simulated = money["fair"]["why"]["simulated_fields"]
    assert "views" in simulated

    # A typed follower count is the creator's own; only generated data is simulated.
    typed = client.post("/api/creators", json={**body, "name": "Typed Creator", "followers": 4200, "connected": {}}).json()["id"]
    t = db.creators.find_one({"_id": typed})
    assert "followers" not in t["provenance"] and t["provenance"]["audience"] == "simulated"


def test_trust_filter_reasons_and_tip_name_the_real_cause(db):
    from app.engines.collective import build

    listing = db.listings.find_one({"_id": "lst_senpai_collective"})
    brand = db.brands.find_one({"_id": listing["owner_id"]})
    strict = build(listing, brand, budget=80_000, trust_min=80)
    by_trust = [e for e in strict["excluded"] if e["reason"].startswith("Trust")]
    assert by_trust
    for e in by_trust:
        score = int(re.match(r"Trust (\d+)", e["reason"]).group(1))
        # A decent score only misses the brand's higher bar: no warning sign is quoted.
        assert (":" in e["reason"]) == (score < 60), e
    if strict["size"] < 10:
        assert any("lower the trust minimum" in n for n in strict["notes"])
    default = build(listing, brand, budget=80_000)
    assert not any("lower the trust minimum" in n for n in default["notes"])


def test_new_brands_are_not_marked_verified(client, db):
    body = {"name": "Test Brand", "category": "Snacks", "description": "", "niches": ["food"], "ages": ["18-24"], "gender": "any",
            "languages": ["hi"], "cities": [], "budget_monthly": 50_000, "goal": "Sales"}
    r = client.post("/api/brands", json=body)
    assert r.status_code == 200, r.text
    assert db.brands.find_one({"_id": r.json()["id"]})["verified"] is False


def test_contract_text_names_no_policy_that_does_not_exist(client, db):
    d = client.get("/api/deals/dl_a_pixelforge?role=creator").json()
    terms = " ".join(d["contract"]["terms"])
    assert "refund policy" not in terms and "until the post is verified or auto-released" in terms


def test_link_in_bio_guest_can_sign_and_pay(client, db):
    r = client.post("/api/public/creator.b/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 2000}).json()
    deal_id = re.search(r"/brand/deals/(dl_\w+)\?as=(br_\w+)", r["track"]).group(1)
    assert client.post(f"/api/deals/{deal_id}/action", json={"role": "creator", "action": "accept"}).status_code == 200
    assert client.post(f"/api/deals/{deal_id}/action", json={"role": "brand", "action": "sign"}).status_code == 200
    paid = client.post(f"/api/deals/{deal_id}/pay").json()
    assert paid["deal"]["stage"] == "escrow_funded"


def test_fictional_seed_data_is_never_high_confidence(client, db):
    for cid in ("cr_a", "cr_b"):
        fair = client.get(f"/api/creators/{cid}/money").json()["fair"]
        assert fair["estimate"]["confidence"] != "high", cid


def test_caption_safety_flags_become_brand_safety_notes(client, db):
    body = {"name": "Caption Creator", "niche": "fitness", "audience_stage": "1k_10k", "income_goal": 10000,
            "languages": ["en"], "city": "Pune", "connected": {"instagram": True},
            "captions": ["This drink will cure your back pain, permanent results", "Morning workout, no excuses"]}
    cid = client.post("/api/creators", json=body).json()["id"]
    assert "health_claims" in db.creators.find_one({"_id": cid})["content_flags"]
    steps = client.get(f"/api/creators/{cid}/money").json()["fair"]["steps"]
    assert any(s["key"] == "safety" and "health claims" in s["reason"].lower() for s in steps)


def _share_nothing(db):
    db.consents.delete_many({})
    db.creators.update_many({}, {"$set": {"consent_defaults": {"stats": False, "demographics": False, "rate_card": False}}})


def test_collective_builder_respects_stats_and_demographics(client, db):
    # Seed defaults: stats shared, demographics not. Exact overlaps need demographics from both creators.
    pack = client.post("/api/listings/lst_senpai_collective/collective", json={}).json()
    assert pack["combined_reach"] is not None
    for m in pack["members"]:
        assert m["reach"] is not None and m["overlap_level"] in ("High", "Low")
        assert m["overlap"] is None, m["name"]
    # Nothing shared: no member numbers and no pack totals a brand could subtract from.
    _share_nothing(db)
    pack = client.post("/api/listings/lst_senpai_collective/collective", json={}).json()
    assert pack["members"]
    for m in pack["members"]:
        assert m["followers"] is None and m["reach"] is None and m["effective_reach"] is None and m["engagement"] is None
        assert m["overlap"] is None and m["audience_stage"]
    for k in ("combined_reach", "raw_reach", "dedup_saved", "avg_engagement", "cost_per_1k"):
        assert pack[k] is None, k
    assert "combined reach" not in pack["summary"]


def test_reach_ratio_reason_needs_the_stats_scope(client, db):
    client.post("/api/creators/cr_a/consents/br_senpai", json={"scopes": {"stats": False, "demographics": False, "rate_card": False}})
    r = client.get("/api/brands/br_senpai/creators/cr_a?listing_id=lst_senpai_hoodie").json()
    assert r["scopes"]["stats"] is False
    assert not any("Reels reach" in x for x in r["fit"]["reasons"])
    rows = matches(db.listings.find_one({"_id": "lst_senpai_hoodie"}), db.brands.find_one({"_id": "br_senpai"}))["items"]
    a = next(x for x in rows if x["id"] == "cr_a")
    assert not any("Reels reach" in x for x in a["reasons"])


def test_public_kit_follows_the_creators_public_switches(client, db):
    client.post("/api/creators/cr_a/kit", json={"stats": False, "demographics": False, "rates": False})
    k = client.get("/api/public/creator.a").json()
    assert k["stats"] is None and k["rates"] is None and k["from_rate"] is None
    text = k["copy"]["headline"] + " " + k["copy"]["bio"]
    assert "the follower count" not in text and "median" not in text
    booked = client.post("/api/public/creator.a/book", json={"brand_name": "Guest Co", "email": "a@b.co", "budget": 9000}).json()
    assert booked["fair"] is None


def test_creator_as_real_views_are_not_labelled_simulated(client, db):
    # The price uses the last six reels, whose views are real; older simulated reels don't count.
    steps = client.get("/api/creators/cr_a/money").json()["fair"]["steps"]
    base = next(s for s in steps if s["key"] == "base")
    assert base["simulated"] is False and base["simulated_fields"] == []
    # The posting pace counts a 4-week window that includes one simulated reel, so it says so.
    assert next(s for s in steps if s["key"] == "consistency")["simulated_fields"] == ["reel dates"]
