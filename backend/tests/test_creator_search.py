"""Brand creator search: MongoDB queries for text, niche, follower band and reach, within
what each creator lets the brand see."""
from app.services import consent as cs
from app.services import reach
from app.services.creator_search import PAGE_SIZE

URL = "/api/brands/br_senpai/creators"


def _names(r) -> list[str]:
    return [x["name"] for x in r.json()["results"]]


def test_search_needs_the_brand_that_owns_the_console(client, login, db):
    assert client.get(URL).status_code == 401
    assert login("br_thalam").get(URL).status_code == 403
    assert login("cr_a").get(URL).status_code == 403


def test_text_is_a_case_insensitive_partial_match_and_regex_safe(login, db):
    b = login("br_senpai")
    r = b.get(URL, params={"q": "creAtor a"})
    assert r.status_code == 200 and "Creator A" in _names(r)
    by_niche_label = b.get(URL, params={"q": "anime"}).json()
    assert by_niche_label["total"] > 0 and all("Anime" in x["niche_label"] or x["name"] == "Creator A" for x in by_niche_label["results"])
    assert b.get(URL, params={"q": ".*(["}).json()["total"] == 0  # a literal string, not a pattern


def test_niche_followers_and_reach_filters_are_exact_and_ranged(login, db):
    b = login("br_senpai")
    food = b.get(URL, params={"niche": "food", "sort": "name"}).json()
    assert food["total"] == db.creators.count_documents({"niche": "food", "discoverable": {"$ne": False}})
    assert all(x["niche_label"] == "Food and cooking" or x["niche_label"].startswith("Food") for x in food["results"])
    band = b.get(URL, params={"followers": "1k_10k"}).json()
    assert band["total"] > 0 and all(1_000 <= x["followers"] <= 9_999 for x in band["results"])
    hits = b.get(URL, params={"reach": "10k_50k"}).json()
    assert hits["total"] > 0 and all(10_000 <= x["reach_views"] <= 49_999 for x in hits["results"])
    ranked = [x["reach_views"] for x in hits["results"]]
    assert ranked == sorted(ranked, reverse=True)  # highest reach first
    for bad in ({"niche": "astrology"}, {"followers": "huge"}, {"reach": "1m"}, {"sort": "random"}):
        assert b.get(URL, params=bad).status_code == 422


def test_stats_stay_private_and_the_reach_filter_never_reveals_them(login, db):
    b = login("br_senpai")
    target = db.creators.find_one({"niche": "food", "reach_views": {"$gte": 10_000, "$lte": 49_999}})
    db.creators.update_one({"_id": target["_id"]}, {"$set": {"consent_defaults.stats": False}})
    db.consents.delete_many({"creator_id": target["_id"], "lister_id": "br_senpai"})
    everyone = b.get(URL, params={"q": target["name"]}).json()["results"]
    card = next(x for x in everyone if x["id"] == target["_id"])
    assert card["shares_stats"] is False and card["followers"] is None and card["reach_views"] is None
    assert card["audience_stage"]  # the follower band is public
    in_range = b.get(URL, params={"reach": "10k_50k"}).json()
    assert target["_id"] not in {x["id"] for x in in_range["results"]} and in_range["hidden_by_reach"] >= 1
    # The same count whatever the hidden creator's real reach: no way to narrow it down.
    other = b.get(URL, params={"reach": "100k_plus"}).json()
    assert other["hidden_by_reach"] == in_range["hidden_by_reach"]
    # Sorted by reach, they come after everyone who shares it, wherever their reach is.
    first = b.get(URL, params={"niche": "food"}).json()
    ranked = [x for page in range(1, first["pages"] + 1) for x in b.get(URL, params={"niche": "food", "page": page}).json()["results"]]
    flags = [x["shares_stats"] for x in ranked]
    assert flags == sorted(flags, reverse=True) and ranked[-1]["id"] == target["_id"]
    # A per-brand grant with stats makes them visible to that brand.
    cs.grant(target["_id"], "br_senpai", {"stats": True})
    assert target["_id"] in {x["id"] for x in b.get(URL, params={"reach": "10k_50k"}).json()["results"]}


def test_hidden_and_revoked_creators_never_appear(login, db):
    b = login("br_senpai")
    a, other = db.creators.find_one({"_id": "cr_a"}), db.creators.find_one({"niche": "food"})
    db.creators.update_one({"_id": other["_id"]}, {"$set": {"discoverable": False}})
    cs.revoke("cr_a", "br_senpai")
    ids = {x["id"] for x in b.get(URL, params={"sort": "name", "page": 1}).json()["results"]}
    ids |= {x["id"] for x in b.get(URL, params={"sort": "name", "page": 2}).json()["results"]}
    ids |= {x["id"] for x in b.get(URL, params={"sort": "name", "page": 3}).json()["results"]}
    assert "cr_a" not in ids and other["_id"] not in ids
    assert a["name"] not in _names(b.get(URL, params={"q": a["name"]}))
    assert "cr_a" in {x["id"] for x in login("br_thalam").get("/api/brands/br_thalam/creators", params={"q": "Creator A"}).json()["results"]}


def test_pages_cover_every_match_once_in_both_orders(login, db):
    b = login("br_senpai")
    for sort in ("reach", "name"):
        first = b.get(URL, params={"sort": sort}).json()
        seen = []
        for page in range(1, first["pages"] + 1):
            seen += [x["id"] for x in b.get(URL, params={"sort": sort, "page": page}).json()["results"]]
        assert len(seen) == len(set(seen)) == first["total"]
        assert len(b.get(URL, params={"sort": sort}).json()["results"]) == min(PAGE_SIZE, first["total"])


def test_sample_profiles_are_marked(login, db):
    r = login("br_senpai").get(URL, params={"q": "Creator B"}).json()["results"][0]
    assert r["sample"] is True and r["followers_source"] == "synthetic"


def test_stored_reach_follows_the_creator_data(login, db):
    # Seeding fills it; it's the median of the last six reels, never the follower guess.
    for c in db.creators.find({}, {"reels": 1, "manual": 1, "provenance": 1, "provenance_default": 1, "insights_source": 1, "reach_views": 1}):
        assert c["reach_views"] == reach.measured(c)["reach_views"]
    me = login("new_creator")
    cid = me.post("/api/creators", json={"name": "Asha", "niche": "food", "audience_stage": "1k_10k", "income_goal": 5000, "languages": ["hi"], "city": "Pune"}).json()["id"]
    assert db.creators.find_one({"_id": cid})["reach_views"] is None  # no reels, nothing typed: no reach
    assert me.post(f"/api/creators/{cid}/manual-metrics", json={"platform": "instagram", "followers": 4200, "avg_views": 3100}).status_code == 200
    doc = db.creators.find_one({"_id": cid})
    assert doc["reach_views"] == 3100 and doc["reach_source"] == "manual"
