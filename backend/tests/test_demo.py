"""Demo profiles: Hindi copy, silent brand-safety notes and the reach chart."""


def test_hindi_copy_travels_with_the_english(login, db):
    home = login("cr_a").get("/api/creators/cr_a/home").json()
    assert home["stage"]["hi"]["label"] == "कमा रहे हैं, पर कम रेट पर"
    assert all(m["hi"]["title"] and m["hi"]["reason"] for m in home["plan"]["moves"])
    assert "₹17K–18K" in home["plan"]["moves"][0]["hi"]["title"]
    assert home["rate_gap"]["line_hi"].startswith("हर ब्रैंड रील पर")
    assert home["durable"]["warning_hi"] and all(a["hi"]["text"] for a in home["pipeline"]["alerts"])
    b = login("cr_b").get("/api/creators/cr_b/home").json()
    assert b["plan"]["moves"][0]["hi"]["reason"].endswith("क्रिएटर ही इन्हें पोस्ट करते हैं।")


def test_brand_safety_notes_are_shown_to_brands_without_the_maths(login, db):
    rows = login("br_senpai").get("/api/listings/lst_senpai_hoodie/matches").json()["items"]
    a = next(r for r in rows if r["id"] == "cr_a")
    assert [f["id"] for f in a["safety"]["flags"]] == ["copyrighted_clips"]
    assert "penalty" not in a["safety"]["flags"][0]
    profile = login("br_thalam").get("/api/brands/br_thalam/creators/cr_b").json()
    assert profile["safety"]["flags"] == []


def test_home_sends_the_last_six_reels_for_the_reach_chart(login, db):
    ctx = login("cr_a").get("/api/creators/cr_a/home").json()["context"]
    assert [r["views"] for r in ctx["recent"]] == [359_000, 142_000, 88_900, 33_200, 210_000, 117_000]
    assert ctx["recent"][0]["date"] == "2026-09-20" and ctx["recent_provenance"] == {"views": "real", "followers": "real"}
