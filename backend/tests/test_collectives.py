"""Collectives: explained picks, adjusted terms, member confirmations, replacement and
per-member status that members can't see for each other."""
L = "lst_thalam_collective"


def _pack(brand):
    return brand.post(f"/api/listings/{L}/collective", json={}).json()


def _book(brand, pack, **extra):
    r = brand.post(f"/api/listings/{L}/collective/book", json={"member_ids": [m["id"] for m in pack["members"]], **extra})
    assert r.status_code == 200, r.text
    return brand.get(f"/api/collectives/{r.json()['id']}").json()


def _accept(login, member):
    r = login(member["creator_id"]).post(f"/api/deals/{member['deal_id']}/action", json={"action": "accept"})
    assert r.status_code == 200, r.text


def test_the_builder_explains_its_method_and_each_pick(login):
    pack = _pack(login("br_thalam"))
    m = pack["method"]
    assert "per rupee" in m["objective"] and any("Trust Score at least" in t for t in m["thresholds"]) and any("Audience fit at least 55" in t for t in m["thresholds"])
    for member in pack["members"]:
        assert len(member["why"]) >= 4 and any("Audience fit" in w for w in member["why"]) and member["deliverables"]
        if member["reach"] is None:
            assert "isn't shared" in member["why"][0] or "isn't shared" in member["why"][1]


def test_the_brand_adjusts_terms_before_sending(login, db):
    t = login("br_thalam")
    pack = _pack(t)
    first = pack["members"][0]["id"]
    assert t.post(f"/api/listings/{L}/collective/book", json={"member_ids": [first, pack["members"][1]["id"]], "adjust": {first: {"price": 100}}}).status_code == 422
    assert t.post(f"/api/listings/{L}/collective/book", json={"member_ids": [first, pack["members"][1]["id"]], "adjust": {first: {"deliverables": [{"kind": "tweet", "count": 1}]}}}).status_code == 422
    col = _book(t, pack, adjust={first: {"price": 4_321, "deliverables": [{"kind": "reel", "count": 2}]}})
    mine = next(m for m in col["members"] if m["creator_id"] == first)
    assert mine["price"] == 4_321 and mine["deliverables"] == "2 reels" and abs(sum(m["split"] for m in col["members"]) - 1) < 0.01
    deal = db.deals.find_one({"_id": mine["deal_id"]})
    assert deal["amount"] == 4_321 and deal["versions"][0]["terms"]["deliverables"] == [{"kind": "reel", "count": 2}]
    assert col["confirmations"]["status"] == "awaiting_confirmations" and col["total"] == sum(m["price"] for m in col["members"])


def test_it_activates_only_when_every_member_confirms(login, db):
    t = login("br_thalam")
    col = _book(t, _pack(t))
    for m in col["members"][:-1]:
        _accept(login, m)
    r = t.post(f"/api/collectives/{col['id']}/fund")
    assert r.status_code == 409 and "1 of" in r.json()["detail"]
    _accept(login, col["members"][-1])
    assert t.get(f"/api/collectives/{col['id']}").json()["confirmations"]["status"] == "active"
    funded = t.post(f"/api/collectives/{col['id']}/fund").json()
    assert funded["funded"] and all(m["payment_status"] == "In escrow (simulated)" for m in funded["members"])
    assert {d["stage"] for d in db.deals.find({"collective_id": col["id"]})} == {"escrow_funded"}


def test_a_member_who_declines_is_replaced(login, db):
    t = login("br_thalam")
    pack = _pack(t)
    col = _book(t, {"members": pack["members"][:3]})  # a small pack leaves others who fit
    out = col["members"][0]
    login(out["creator_id"]).post(f"/api/deals/{out['deal_id']}/action", json={"action": "decline"})
    assert t.get(f"/api/collectives/{col['id']}").json()["confirmations"]["status"] == "needs_replacement"
    options = t.get(f"/api/collectives/{col['id']}/replacements").json()["items"]
    assert options and all(o["id"] not in {m["creator_id"] for m in col["members"]} for o in options) and options[0]["why"]
    stay = col["members"][1]["creator_id"]
    assert t.post(f"/api/collectives/{col['id']}/replace", json={"out_id": stay, "in_id": options[0]["id"]}).status_code == 409  # didn't decline
    assert t.post(f"/api/collectives/{col['id']}/replace", json={"out_id": out["creator_id"], "in_id": stay}).status_code == 409
    new = t.post(f"/api/collectives/{col['id']}/replace", json={"out_id": out["creator_id"], "in_id": options[0]["id"]}).json()
    ids = {m["creator_id"] for m in new["members"]}
    assert out["creator_id"] not in ids and options[0]["id"] in ids and new["confirmations"]["status"] == "awaiting_confirmations"
    assert new["total"] == sum(m["price"] for m in new["members"])
    for m in new["members"]:
        _accept(login, m)
    assert t.get(f"/api/collectives/{col['id']}").json()["confirmations"]["status"] == "active"


def test_members_see_only_their_own_terms_and_others_cant_see_the_pack(login):
    t = login("br_thalam")
    col = _book(t, _pack(t))
    a = col["members"][0]
    seen = login(a["creator_id"]).get(f"/api/collectives/{col['id']}").json()
    mine = next(m for m in seen["members"] if m["creator_id"] == a["creator_id"])
    assert mine["price"] == a["price"] and mine["deliverables"] and mine["payment_status"] == "Not funded yet"
    for m in seen["members"]:
        if m["creator_id"] != a["creator_id"]:
            assert m["price"] is None and m["deliverables"] is None and m["payment_status"] is None and m["deal_id"] is None
    assert login("br_senpai").get(f"/api/collectives/{col['id']}").status_code == 403
    assert login("br_senpai").post(f"/api/collectives/{col['id']}/replace", json={"out_id": "x1x", "in_id": "y1y"}).status_code == 403
    assert login("cr_a").get(f"/api/collectives/{col['id']}").status_code == 403
