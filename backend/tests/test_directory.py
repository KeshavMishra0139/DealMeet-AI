"""Brand directory, brand pages, unclaimed brands, claims, removal requests and Dream Brands."""
from pymongo.errors import OperationFailure

from app.services import directory as dr


def _search(client, **params):
    r = client.get("/api/directory/brands", params=params)
    assert r.status_code == 200, r.text
    return r.json()


# ------------------------------------------------------------------ search
def test_search_by_name_category_language_and_open_campaigns(client, login, db):
    d = _search(client, q="senpai")
    assert d["search"] == "regex" and [b["slug"] for b in d["items"]] == ["senpai-supply-co"]
    assert _search(client, category="anime MERCH store")["items"][0]["id"] == "br_senpai"
    tamil = {b["id"] for b in _search(client, language="ta")["items"]}
    assert "br_thalam" in tamil and "br_senpai" not in tamil
    live = {x["owner_id"] for x in db.listings.find({"status": "live"})}
    open_ids = {b["id"] for b in _search(client, open="true")["items"]}
    assert open_ids and open_ids <= live
    member = login("cr_b")
    every = {b["id"] for lang in ("hi", "ta", "en") for b in member.get("/api/directory/brands", params={"language": lang}).json()["items"]}
    assert every
    assert not any(i.startswith("xx_") for i in every)  # spam examples never show


def test_search_input_is_escaped(client):
    # Symbols are never a pattern: only the words in a search count.
    for q in ["[a-z]+", "\\", "(?i)x", "$where"]:
        assert _search(client, q=q)["total"] == 0
    assert [b["id"] for b in _search(client, q="Senpai.*(")["items"]] == ["br_senpai"]
    assert client.get("/api/directory/brands", params={"q": "x" * 81}).status_code == 422


def test_atlas_search_is_used_on_atlas_and_falls_back_when_the_index_is_missing(client, monkeypatch):
    monkeypatch.setattr(dr, "db_mode", lambda: "atlas")
    monkeypatch.setattr(dr, "_atlas_ids", lambda q, limit: ["br_thalam", "br_senpai"])
    d = _search(client, q="snacks")
    assert d["search"] == "atlas" and [b["id"] for b in d["items"]] == ["br_thalam", "br_senpai"]

    def broken(q, limit):
        raise OperationFailure("index not found", code=40324)

    monkeypatch.setattr(dr, "_atlas_ids", broken)
    d = _search(client, q="senpai")
    assert d["search"] == "regex" and "isn't available" in d["note"] and d["items"][0]["id"] == "br_senpai"


# ------------------------------------------------------------------ pages
def test_brand_page_shows_live_campaigns_only(client, login, db):
    b = login("br_senpai")
    draft = b.post("/api/brands/br_senpai/campaigns", json={"title": "Secret draft drop"}).json()["id"]
    p = client.get("/api/directory/brands/senpai-supply-co").json()
    titles = {c["title"] for c in p["campaigns"]}
    assert p["claimed"] and p["description"] and "Secret draft drop" not in titles and p["open_campaigns"] == len(titles) > 0
    assert draft not in {c["id"] for c in p["campaigns"]}
    assert client.get("/api/directory/brands/no-such-brand").status_code == 404
    assert client.get("/api/directory/brands/fame-boost-agency").status_code == 404


def test_unclaimed_pages_show_only_public_basics(client):
    p = client.get("/api/directory/brands/notebook-nagar").json()
    assert p["claimed"] is False and p["note"] == "Not on DealMeet AI and not affiliated with us."
    assert {"description", "website", "campaigns", "hue"}.isdisjoint(p)
    assert p["source"] == "synthetic"


# ------------------------------------------------------------------ Dream Brands
def test_dream_brands_owner_only(client, login):
    assert client.put("/api/creators/cr_a/dream-brands/br_senpai", json={}).status_code == 401
    other = login("cr_b")
    assert other.client.put("/api/creators/cr_a/dream-brands/br_senpai", json={}, headers=other.headers).status_code == 403
    a = login("cr_a")
    assert a.client.put("/api/creators/cr_a/dream-brands/br_nope", json={}, headers=a.headers).status_code == 404


def test_counts_only_creators_with_connected_accounts_and_names_by_consent(client, login, db):
    a, b = login("cr_a"), login("cr_b")
    a.client.put("/api/creators/cr_a/dream-brands/br_senpai", json={"show_name": True}, headers=a.headers)
    b.client.put("/api/creators/cr_b/dream-brands/br_senpai", json={"show_name": False}, headers=b.headers)
    p = client.get("/api/directory/brands/senpai-supply-co").json()
    assert p["dream"] == {"connected": 0, "others": 2}  # sample profiles have no connected accounts
    db.connections.insert_one({"_id": "cn_test", "creator_id": "cr_b", "user_id": "us_cr_b", "platform": "instagram", "status": "connected"})
    assert client.get("/api/directory/brands/senpai-supply-co").json()["dream"] == {"connected": 1, "others": 1}
    owner = login("br_senpai").get("/api/directory/brands/senpai-supply-co").json()
    assert [n["id"] for n in owner["dream"]["names"]] == ["cr_a"]  # only the creator who agreed
    assert "names" not in login("br_thalam").get("/api/directory/brands/senpai-supply-co").json()["dream"]
    assert a.get("/api/directory/brands/senpai-supply-co").json()["viewer"] == {"role": "creator", "creator_id": "cr_a", "saved": True, "show_name": True}
    assert a.delete("/api/creators/cr_a/dream-brands/br_senpai").json()["saved"] is False


def test_saved_brands_notify_when_they_open_a_campaign(login, db):
    a, b = login("cr_a"), login("br_senpai")
    a.client.put("/api/creators/cr_a/dream-brands/br_senpai", json={}, headers=a.headers)
    from test_campaigns import COMPLETE

    lid = b.post("/api/brands/br_senpai/campaigns", json=COMPLETE).json()["id"]
    assert not a.get("/api/creators/cr_a/dream-brands").json()["notifications"]  # a draft says nothing
    b.post(f"/api/campaigns/{lid}/status", json={"action": "publish"})
    b.post(f"/api/campaigns/{lid}/status", json={"action": "pause"})
    b.post(f"/api/campaigns/{lid}/status", json={"action": "resume"})
    d = a.get("/api/creators/cr_a/dream-brands").json()
    assert len(d["notifications"]) == 1 and d["notifications"][0]["title"] == COMPLETE["title"] and d["unread"] == 1
    assert d["items"][0]["id"] == "br_senpai"
    a.post("/api/creators/cr_a/dream-brands/read")
    assert a.get("/api/creators/cr_a/dream-brands").json()["unread"] == 0


# ------------------------------------------------------------------ unclaimed brands, claims, removal
def test_only_admins_add_unclaimed_brands(client, login, admin):
    body = {"name": "Chai Tapri Co", "category": "Tea", "public_handles": {"instagram": "chaitapri.co"}, "reason": "Creators keep pitching them."}
    assert client.post("/api/admin/brands", json=body).status_code == 401
    assert login("br_senpai").post("/api/admin/brands", json=body).status_code == 403
    assert admin.post("/api/admin/brands", json={**body, "public_handles": {"instagram": "not a handle!"}}).status_code == 422
    assert admin.post("/api/admin/brands", json={**body, "reason": "   "}).status_code == 422  # every admin action needs a reason
    d = admin.post("/api/admin/brands", json=body).json()
    assert d["claimed"] is False and d["public_handles"] == {"instagram": "@chaitapri.co"} and d["slug"] == "chai-tapri-co"
    assert admin.post("/api/admin/brands", json=body).status_code == 409
    assert "chai-tapri-co" in {b["slug"] for b in _search(client, q="chai")["items"]}


def test_claiming_a_page_needs_an_admin(client, login, admin, db):
    me = login("new_brand")
    assert login("cr_a").post("/api/directory/brands/notebook-nagar/claim", json={"message": "We run Notebook Nagar."}).status_code == 403
    assert login("br_senpai").post("/api/directory/brands/notebook-nagar/claim", json={"message": "We run Notebook Nagar."}).status_code == 409
    assert me.post("/api/directory/brands/senpai-supply-co/claim", json={"message": "This is our brand page."}).status_code == 409
    r = me.post("/api/directory/brands/notebook-nagar/claim", json={"message": "We run Notebook Nagar in Pune."}).json()
    assert r["status"] == "pending" and r["duplicate"] is False
    assert me.post("/api/directory/brands/notebook-nagar/claim", json={"message": "We run Notebook Nagar in Pune."}).json()["duplicate"] is True
    assert client.get("/api/directory/brands/notebook-nagar").json()["claimed"] is False  # stays unclaimed until approved
    ok = "Checked their company email domain."
    assert me.post(f"/api/admin/claims/{r['id']}", json={"action": "approve", "reason": ok}).status_code == 403
    assert admin.post(f"/api/admin/claims/{r['id']}", json={"action": "approve"}).status_code == 422
    assert admin.get("/api/admin/claims").json()["items"][0]["_id"] == r["id"]
    done = admin.post(f"/api/admin/claims/{r['id']}", json={"action": "approve", "reason": ok}).json()
    assert done["status"] == "approved" and done["decision_reason"] == ok
    assert admin.post(f"/api/admin/claims/{r['id']}", json={"action": "reject", "reason": ok}).status_code == 409
    assert client.get("/api/directory/brands/notebook-nagar").json()["claimed"] is True
    assert me.get("/api/brands/br_unc_notebook/profile").status_code == 200  # the account now owns it
    assert db.audit.count_documents({"action": "brand_claim_approved", "brand_id": "br_unc_notebook", "reason": ok}) == 1


def test_anyone_can_ask_to_remove_an_unclaimed_page(client, admin, login, db):
    body = {"reason": "We are this company and don't want a page here.", "contact": "legal@kokum.example"}
    r = client.post("/api/directory/brands/kokum-and-kesar-pantry/removal-request", json=body)
    assert r.status_code == 200 and r.json()["status"] == "pending"
    assert client.post("/api/directory/brands/senpai-supply-co/removal-request", json=body).status_code == 409
    assert client.post("/api/directory/brands/kokum-and-kesar-pantry/removal-request", json={"reason": "short"}).status_code == 422
    codes = [client.post("/api/directory/brands/kokum-and-kesar-pantry/removal-request", json=body).status_code for _ in range(5)]
    assert codes[-1] == 429
    a = login("cr_a")
    a.client.put("/api/creators/cr_a/dream-brands/br_unc_kokum", json={}, headers=a.headers)
    rid = admin.get("/api/admin/removal-requests").json()["items"][0]["_id"]
    assert admin.post(f"/api/admin/removal-requests/{rid}", json={"action": "remove"}).status_code == 422
    assert admin.post(f"/api/admin/removal-requests/{rid}", json={"action": "remove", "reason": "Request came from the company."}).json()["status"] == "removed"
    assert client.get("/api/directory/brands/kokum-and-kesar-pantry").status_code == 404
    assert not db.wishlists.count_documents({"brand_id": "br_unc_kokum"})
