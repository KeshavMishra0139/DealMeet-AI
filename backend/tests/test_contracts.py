"""Contract versions, counter-proposals, the status machine, deliverable reviews and idempotency."""
import time

from app.services import contracts

D = "dl_b_tiffin"  # an offer from Tamil Tiffin Diaries (a page) to Creator B


def _act(actor, action, deal=D, **body):
    return actor.post(f"/api/deals/{deal}/action", json={"action": action, **body})


def test_an_offer_is_version_1_from_the_brand(login):
    v = login("cr_b").get(f"/api/deals/{D}").json()
    assert v["status"] == "offer" and v["awaiting"] == "creator"
    first = v["versions"][0]
    assert first["number"] == 1 and first["author"] == "brand" and [a["side"] for a in first["accepted_by"]] == ["brand"]
    assert first["hash"] == contracts.digest(first["terms"]) and len(first["hash"]) == 64
    assert [a["id"] for a in v["actions"]] == ["accept", "counter", "propose", "decline"]


def test_proposals_make_new_versions_until_both_accept_the_same_one(login, db):
    b, t = login("cr_b"), login("pg_tiffin")
    r = _act(b, "propose", amount=2_500, deliverables=[{"kind": "reel", "count": 1}, {"kind": "story", "count": 2}], post_by="2026-11-15", note="Two stories too")
    v = r.json()
    assert r.status_code == 200 and v["status"] == "negotiating" and v["awaiting"] == "brand"
    assert v["versions"][1]["author"] == "creator" and v["versions"][1]["terms"]["amount"] == 2_500
    assert _act(b, "propose", amount=2_600).status_code == 409  # wait for the brand's answer
    v = _act(t, "propose", amount=2_200).json()  # the brand counters
    assert len(v["versions"]) == 3 and v["awaiting"] == "creator" and v["versions"][2]["terms"]["deliverables"][1]["count"] == 2
    v = _act(b, "accept", name="Meera").json()
    assert v["status"] == "contract_agreed" and v["agreed_version"] == 3
    d = db.deals.find_one({"_id": D})
    assert d["amount"] == 2_200 and d["post_by"] == "2026-11-15" and d["contract"]["hash"] == d["versions"][2]["hash"]
    assert {(a["version"], a["side"]) for a in d["acceptances"]} >= {(1, "brand"), (2, "creator"), (3, "brand"), (3, "creator")}
    # Earlier versions never change.
    assert d["versions"][0]["terms"]["amount"] == 1_500 and d["versions"][0]["hash"] == contracts.digest(d["versions"][0]["terms"])
    assert any("Post by 15 Nov" in t for t in v["contract"]["terms"])


def test_invalid_proposals_are_refused(login):
    b = login("cr_b")
    assert _act(b, "propose").status_code == 409  # nothing changes
    assert _act(b, "propose", amount=1_500).status_code == 409  # the terms already on the table
    assert _act(b, "propose", amount=100).status_code == 422
    assert _act(b, "propose", post_by="next week").status_code == 422
    assert _act(b, "propose", deliverables=[{"kind": "tweet", "count": 1}]).status_code == 422
    assert _act(b, "propose", usage_rights_days=999).status_code == 422
    assert _act(login("pg_tiffin"), "propose", amount=2_000).status_code == 409  # not the brand's turn
    assert _act(login("cr_a"), "propose", amount=2_000).status_code == 403  # not their deal


def test_every_status_change_is_checked_and_audited(login, db):
    b, t = login("cr_b"), login("pg_tiffin")
    since = time.time()  # the audit log is append-only and outlives each test
    assert _act(t, "approve").status_code == 409  # nothing submitted yet
    assert _act(b, "submit_post", url="https://www.instagram.com/reel/EARLY1/").status_code == 409  # not funded
    _act(b, "counter", amount=2_000)
    _act(t, "accept_counter")
    moves = [(e["from"], e["to"]) for e in db.audit.find({"action": "deal_status", "deal_id": D, "ts": {"$gte": since}}).sort("ts", 1)]
    assert moves == [("offer", "negotiating"), ("negotiating", "contract_agreed")]
    assert _act(t, "fund").status_code == 409  # funding only from a verified payment
    assert contracts.ALLOWED["paid"] == set() and contracts.ALLOWED["cancelled"] == set()


def test_submissions_revision_rounds_and_double_clicks(login, db):
    b, t = login("cr_b"), login("pg_tiffin")
    _act(b, "accept")
    assert t.post(f"/api/deals/{D}/pay").json()["deal"]["status"] == "in_progress"
    links = ["https://www.instagram.com/reel/RAGI1/", "https://www.instagram.com/p/RAGI2/"]
    v = _act(b, "submit_post", links=links, note="Reel plus a carousel").json()
    assert v["status"] == "submitted" and v["submissions"][0]["links"] == links and v["submissions"][0]["round"] == 1
    assert v["submissions"][0]["check"]["source"] == "not_connected"  # automatic checks need a connected account
    assert len(_act(b, "submit_post", links=links, note="Reel plus a carousel").json()["submissions"]) == 1  # same again: no change
    assert _act(b, "submit_post", links=["https://example.com/x"]).status_code == 409
    v = _act(t, "request_revision", note="Tag us in the caption").json()
    assert v["status"] == "revision_requested" and v["revision_round"] == 1
    assert _act(t, "request_revision", note="Tag us in the caption").json()["revision_round"] == 1  # double-click
    v = _act(b, "submit_post", links=["https://www.instagram.com/reel/RAGI3/"]).json()
    assert v["status"] == "submitted" and v["submissions"][-1]["round"] == 2
    v = _act(t, "approve").json()
    assert v["status"] == "paid" and v["payout"]["status"] == "simulated"  # demo escrow, labelled simulated
    assert _act(t, "approve").json()["status"] == "paid"  # approving twice changes nothing
    assert _act(b, "accept").json()["status"] == "paid"


def test_a_request_key_makes_retries_no_ops(login, db):
    b = login("cr_b")
    for _ in range(3):
        assert _act(b, "counter", amount=2_000, request_key="dl_b_tiffin:counter:1").status_code == 200
    d = db.deals.find_one({"_id": D})
    assert len(d["versions"]) == 2 and d["ops"] == ["dl_b_tiffin:counter:1"]


def test_collective_terms_are_fixed(login, db):
    thalam = login("br_thalam")
    pack = thalam.post("/api/listings/lst_thalam_collective/collective", json={}).json()
    booked = thalam.post("/api/listings/lst_thalam_collective/collective/book", json={"member_ids": [m["id"] for m in pack["members"]]}).json()
    d = db.deals.find_one({"collective_id": booked["id"]})
    member = login(d["creator_id"])
    assert _act(member, "propose", deal=d["_id"], amount=99_999).status_code == 409
    assert [a["id"] for a in member.get(f"/api/deals/{d['_id']}").json()["actions"]] == ["accept", "decline"]
