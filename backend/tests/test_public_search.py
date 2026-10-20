"""Public search: creators found by their own words, brands by what they make and who they
hire, and visitors asked to sign in for more."""
import pytest

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
    assert _creators(client, q="madurai", web="false")["items"][0]["city"] == "Madurai"
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
    visitor = client.get("/api/directory/brands", params={"open": "true", "page": 2}).json()
    assert visitor["page"] == 1 and len(visitor["items"]) == dr.VISITOR_LIMIT and visitor["locked"]
    member = login("cr_b").get("/api/directory/brands", params={"open": "true"}).json()
    assert len(member["items"]) > dr.VISITOR_LIMIT and not member["locked"]


# ------------------------------------------------------------------ like a search engine
def test_several_niches_list_their_top_creators_first(client):
    d = _creators(client, niche="gaming,fitness", web="false")
    assert {i["niche"]["id"] for i in d["items"]} == {"gaming", "fitness"} and d["total"] == 8
    assert client.get("/api/directory/creators", params={"niche": "gaming,nope"}).status_code == 422


def test_ties_go_to_the_bigger_creator_and_small_typos_still_match(client, db):
    names = [i["handle"] for i in _creators(client, q="madurai", web="false")["items"] if i["city"] == "Madurai"]
    assert len(names) == 3
    followers = {c["handle"]: c["followers"] for c in db.creators.find({"handle": {"$in": names}})}
    assert names == sorted(names, key=lambda h: -followers[h])
    assert _creators(client, q="Anitah", web="false")["items"][0]["handle"] == "anitha.chettinad"


def test_a_linked_channel_name_finds_the_creator(client, db):
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"channels.youtube": {"title": "Vivek Cooks", "handle": "@vivekcooks", "channel_id": "UCvivek"}}})
    assert _creators(client, q="vivek", web="false")["items"][0]["handle"] == "creator.b"


class FakeSearch:
    """YouTube's search.list and channels.list, counting the calls that cost quota."""

    def __init__(self):
        self.searches = 0

    def __call__(self, endpoint, params):
        if endpoint == "search":
            self.searches += 1
            return {"items": [{"id": {"channelId": "UCvivek"}}, {"id": {"channelId": "UCother"}}]}, 0
        assert endpoint == "channels"
        if "forHandle" in params:
            return {"items": [{"id": "UCvivek"}]}, 0
        chans = {
            "UCvivek": {"snippet": {"title": "Vivek Cooks", "customUrl": "@vivekcooks", "description": "Home recipes\nmore"}, "statistics": {"subscriberCount": "120000", "videoCount": "300"}},
            "UCother": {"snippet": {"title": "Other", "customUrl": "@other"}, "statistics": {"hiddenSubscriberCount": True, "videoCount": "5"}},
        }
        return {"items": [{"id": i, **chans[i]} for i in params["id"].split(",") if i in chans]}, 0


@pytest.fixture()
def yt_search(monkeypatch, db):
    from app.services import youtube_public as ytp
    from app.services import youtube_search as yts

    fake = FakeSearch()
    monkeypatch.setattr(ytp, "configured", lambda: True)
    monkeypatch.setattr(ytp, "is_cached", lambda e, p: False)
    monkeypatch.setattr(ytp, "_call", fake)
    db.rate_limits.delete_many({})
    return fake, yts


def test_public_youtube_channels_come_after_dealmeet_creators_without_a_price(client, yt_search):
    d = _creators(client, q="@vivekcooks")
    yt = d["youtube"]["items"]
    assert [c["channel_id"] for c in yt] == ["UCvivek", "UCother"]  # the exact handle first
    assert yt[0]["subscribers"] == 120_000 and yt[0]["url"] == "https://www.youtube.com/@vivekcooks" and yt[0]["description"] == "Home recipes"
    assert yt[1]["subscribers"] is None  # hidden stays hidden
    assert not any(k in yt[0] for k in ("price", "estimate", "prices", "per_video"))
    assert len(yt) <= 4  # visitors see a few


def test_a_channel_on_dealmeet_points_to_its_public_page(client, db, yt_search):
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"channels.youtube": {"title": "Vivek Cooks", "channel_id": "UCvivek"}}})
    yt = _creators(client, q="vivek cooks")["youtube"]["items"]
    assert yt[0]["on_dealmeet"] == "/c/creator.b"


def test_youtube_searches_are_capped_and_never_break_the_search(client, yt_search, monkeypatch):
    fake, yts = yt_search
    monkeypatch.setattr(yts, "SEARCHES_PER_DAY", 2)
    for q in ("cooking one", "cooking two"):
        assert _creators(client, q=q)["youtube"]["items"]
    d = _creators(client, q="cooking three")
    assert fake.searches == 2 and "paused for today" in d["youtube"]["note"] and d["items"]  # DealMeet results still come


def test_without_a_key_youtube_says_so(client, monkeypatch):
    from app.services import youtube_public as ytp

    monkeypatch.setattr(ytp, "configured", lambda: False)
    d = _creators(client, q="cooking")
    assert d["youtube"]["items"] == [] and "aren't set up" in d["youtube"]["note"] and d["items"]


def test_nobody_is_listed_until_someone_searches(client, login):
    for who in (client, login("br_senpai")):
        d = who.get("/api/directory/creators").json()
        assert d["idle"] and d["items"] == [] and d["total"] == 0 and len(d["niches"]) == len(ps.NICHES)
        b = who.get("/api/directory/brands").json()
        assert b["idle"] and b["items"] == [] and b["total"] == 0
    assert not _creators(client, niche="food", web="false")["idle"]


@pytest.fixture()
def no_web(monkeypatch):
    from app.services import suggest_web

    monkeypatch.setattr(suggest_web, "phrases", lambda q, kind="creators": [])


def test_suggestions_as_you_type(client, db, no_web):
    ps._VOCAB.clear()
    s = client.get("/api/directory/suggest", params={"q": "quic"}).json()["items"]
    assert s[0] == {"text": "Quick breakfast", "kind": "tag", "query": "Quick breakfast"}
    assert client.get("/api/directory/suggest", params={"q": "gam"}).json()["items"][0]["kind"] == "niche"
    # A creator's name suggests their exact @handle.
    names = [x for x in client.get("/api/directory/suggest", params={"q": "@creator"}).json()["items"] if x["kind"] == "creator"]
    assert names[0]["query"] == "@creator.b"
    # Only public profiles: a hidden creator isn't suggested.
    db.creators.update_one({"_id": "cr_b"}, {"$set": {"discoverable": False}})
    ps._VOCAB.clear()
    assert not any(x["query"] == "@creator.b" for x in client.get("/api/directory/suggest", params={"q": "creator"}).json()["items"])
    assert "creator.a" not in str(client.get("/api/directory/suggest", params={"q": "creator"}).json())  # reference profile
    brands = client.get("/api/directory/suggest", params={"q": "snack", "kind": "brands"}).json()["items"]
    assert {"Rangeela Snacks", "Namkeen and snacks"} <= {x["text"] for x in brands}
    assert client.get("/api/directory/suggest", params={"q": "", "kind": "creators"}).json()["items"] == []
    assert client.get("/api/directory/suggest", params={"q": "x", "kind": "other"}).status_code == 422


def test_typed_words_can_be_half_finished(client, no_web):
    ps._VOCAB.clear()
    texts = [x["text"] for x in client.get("/api/directory/suggest", params={"q": "tamil bre"}).json()["items"]]
    assert "Tamil home cooking" not in texts  # "bre" isn't in it
    assert [x["text"] for x in client.get("/api/directory/suggest", params={"q": "quick bre"}).json()["items"]][0] == "Quick breakfast"


def test_suggestions_are_what_people_search_for_like_youtube(client, db, monkeypatch):
    from app.services import suggest_web

    calls = []

    class R:
        def __init__(self, body):
            self.content = body.encode()

        def raise_for_status(self):
            pass

    def fake_get(url, params, timeout, headers):
        calls.append(params)
        return R('["tamil bre",["tamil breakfast recipes","tamil breakfast ideas","tamil bread"],[],{}]')

    db.suggest_cache.delete_many({})
    ps._VOCAB.clear()
    monkeypatch.setattr(suggest_web.httpx, "get", fake_get)
    items = client.get("/api/directory/suggest", params={"q": "Tamil bre"}).json()["items"]
    assert [x["text"] for x in items if x["kind"] == "search"] == ["tamil breakfast recipes", "tamil breakfast ideas", "tamil bread"]
    assert calls[0]["ds"] == "yt" and calls[0]["q"] == "tamil bre"  # YouTube's own suggestions
    client.get("/api/directory/suggest", params={"q": "tamil bre"})
    assert len(calls) == 1  # cached for a day
    client.get("/api/directory/suggest", params={"q": "snack", "kind": "brands"})
    assert "ds" not in calls[-1]  # brands: general suggestions

    def broken(*a, **k):
        raise suggest_web.httpx.ConnectError("blocked")

    monkeypatch.setattr(suggest_web.httpx, "get", broken)
    items = client.get("/api/directory/suggest", params={"q": "quick"}).json()["items"]
    assert items and items[0]["text"] == "Quick breakfast"  # ours still come
