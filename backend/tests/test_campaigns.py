"""Brand organisation profile and the campaign lifecycle: draft -> live -> paused <-> live, any -> closed."""
from datetime import timedelta

from app.config import today

FUTURE = (today() + timedelta(days=30)).isoformat()
COMPLETE = {
    "title": "Festive anime merch reels",
    "summary": "Two reels showing the festive drop, posted before Diwali.",
    "objectives": ["launch", "sales"],
    "niches": ["anime_edits"],
    "languages": ["hi", "en"],
    "audience_ages": ["18-24", "25-34"],
    "audience_gender": "any",
    "regions": ["Pan-India"],
    "budget_min": 6_000,
    "budget_max": 20_000,
    "reels": 1,
    "stories": 1,
    "usage_rights_days": 30,
    "deadline": FUTURE,
}


def _draft(brand, **kw):
    r = brand.post("/api/brands/br_senpai/campaigns", json={"title": "Festive anime merch reels", **kw})
    assert r.status_code == 200, r.text
    return r.json()


def _status(brand, lid, action):
    return brand.post(f"/api/campaigns/{lid}/status", json={"action": action})


def _live(brand):
    lid = _draft(brand, **{k: v for k, v in COMPLETE.items() if k != "title"})["id"]
    assert _status(brand, lid, "publish").status_code == 200
    return lid


# ------------------------------------------------------------------ access
def test_only_the_owner_manages_a_campaign(client, login):
    b = login("br_senpai")
    lid = _draft(b)["id"]
    assert client.post("/api/brands/br_senpai/campaigns", json={"title": "Nope nope"}).status_code == 401
    assert client.patch(f"/api/campaigns/{lid}", json={"title": "Nope nope"}).status_code == 401
    other = login("br_thalam")
    assert other.post("/api/brands/br_senpai/campaigns", json={"title": "Nope nope"}).status_code == 403
    assert other.patch(f"/api/campaigns/{lid}", json={"title": "Nope nope"}).status_code == 403
    assert other.post(f"/api/campaigns/{lid}/status", json={"action": "publish"}).status_code == 403
    assert other.get(f"/api/campaigns/{lid}/applications").status_code == 403
    assert login("cr_a").post(f"/api/campaigns/{lid}/status", json={"action": "publish"}).status_code == 403


def test_invalid_input(login):
    b = login("br_senpai")
    assert b.post("/api/brands/br_senpai/campaigns", json={"title": "x"}).status_code == 422
    assert b.post("/api/brands/br_senpai/campaigns", json={"title": "Good title", "niches": ["knitting"]}).status_code == 422
    assert b.post("/api/brands/br_senpai/campaigns", json={"title": "Good title", "objectives": ["fame"]}).status_code == 422
    assert b.post("/api/brands/br_senpai/campaigns", json={"title": "Good title", "deadline": "next week"}).status_code == 422
    lid = _draft(b)["id"]
    assert _status(b, lid, "explode").status_code == 422


# ------------------------------------------------------------------ drafts and publishing
def test_drafts_are_invisible_to_creators(login, db):
    b = login("br_senpai")
    d = _draft(b, **{k: v for k, v in COMPLETE.items() if k != "title"})
    assert d["status"] == "draft" and d["missing"] == []
    lid = d["id"]
    a = login("cr_a")
    assert a.get(f"/api/listings/{lid}").status_code == 404
    ids = {i["id"] for i in a.get("/api/creators/cr_a/opportunities").json()["items"]}
    assert lid not in ids
    assert a.post("/api/creators/cr_a/apply", json={"listing_id": lid, "scopes": {"stats": True}}).status_code == 404
    offer = b.post("/api/offers", json={"creator_id": "cr_a", "listing_id": lid, "amount": 9_000})
    assert offer.status_code == 409 and "draft" in offer.json()["detail"]
    # The owner sees it, with what's missing and what it can do next.
    view = b.get(f"/api/listings/{lid}").json()
    assert view["status"] == "draft" and view["actions"] == ["publish", "close"]


def test_publishing_says_what_is_missing(login):
    b = login("br_senpai")
    lid = _draft(b, budget_min=9_000, budget_max=5_000, deadline=(today() - timedelta(days=1)).isoformat())["id"]
    r = _status(b, lid, "publish")
    assert r.status_code == 422
    missing = {m["field"] for m in r.json()["detail"]["missing"]}
    assert {"summary", "objectives", "niches", "languages", "audience", "budget", "deadline"} <= missing
    assert b.get(f"/api/listings/{lid}").json()["status"] == "draft"
    fixed = {k: v for k, v in COMPLETE.items() if k != "title"}
    assert b.patch(f"/api/campaigns/{lid}", json=fixed).status_code == 200
    r = _status(b, lid, "publish")
    assert r.status_code == 200 and r.json()["status"] == "live" and r.json()["changed"] is True
    # A repeated request changes nothing.
    again = _status(b, lid, "publish")
    assert again.status_code == 200 and again.json()["changed"] is False


def test_a_live_campaign_cant_be_edited_into_an_invalid_one(login, db):
    b = login("br_senpai")
    lid = _live(b)
    r = b.patch(f"/api/campaigns/{lid}", json={"objectives": [], "budget_max": 100})
    assert r.status_code == 422 and {m["field"] for m in r.json()["detail"]["missing"]} == {"objectives", "budget"}
    assert db.listings.find_one({"_id": lid})["objectives"] == ["launch", "sales"]
    ok = b.patch(f"/api/campaigns/{lid}", json={"budget_max": 25_000, "cities": ["Delhi"]})
    assert ok.status_code == 200 and ok.json()["budget"]["per_creator_max"] == 25_000
    assert b.patch(f"/api/campaigns/{lid}", json={"cities": ["Atlantis"]}).status_code == 422


def test_pause_resume_and_close(login, db):
    b, a, other = login("br_senpai"), login("cr_a"), login("cr_b")
    lid = _live(b)
    assert a.post("/api/creators/cr_a/apply", json={"listing_id": lid, "scopes": {"stats": True}}).json()["status"] == "applied"
    assert _status(b, lid, "pause").json()["status"] == "paused"
    # Paused: no new applications or offers; the creator who applied can still see it.
    assert other.post("/api/creators/cr_b/apply", json={"listing_id": lid, "scopes": {"stats": True}}).status_code == 404
    assert b.post("/api/offers", json={"creator_id": "cr_a", "listing_id": lid, "amount": 9_000}).status_code == 409
    assert a.get(f"/api/listings/{lid}").json()["status"] == "paused"
    assert other.get(f"/api/listings/{lid}").status_code == 404
    assert _status(b, lid, "publish").status_code == 409
    # Resuming checks the campaign again: a deadline that has passed blocks it.
    db.listings.update_one({"_id": lid}, {"$set": {"deadline": (today() - timedelta(days=1)).isoformat()}})
    r = _status(b, lid, "resume")
    assert r.status_code == 422 and r.json()["detail"]["missing"][0]["field"] == "deadline"
    db.listings.update_one({"_id": lid}, {"$set": {"deadline": FUTURE}})
    assert _status(b, lid, "resume").json()["status"] == "live"
    # Closed is final.
    assert _status(b, lid, "close").json()["status"] == "closed"
    assert _status(b, lid, "close").json()["changed"] is False
    assert _status(b, lid, "resume").status_code == 409
    assert b.patch(f"/api/campaigns/{lid}", json={"title": "Reopen it please"}).status_code == 409
    assert lid not in {i["id"] for i in a.get("/api/creators/cr_a/opportunities").json()["items"]}


def test_applications_view_and_every_change_is_audited(login, db):
    b, a, c = login("br_senpai"), login("cr_a"), login("cr_b")
    lid = _live(b)
    a.post("/api/creators/cr_a/apply", json={"listing_id": lid, "scopes": {"stats": True}})
    c.post("/api/creators/cr_b/apply", json={"listing_id": lid, "scopes": {"stats": True}})
    apps = b.get(f"/api/campaigns/{lid}/applications").json()
    assert apps["counts"]["applied"] == 2
    r = b.post(f"/api/campaigns/{lid}/applications/cr_a", json={"status": "shortlisted"})
    assert r.json()["counts"]["shortlisted"] == 1
    b.post(f"/api/campaigns/{lid}/applications/cr_b", json={"status": "declined"})
    # Applying again doesn't undo the brand's decision.
    assert c.post("/api/creators/cr_b/apply", json={"listing_id": lid, "scopes": {"stats": True}}).json()["status"] == "declined"
    deal = b.post("/api/offers", json={"creator_id": "cr_a", "listing_id": lid, "amount": 12_000}).json()["id"]
    apps = b.get(f"/api/campaigns/{lid}/applications").json()
    item = next(i for i in apps["items"] if i["creator_id"] == "cr_a")
    assert item["status"] == "offered" and item["deal_id"] == deal
    assert b.post(f"/api/campaigns/{lid}/applications/cr_a", json={"status": "declined"}).status_code == 409
    assert b.post(f"/api/campaigns/{lid}/applications/cr_c", json={"status": "declined"}).status_code == 404
    assert b.post(f"/api/campaigns/{lid}/applications/cr_a", json={"status": "offered"}).status_code == 422
    actions = {e["action"] for e in db.audit.find({"listing_id": lid})}
    assert {"campaign_created", "campaign_publish", "campaign_application"} <= actions
    history = [h["action"] for h in b.get(f"/api/listings/{lid}").json()["history"]]
    assert history[:2] == ["created", "publish"] and "application" in history
    # Creators don't see the brand's history.
    assert "history" not in a.get(f"/api/listings/{lid}").json()


# ------------------------------------------------------------------ the brand's organisation profile
def test_brand_profile_owner_only(client, login):
    assert client.get("/api/brands/br_senpai/profile").status_code == 401
    assert login("br_thalam").get("/api/brands/br_senpai/profile").status_code == 403
    assert login("br_thalam").patch("/api/brands/br_senpai/profile", json={"name": "Hacked"}).status_code == 403
    p = login("br_senpai").get("/api/brands/br_senpai/profile").json()
    assert p["slug"] == "senpai-supply-co" and "contact" in p


def test_brand_profile_edits_are_validated_and_audited(login, db):
    b = login("br_senpai")
    r = b.patch("/api/brands/br_senpai/profile", json={"website": "https://senpai.example", "description": "Anime merch for India.",
                                                       "contact": {"name": "Riya", "email": "riya@senpai.example"}})
    assert r.status_code == 200 and r.json()["website"] == "https://senpai.example"
    assert r.json()["contact"]["email"] == "riya@senpai.example"
    assert b.patch("/api/brands/br_senpai/profile", json={"website": "senpai"}).status_code == 422
    assert b.patch("/api/brands/br_senpai/profile", json={"slug": "Bad Slug!"}).status_code == 422
    assert b.patch("/api/brands/br_senpai/profile", json={"slug": "admin"}).status_code == 422
    assert b.patch("/api/brands/br_senpai/profile", json={"slug": "thalam-foods"}).status_code == 409
    assert b.patch("/api/brands/br_senpai/profile", json={"contact": {"email": "nope"}}).status_code == 422
    assert b.patch("/api/brands/br_senpai/profile", json={"slug": "senpai"}).json()["slug"] == "senpai"
    assert db.audit.count_documents({"action": "brand_profile_updated", "brand_id": "br_senpai"}) == 2
    # The contact stays private: a creator viewing a campaign sees the brand's name and address only.
    lid = _live(b)
    owner = login("cr_a").get(f"/api/listings/{lid}").json()["owner"]
    assert owner == {"id": "br_senpai", "name": "Senpai Supply Co.", "hue": owner["hue"], "slug": "senpai"}


def test_a_new_brand_gets_a_unique_address(login, db):
    me = login("new_brand")
    body = {"name": "Thalam Foods", "category": "Food", "niches": ["food"], "ages": ["25-34"], "languages": ["ta"], "budget_monthly": 50_000,
            "website": "https://example.in"}
    bid = me.post("/api/brands", json=body).json()["id"]
    b = db.brands.find_one({"_id": bid})
    assert b["slug"] == "thalam-foods-2" and b["source"] == "manual" and b["website"] == "https://example.in"
