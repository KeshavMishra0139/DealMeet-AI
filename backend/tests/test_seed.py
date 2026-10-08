"""Creator A must use exactly the real interview data, with provenance on every field."""
from statistics import median

from app.seed.creator_a import REFERENCE_NOTE
from app.services.views import provenance_of


def test_creator_a_real_values(db):
    a = db.creators.find_one({"_id": "cr_a"})
    assert a["followers"] == 21_300
    assert a["following"] == 39
    assert a["posts"] == 106
    assert a["avg_likes"] == 7_900 and a["avg_comments"] == 81
    assert a["best_deal"] == 20_000
    assert a["languages"] == ["hi", "en"]
    recent = sorted(a["reels"], key=lambda r: r["date"], reverse=True)[:6]
    assert sorted(r["views"] for r in recent) == [33_200, 88_900, 117_000, 142_000, 210_000, 359_000]
    assert {r["date"] for r in recent} == {
        "2026-09-20", "2026-09-22", "2026-09-27", "2026-09-28", "2026-09-29", "2026-10-01",
    }
    assert median(r["views"] for r in recent) == 129_500
    # Simulated per-reel likes and comments stay consistent with the public averages.
    assert round(sum(r["likes"] for r in recent) / 6, -2) == 7_900
    assert round(sum(r["comments"] for r in recent) / 6) == 81
    # Earlier (simulated) reels stay inside the real 50K-150K range.
    for r in a["reels"]:
        if not r["is_recent"]:
            assert 50_000 <= r["views"] <= 150_000


def test_creator_a_provenance_and_identity(db):
    a = db.creators.find_one({"_id": "cr_a"})
    assert a["reference_note"] == REFERENCE_NOTE
    assert a["handle"] == "creator.a" and a["name"] == "Creator A"
    assert a["city"] is None
    assert provenance_of(a, "followers") == "real"
    assert provenance_of(a, "reels.0.views") == "real"
    assert provenance_of(a, "reels.0.saves") == "simulated"
    assert provenance_of(a, "audience.age") == "simulated"
    assert provenance_of(a, "income_history") == "simulated"
    # Nothing is attributed to the creator as a statement.
    assert all(r["caption"] is None for r in a["reels"])


def test_seed_shape(db):
    assert db.creators.count_documents({}) == 60
    assert db.listings.count_documents({"type": "brand_campaign", "owner_id": {"$regex": "^br_"}}) == 13
    assert db.listings.count_documents({"type": "collective"}) == 2
    assert db.listings.count_documents({"type": "pr_service"}) == 6
    assert db.listings.count_documents({"type": "page", "owner_id": {"$regex": "^pg_"}}) == 5
    assert db.listings.count_documents({"type": "creator_collab"}) == 8
    low = db.creators.count_documents({"seed_low_trust": {"$ne": None}})
    assert low == 5
    b = db.creators.find_one({"_id": "cr_b"})
    assert b["followers"] == 2_000 and b["languages"] == ["ta"] and b["income_goal"]["monthly"] == 10_000
