"""Demo screens: Creator A vs B, Hindi copy and silent brand-safety notes."""


def test_compare_shows_both_creators_and_a_guided_script(client, db):
    d = client.get("/api/demo/compare").json()
    assert d["a"]["stage"]["id"] == "underpriced" and d["b"]["stage"]["id"] == "starting"
    assert d["a"]["rate_gap"]["fair"]["low"] >= 17_000
    assert [m["kind"] for m in d["a"]["moves"]] == ["raise_rate", "double_down", "apply_matches"]
    assert {p["type"] for p in d["b"]["paths"]} == {"collective", "digital", "affiliate"}
    assert any(o["type"] == "collective" for o in d["b"]["opportunities"])
    steps = {g["id"]: g for g in d["guide"]}
    assert list(steps) == ["who", "stage", "price", "roadmap", "money", "opportunities", "moves"]
    assert "₹17K–18K" in steps["price"]["caption"] and "voiceover" in steps["roadmap"]["caption"]
    assert "basic editing" in steps["roadmap"]["caption"] and "Thalam Foods" in steps["opportunities"]["caption"]


def test_hindi_copy_travels_with_the_english(client, db):
    home = client.get("/api/creators/cr_a/home").json()
    assert home["stage"]["hi"]["label"] == "कमा रहे हैं, पर कम रेट पर"
    assert all(m["hi"]["title"] and m["hi"]["reason"] for m in home["plan"]["moves"])
    assert "₹17K–18K" in home["plan"]["moves"][0]["hi"]["title"]
    assert home["rate_gap"]["line_hi"].startswith("हर ब्रैंड रील पर")
    assert home["durable"]["warning_hi"] and all(a["hi"]["text"] for a in home["pipeline"]["alerts"])
    b = client.get("/api/creators/cr_b/home").json()
    assert b["plan"]["moves"][0]["hi"]["reason"].endswith("क्रिएटर ही इन्हें पोस्ट करते हैं।")


def test_brand_safety_notes_are_shown_to_brands_without_the_maths(client, db):
    rows = client.get("/api/listings/lst_senpai_hoodie/matches").json()["items"]
    a = next(r for r in rows if r["id"] == "cr_a")
    assert [f["id"] for f in a["safety"]["flags"]] == ["copyrighted_clips"]
    assert "penalty" not in a["safety"]["flags"][0]
    profile = client.get("/api/brands/br_thalam/creators/cr_b").json()
    assert profile["safety"]["flags"] == []
