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
