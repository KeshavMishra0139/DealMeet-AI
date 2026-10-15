"""The AI market review: bounded, grounded in the facts, and the formula's price when AI is off."""
from dataclasses import replace
from threading import enumerate as threads

import pytest
from test_ai_fallback import fake_ai  # noqa: F401  (fixture)
from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)
from test_youtube_profile import _new_creator

from app.ai import llm, price_review
from app.ai.price_review import PriceReview
from app.engines import fair_price as fp_mod


@pytest.fixture()
def ai_on(fake_ai, monkeypatch):
    settings = llm.get_settings()
    monkeypatch.setattr(price_review, "get_settings", lambda: settings)
    price_review.get_db().ai_cache.delete_many({})
    return fake_ai


def _review(pct=20, niche="comedy", language="hi", reasons=None):
    return PriceReview(adjust_pct=pct, niche=niche, language=language, confidence="medium",
                       reasons=reasons or ["Family sitcom clips holding 50000 median views are easy for brands to place."])


def test_without_ai_the_formula_price_stands(client, youtube, db):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    fair = a.get(f"/api/creators/{cid}/fair-price").json()
    assert fair["ai_review"] == {"status": "off"} and all(s["key"] != "ai" for s in fair["steps"])
    assert a.post(f"/api/creators/{cid}/price-review").status_code == 503


def test_a_creators_review_is_stored_applied_everywhere_and_goes_stale(client, youtube, db, ai_on):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    before = a.get(f"/api/creators/{cid}/fair-price").json()
    for t in threads():  # the background review started by linking or the home page
        if t.name.startswith("price-review-"):
            t.join(10)
    db.creators.update_one({"_id": cid}, {"$unset": {"ai_price": "", "ai_price_attempt": ""}})
    ai_on["output"] = _review(pct=-10, niche="food", reasons=["Recipe videos with steady views; 4 long videos is a thin record."])
    out = a.post(f"/api/creators/{cid}/price-review").json()
    assert out["status"] == "applied" and out["adjust_pct"] == -10
    fair = a.get(f"/api/creators/{cid}/fair-price").json()
    step = next(s for s in fair["steps"] if s["key"] == "ai")
    assert step["pct"] == -0.1 and step["label"] == "AI market review"
    assert fair["per_reel"] < before["per_reel"] or before["per_reel"] == fp_mod.PRODUCTION_FLOOR
    assert fair["model_check"]["predicted"] == before["model_check"]["predicted"]  # the cross-check stays on the formula
    # The same review reaches the brand side's price for this creator.
    c = db.creators.find_one({"_id": cid})
    assert any(s["key"] == "ai" for s in fp_mod.fair_price(c, None, with_model=False)["steps"])
    # New numbers (another niche): the stored review no longer applies until it's redone.
    db.creators.update_one({"_id": cid}, {"$set": {"niche": "comedy"}})
    c = db.creators.find_one({"_id": cid})
    assert price_review.current(c) is None and price_review.status(c) == "pending"


def test_background_review_runs_once_per_numbers(client, youtube, db, ai_on):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    for t in threads():
        if t.name.startswith("price-review-"):
            t.join(10)
    ai_on["output"] = _review(niche="food", reasons=["Steady recipe videos."])
    db.creators.update_one({"_id": cid}, {"$unset": {"ai_price": "", "ai_price_attempt": ""}})
    n = ai_on["n"]
    a.get(f"/api/creators/{cid}/home")
    for t in threads():
        if t.name.startswith("price-review-"):
            t.join(10)
    assert price_review.current(db.creators.find_one({"_id": cid}))
    a.get(f"/api/creators/{cid}/home")
    assert ai_on["n"] == n + 1  # reviewed once; the next load reuses it


def test_language_from_titles_without_ai():
    assert price_review.detect_language(["10 நிமிடத்தில் ரவா உப்புமா", "Easy dosa", "சாம்பார் ரெசிபி", "Breakfast"]) == "ta"
    assert price_review.detect_language(["SIP vs FD, simple samjho", "Tax kaise bachaye yaar"]) == "hinglish"
    assert price_review.detect_language([]) is None
