"""The behaviours the demo depends on, pinned as tests."""
from app.engines import money_paths, next_step
from app.engines.fair_price import fair_price
from app.engines.opportunities import matched
from app.engines.spam import scan
from app.engines.trust import trust_score
from app.services import creator_ctx as cc


def _c(db, cid):
    return db.creators.find_one({"_id": cid})


def test_creator_a_fair_price_is_reach_based(db):
    a = _c(db, "cr_a")
    senpai = db.brands.find_one({"_id": "br_senpai"})
    thalam = db.brands.find_one({"_id": "br_thalam"})
    fp = fair_price(a, senpai)
    assert fp["range"] == {"low": 17_000, "high": 18_000}
    assert fp["follower_price"] == 7_000
    assert fp["base"] == 15_540  # 129.5K median views x 120 per 1,000
    # Per match, not per creator: a poor-fit brand gets a lower price.
    assert fair_price(a, thalam)["per_reel"] < fp["per_reel"] * 0.8
    # Every adjustment respects its cap.
    for s in fp["steps"]:
        if s.get("cap"):
            assert s["cap"][0] - 1e-9 <= s["pct"] <= s["cap"][1] + 1e-9
    assert fp["model_check"]["agrees_within_pct"] <= 10
    # Steps built on simulated data say so.
    eng = next(s for s in fp["steps"] if s["key"] == "engagement")
    assert eng["simulated"] and "saves" in eng["simulated_fields"]


def test_stages(db):
    assert cc.build(_c(db, "cr_a"))["stage"]["label"] == "Earning, underpriced"
    assert cc.build(_c(db, "cr_b"))["stage"]["label"] == "Starting"
    assert cc.build(_c(db, "cr_n01"))["stage"]["label"] == "Expert, audience later"


def test_creator_a_next_moves(db):
    moves = cc.build(_c(db, "cr_a"))["plan"]["moves"]
    assert [m["kind"] for m in moves] == ["raise_rate", "double_down", "apply_matches"]
    assert "7x your followers" in moves[0]["reason"]
    assert moves[0]["title"] == "Raise your reel rate to ₹17K–18K"
    assert set(moves[1]["why"]["simulated_fields"]) >= {"saves", "format labels"}
    for m in moves:
        assert m["impact"]["low"] <= m["impact"]["high"] and m["impact"]["assumptions"]
        assert m["effort"] in ("S", "M", "L")


def test_creator_b_next_moves(db):
    moves = cc.build(_c(db, "cr_b"))["plan"]["moves"]
    assert {m["kind"] for m in moves} == {"content_gap", "join_collective", "digital"}
    assert any("Tamil quick-breakfast" in m["title"] for m in moves)
    assert any("Thalam Foods" in m["title"] for m in moves)


def test_money_paths(db):
    top_a = {p["type"] for p in cc.build(_c(db, "cr_a"))["paths"][:3]}
    top_b = {p["type"] for p in cc.build(_c(db, "cr_b"))["paths"][:3]}
    assert top_a == {"brand", "affiliate", "collective"}
    assert top_b == {"collective", "digital", "affiliate"}
    # Expertise-first: services before audience.
    assert cc.build(_c(db, "cr_n01"))["paths"][0]["type"] == "services"


def test_a_and_b_get_different_plans(db):
    a, b = cc.build(_c(db, "cr_a")), cc.build(_c(db, "cr_b"))
    assert not {m["title"] for m in a["plan"]["moves"]} & {m["title"] for m in b["plan"]["moves"]}
    assert [p["title"] for p in a["paths"][:3]] != [p["title"] for p in b["paths"][:3]]
    ids_a = {o["id"] for o in matched(_c(db, "cr_a"))["items"][:5]}
    ids_b = {o["id"] for o in matched(_c(db, "cr_b"))["items"][:5]}
    assert not ids_a & ids_b


def test_durable_income(db):
    d = cc.build(_c(db, "cr_a"))["durable"]
    assert d["score"] < 40 and "97%" in d["warning"]
    assert d["next_stream"]["type"] in ("collective", "affiliate")
    assert cc.build(_c(db, "cr_b"))["durable"]["state"] == "no_income"


def test_trust_catches_engineered_profiles(db):
    for c in db.creators.find({}):
        t = trust_score(c)
        if c.get("seed_low_trust"):
            assert t["score"] < 50, c["_id"]
        else:
            assert t["score"] >= 60, (c["_id"], t)


def test_low_offer_alert(db):
    alerts = cc.pipeline(_c(db, "cr_a"))["alerts"]
    low = next(a for a in alerts if a["kind"] == "low_offer")
    assert "58% below" in low["text"]
    assert any(a["kind"] == "invoice_late" for a in alerts)


def test_learning_loop(db):
    a = _c(db, "cr_a")
    plan = cc.build(a)["plan"]
    next_step.record_outcome(a, plan["moves"][0]["id"], "worked", 17_000, None)
    a = _c(db, "cr_a")
    assert a["current_rate"] == 17_000
    week2 = next_step.next_week(a, cc.build(a, with_plan=False))
    assert week2["week"] == 2
    assert "lock_rate" in [m["kind"] for m in week2["moves"]]
    assert any("worked" in ch for ch in week2["changes"])


def test_spam_and_duplicates_hidden(db):
    flagged = {k for k, v in scan().items() if v["flagged"]}
    assert flagged == {"lst_spam_fee", "lst_dup_hoodie", "lst_spam_followers"}
    ids = {o["id"] for o in matched(_c(db, "cr_a"))["items"]}
    assert not ids & flagged


def test_money_goal_summary(db):
    b = _c(db, "cr_b")
    paths = cc.build(b)["paths"]
    g = money_paths.goal_summary(b, paths)
    assert g["goal"] == 10_000 and g["top3"]["low"] < g["top3"]["high"]
