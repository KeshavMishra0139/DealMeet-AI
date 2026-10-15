"""Public search: creators found by their own words, brands by what they make and who they
hire, and visitors asked to sign in for more."""
from app.services import directory as dr
from app.services import public_search as ps


def _creators(client, **params):
    r = client.get("/api/directory/creators", params=params)
    assert r.status_code == 200, r.text
    return r.json()


def test_creators_are_found_by_their_tags_niche_city_and_language(client):
    d = _creators(client, q="tamil breakfast")
    assert d["items"][0]["handle"] == "creator.b"
    assert d["items"][0]["matched"] == ["Tamil home cooking", "Quick breakfast"]  # says why it matched
    assert d["niche_hint"] == {"id": "food", "label": "Food and cooking"}
    assert all(i["niche"]["id"] == "food" for i in _creators(client, q="dosa")["items"])  # content words find the niche
    assert {"Madurai"} == {i["city"] for i in _creators(client, q="madurai")["items"]}
    assert _creators(client, q="@creator.b")["items"][0]["handle"] == "creator.b"
    assert _creators(client, q="zzzz")["total"] == 0


def test_only_public_pages_and_nothing_private(client, db):
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"public_page": False}})
    assert _creators(client, q="@creator.b")["total"] == 0
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"public_page": None, "discoverable": False}})
    assert _creators(client, q="@creator.b")["total"] == 0
    # The anonymised reference profile never appears.
    assert "creator.a" not in {i["handle"] for i in _creators(client, q="anime")["items"]}
    card = _creators(client, q="gaming")["items"][0]
    assert set(card) == {"handle", "name", "avatar_hue", "niche", "languages", "city", "tags", "followers_band", "matched", "page"}
    assert card["page"] == f"/c/{card['handle']}"


def test_every_niche_is_listed_busiest_first(client):
    niches = _creators(client)["niches"]
    assert len(niches) == len(ps.NICHES) and niches[0]["id"] == "food"
    assert [n["count"] for n in niches] == sorted((n["count"] for n in niches), reverse=True)
    assert all(i["niche"]["id"] == "gaming" for i in _creators(client, niche="gaming")["items"])
    assert client.get("/api/directory/creators", params={"niche": "nope"}).status_code == 422


def test_visitors_see_a_few_and_members_see_more(client, login):
    visitor = _creators(client, niche="food")
    assert len(visitor["items"]) == ps.VISITOR_LIMIT and visitor["locked"] and visitor["total"] > ps.VISITOR_LIMIT
    member = login("br_senpai").get("/api/directory/creators", params={"niche": "food"}).json()
    assert len(member["items"]) > ps.VISITOR_LIMIT and not member["locked"]


def test_brands_are_found_by_the_creators_they_hire(client, login):
    d = client.get("/api/directory/brands", params={"q": "dosa"}).json()
    assert d["items"] and all("Works with food and cooking creators" in b["matched"] for b in d["items"])
    assert d["niche_hint"]["id"] == "food"
    # Visitors get the first few, members every page.
    visitor = client.get("/api/directory/brands", params={"page": 2}).json()
    assert visitor["page"] == 1 and len(visitor["items"]) == dr.VISITOR_LIMIT and visitor["locked"]
    member = login("cr_b").get("/api/directory/brands").json()
    assert len(member["items"]) > dr.VISITOR_LIMIT and not member["locked"]
