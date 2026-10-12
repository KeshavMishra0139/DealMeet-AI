"""A linked YouTube channel's numbers drive the creator's screens, and every week has 3 moves."""
import uuid

from conftest import Actor
from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)

from app.engines import metrics, next_step
from app.engines.fair_price import fair_price
from app.services import auth as au
from app.services import youtube_public as yt
from app.services.views import source_of

ONBOARDING = {
    "name": "Ravi",
    "platforms": ["youtube"],
    "formats": ["long", "shorts"],
    "income_goal": 10000,
    "income_types": ["brand"],
    "languages": ["hi"],
    "city": "Mumbai",
    "sample_insights": False,
}


def _new_creator(client, db, niche="fitness", stage="under_1k", channel=None, **extra) -> tuple[Actor, str]:
    """A real (non-demo) creator account through onboarding, optionally signed in with YouTube."""
    user = au.new_user("creator", "Ravi", email=f"ravi-{uuid.uuid4().hex[:8]}@example.test")
    if channel:
        db.users.update_one({"_id": user["_id"]}, {"$set": {"youtube_channel_id": channel}})  # what /api/auth/youtube records
    actor = Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))
    r = actor.post("/api/creators", json={**ONBOARDING, "niche": niche, "audience_stage": stage, **extra})
    assert r.status_code == 200, r.text
    return actor, r.json()["id"]


def test_linking_puts_the_channel_numbers_on_the_profile_and_unlinking_puts_them_back(login, youtube, db):
    before = db.creators.find_one({"_id": "cr_b"})
    a = login("cr_b")
    assert a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"}).status_code == 200
    c = db.creators.find_one({"_id": "cr_b"})
    assert c["followers"] == 21_300 and source_of(c, "followers") == "youtube_api"
    assert len(c["reels"]) == 10 and all(r["source"] == "youtube_api" and r["saves"] is None and r["shares"] is None for r in c["reels"])
    assert {r["format"] for r in c["reels"]} == {"shorts", "long"} and source_of(c, "reels.0.views") == "youtube_api"
    assert c["insights_connected"]["youtube"] is True
    assert c["reference_note"] == f"{yt.LIVE_NOTE} {yt.NOTE_SAMPLE_REST}"  # a seeded demo profile
    # What brands and the creator see is built from the videos.
    home = a.get("/api/creators/cr_b/home").json()
    assert home["context"]["followers"] == 21_300 and home["context"]["recent_provenance"]["views"] == "real"
    assert home["context"]["median_views"] == metrics.median_views(c)
    assert "pre_youtube" not in a.get("/api/creators/cr_b").json()
    # Linking again refreshes the numbers without losing what was there before.
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    assert db.creators.find_one({"_id": "cr_b"})["pre_youtube"]["followers"] == before["followers"]
    # Unlinking puts the profile back as it was.
    a.delete("/api/creators/cr_b/youtube/link")
    after = db.creators.find_one({"_id": "cr_b"})
    for k in ("followers", "reels", "provenance", "insights_source", "reference_note"):
        assert after.get(k) == before.get(k), k
    assert after["insights_connected"].get("youtube") is False and "pre_youtube" not in after


def test_youtube_sign_up_gets_live_numbers_and_three_moves_from_them(client, youtube, db):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    c = db.creators.find_one({"_id": cid})
    assert c["followers"] == 21_300 and len(c["reels"]) == 10 and c["insights_source"] == "youtube_api"
    assert c["reference_note"] == f"{yt.LIVE_NOTE} {yt.NOTE_SAMPLE_AUDIENCE}"
    moves = a.get(f"/api/creators/{cid}/home").json()["plan"]["moves"]
    assert len(moves) == 3 and "growth" in {m["category"] for m in moves}
    # YouTube reports no saves: no move claims any.
    assert not any("save" in (m["title"] + m["reason"]).lower() for m in moves)
    assert all(m["title"] and m["reason"] and m["hi"]["title"] for m in moves)
    report = a.get(f"/api/creators/{cid}/weekly-report").json()
    assert report["reach"] is not None and report["reach"]["source"] == "youtube_api"


def test_hidden_subscribers_keep_the_typed_follower_count_and_its_label(client, youtube, db):
    youtube.hidden = True
    _, cid = _new_creator(client, db, channel=CHANNEL, followers=850)
    c = db.creators.find_one({"_id": cid})
    assert c["followers"] == 850 and source_of(c, "followers") == "manual"
    assert len(c["reels"]) == 10 and source_of(c, "reels.0.views") == "youtube_api"


def test_engines_treat_unreported_saves_as_unknown_not_zero(client, youtube, db):
    _, cid = _new_creator(client, db, channel=CHANNEL)
    c = db.creators.find_one({"_id": cid})
    assert not metrics.ss_known(c) and all(t["save_rate"] is None for t in metrics.by_topic(c))
    fp = fair_price(c, None, with_model=False)
    step = next(s for s in fp["steps"] if s["key"] == "engagement")
    assert step["pct"] == 0 and "YouTube doesn't report saves or shares" in step["reason"]


def test_a_week_without_enough_moves_is_filled_to_three(client, db, monkeypatch):
    monkeypatch.delenv("YOUTUBE_API_KEY", raising=False)
    from app import config

    config.get_settings.cache_clear()
    a, cid = _new_creator(client, db, niche="travel", stage="zero")  # no channel, no views, few listings
    moves = a.get(f"/api/creators/{cid}/home").json()["plan"]["moves"]
    assert len(moves) == 3
    kinds = {m["kind"] for m in moves}
    assert "real_numbers" in kinds  # asks for real views before giving growth advice
    assert next(m for m in moves if m["kind"] == "real_numbers")["title"] == "Add your average views"  # no YouTube key here


def test_a_short_plan_saved_earlier_is_rebuilt_until_someone_acts_on_it(client, db):
    a, cid = _new_creator(client, db, niche="travel", stage="zero")
    a.get(f"/api/creators/{cid}/home")  # saves week 1
    plan = db.plans.find_one({"creator_id": cid})
    db.plans.update_one({"_id": plan["_id"]}, {"$set": {"moves": plan["moves"][:1]}})
    assert len(a.get(f"/api/creators/{cid}/home").json()["plan"]["moves"]) == 3
    # Once a move is acted on, the week stays as it is.
    plan = db.plans.find_one({"creator_id": cid})
    moves = plan["moves"][:1]
    moves[0]["status"] = "done"
    db.plans.update_one({"_id": plan["_id"]}, {"$set": {"moves": moves}})
    assert len(a.get(f"/api/creators/{cid}/home").json()["plan"]["moves"]) == 1


def test_first_link_rebuilds_an_untouched_plan_from_the_channel(login, youtube, db):
    a = login("cr_b")
    a.get("/api/creators/cr_b/home")  # week 1 from the sample numbers
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    plan = db.plans.find_one({"creator_id": "cr_b"}, sort=[("week", -1)])
    assert plan["changes"] == ["New moves from your YouTube channel's numbers."]


def test_channels_linked_before_this_update_get_their_numbers_at_start(login, youtube, db):
    a = login("cr_b")
    before = db.creators.find_one({"_id": "cr_b"})
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    # As stored by the old code: the channel and its videos, the profile untouched.
    db.creators.update_one({"_id": "cr_b"}, {"$set": {k: before.get(k) for k in yt.PROFILE_KEYS if before.get(k) is not None}, "$unset": {"pre_youtube": ""}})
    assert yt.backfill_profiles(db) == 1
    c = db.creators.find_one({"_id": "cr_b"})
    assert c["followers"] == 21_300 and c["pre_youtube"]["followers"] == before["followers"]
    assert yt.backfill_profiles(db) == 0  # safe to repeat


def test_switching_channel_drops_the_old_channels_videos(login, youtube, db):
    a = login("cr_b")
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    other = yt.channel_report("@testkitchen")
    other["channel"]["id"] = "UC" + "b" * 22
    other["videos"] = [{**v, "post_id": "new_" + v["post_id"]} for v in other["videos"][:4]]
    yt.save_for_creator("cr_b", other)
    assert db.posts.count_documents({"creator_id": "cr_b", "platform": "youtube"}) == 4
    assert len(db.creators.find_one({"_id": "cr_b"})["reels"]) == 4


def test_instagram_keeps_priority_and_unlinking_youtube_fixes_what_instagram_restores(login, youtube, db):
    a = login("cr_b")
    original = db.creators.find_one({"_id": "cr_b"})
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    # Instagram connected afterwards (as instagram._apply_to_profile stores it).
    yt_state = db.creators.find_one({"_id": "cr_b"})
    pre_ig = {k: yt_state.get(k) for k in ("reels", "followers", "provenance", "insights_source", "insights_connected")}
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"channels.instagram": {"followers": 999}, "followers": 999, "pre_instagram": pre_ig}})
    # A YouTube refresh doesn't overwrite Instagram's numbers.
    a.post("/api/creators/cr_b/youtube/link", json={"handle": "@testkitchen"})
    assert db.creators.find_one({"_id": "cr_b"})["followers"] == 999
    # Unlinking YouTube keeps Instagram's numbers; disconnecting Instagram later restores the profile from before YouTube.
    a.delete("/api/creators/cr_b/youtube/link")
    c = db.creators.find_one({"_id": "cr_b"})
    assert c["followers"] == 999 and c["pre_instagram"]["followers"] == original["followers"]
    assert c["reference_note"] == original.get("reference_note")


def test_fallback_moves_have_hindi_copy_and_no_promises(client, db):
    import json
    import re
    from pathlib import Path

    rules = [re.compile(r["pattern"], re.I) for r in json.loads((Path(__file__).resolve().parents[2] / "shared" / "copy-rules.json").read_text())["banned"]]
    _, cid = _new_creator(client, db, niche="comedy", stage="zero")
    from app.services import creator_ctx as cc

    c = cc.load_creator(cid)
    ctx = cc.build(c, with_plan=False)
    for f in next_step.FALLBACKS:
        m = f(c, ctx)
        if m:
            text = " ".join([m["title"], m["reason"], m["hi"]["title"], m["hi"]["reason"], *m["impact"]["assumptions"]])
            assert m["hi"]["title"] and not any(rx.search(text) for rx in rules), m["kind"]
