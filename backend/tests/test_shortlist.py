"""Brands acting on matches: ranking criteria, evidence, the shortlist, compare and offer drafts."""
import json

from app.engines import brand_matching as bm
from app.services import consent as cs

L = "lst_senpai_hoodie"
PRIVATE = ("income_history", "income_goal", "manual_history", "email", "phone", "past_deals", "best_deal")


def _ids(rows):
    return [r["id"] for r in rows]


# ------------------------------------------------------------------ ranking, evidence and limitations
def test_matches_return_the_ranking_criteria_and_weights(login):
    m = login("br_senpai").get(f"/api/listings/{L}/matches").json()
    assert [c["key"] for c in m["criteria"]] == ["fit", "reach", "engagement", "trust", "budget"]
    assert abs(sum(c["weight"] for c in m["criteria"]) - 1) < 1e-9
    row = m["items"][0]
    assert [c["key"] for c in row["ranking"]] == ["fit", "reach", "engagement", "trust", "budget"]
    assert abs(sum(c["weight"] * c["score"] for c in row["ranking"]) - row["rank"]) < 1e-3
    assert row["fair"]["estimate"] is True and row["fair"]["range"]["low"] < row["fair"]["range"]["high"]
    assert row["limitations"] and any("estimate" in x for x in row["limitations"])
    assert all(e["source"] in ("instagram_api", "youtube_api", "manual", "synthetic") for e in row["evidence"])


def test_evidence_follows_what_the_creator_shares(login, db):
    cs.grant("cr_g08", "br_senpai", {"stats": False, "demographics": True, "rate_card": False})
    items = login("br_senpai").get(f"/api/listings/{L}/matches").json()["items"]
    row = next(r for r in items if r["id"] == "cr_g08")
    assert row["followers"] is None and row["median_views"] is None
    keys = {e["key"] for e in row["evidence"]}
    assert "followers" not in keys and "median_views" not in keys and {"age", "women", "cities"} <= keys
    hidden = {c["key"]: c for c in row["ranking"]}
    # Built from stats they haven't shared: used to rank, never shown.
    assert hidden["reach"]["score"] is None and hidden["engagement"]["score"] is None
    assert "Reach and engagement aren't shared with you." in row["limitations"]
    text = json.dumps(items)
    assert not any(f'"{k}"' in text for k in PRIVATE)


def test_missing_metrics_score_neutral_with_a_note(db):
    c = {**db.creators.find_one({"_id": "cr_g04"}), "reels": [], "follower_history": [], "comment_insights": {}}
    x, b = db.listings.find_one({"_id": L}), db.brands.find_one({"_id": "br_senpai"})
    row = bm.rank_creator(c, x, b, {"stats": True, "demographics": True, "rate_card": True})
    comps = {k["key"]: k for k in row["ranking"]}
    assert comps["engagement"]["missing"] and comps["engagement"]["score"] == bm.NEUTRAL["engagement"]
    assert comps["trust"]["missing"] and comps["trust"]["score"] == bm.NEUTRAL["trust"]
    assert "neutral" in comps["trust"]["note"] and comps["trust"]["note"] in row["limitations"]


# ------------------------------------------------------------------ shortlist
def test_shortlist_is_owner_only(client, login):
    assert client.get(f"/api/campaigns/{L}/shortlist").status_code == 401
    other = login("br_thalam")
    assert other.get(f"/api/campaigns/{L}/shortlist").status_code == 403
    r = other.client.put(f"/api/campaigns/{L}/shortlist/cr_g08", json={}, headers=other.headers)
    assert r.status_code == 403
    assert login("cr_a").get(f"/api/campaigns/{L}/shortlist").status_code == 403


def test_add_note_and_remove(login):
    b = login("br_senpai")
    put = lambda cid, note=None: b.client.put(f"/api/campaigns/{L}/shortlist/{cid}", json={"note": note}, headers=b.headers)
    assert put("cr_g08", "Great edits").status_code == 200
    r = put("cr_g08", "Great edits, ask about Diwali")  # same creator again: the note changes, nothing duplicates
    items = r.json()["items"]
    assert len(items) == 1 and items[0]["note"] == "Great edits, ask about Diwali" and items[0]["evidence"]
    assert put("cr_nobody").status_code == 404
    assert b.client.put(f"/api/campaigns/{L}/shortlist/cr_g04", json={"note": "x" * 300}, headers=b.headers).status_code == 422
    assert b.delete(f"/api/campaigns/{L}/shortlist/cr_g08").status_code == 200
    assert b.delete(f"/api/campaigns/{L}/shortlist/cr_g08").status_code == 404
    assert b.get(f"/api/listings/{L}/matches").json()["items"][1]["shortlisted"] is False


def test_shortlisting_an_applicant_updates_their_application(login, db):
    b, g = login("br_senpai"), login("cr_g04")
    g.post("/api/creators/cr_g04/apply", json={"listing_id": L, "scopes": {"stats": True}})
    b.client.put(f"/api/campaigns/{L}/shortlist/cr_g04", json={}, headers=b.headers)
    assert db.applications.find_one({"listing_id": L, "creator_id": "cr_g04"})["status"] == "shortlisted"
    b.delete(f"/api/campaigns/{L}/shortlist/cr_g04")
    assert db.applications.find_one({"listing_id": L, "creator_id": "cr_g04"})["status"] == "applied"
    # And shortlisting from the applications view puts them on the shortlist.
    b.post(f"/api/campaigns/{L}/applications/cr_g04", json={"status": "shortlisted"})
    assert "cr_g04" in _ids(b.get(f"/api/campaigns/{L}/shortlist").json()["items"])


def test_a_creator_who_stops_sharing_shows_as_unavailable(login, db):
    b = login("br_senpai")
    b.client.put(f"/api/campaigns/{L}/shortlist/cr_g08", json={"note": "keep"}, headers=b.headers)
    cs.revoke("cr_g08", "br_senpai")
    item = b.get(f"/api/campaigns/{L}/shortlist").json()["items"][0]
    assert item == {"id": "cr_g08", "available": False, "note": "keep", "added_at": item["added_at"], "draft": None, "deal_stage": None}


# ------------------------------------------------------------------ compare
def test_compare_two_to_four_shortlisted_creators_and_log_the_views(login, db):
    b = login("br_senpai")
    for cid in ("cr_g08", "cr_g04", "cr_g03", "cr_g10", "cr_g06"):
        b.client.put(f"/api/campaigns/{L}/shortlist/{cid}", json={}, headers=b.headers)
    assert b.get(f"/api/campaigns/{L}/compare", params={"ids": "cr_g08"}).status_code == 422
    assert b.get(f"/api/campaigns/{L}/compare", params={"ids": "cr_g08,cr_g04,cr_g03,cr_g10,cr_g06"}).status_code == 422
    assert b.get(f"/api/campaigns/{L}/compare", params={"ids": "cr_g08,cr_a"}).status_code == 422  # not shortlisted
    before = db.consent_audit.count_documents({"lister_id": "br_senpai", "action": "viewed"})
    r = b.get(f"/api/campaigns/{L}/compare", params={"ids": "cr_g08,cr_g04,cr_g03"})
    assert r.status_code == 200 and _ids(r.json()["items"]) == ["cr_g08", "cr_g04", "cr_g03"]
    assert db.consent_audit.count_documents({"lister_id": "br_senpai", "action": "viewed"}) == before + 3
    cs.revoke("cr_g04", "br_senpai")
    assert b.get(f"/api/campaigns/{L}/compare", params={"ids": "cr_g08,cr_g04"}).status_code == 409


# ------------------------------------------------------------------ offer drafts
def _draft(b, cid, **kw):
    return b.post(f"/api/campaigns/{L}/offer-drafts", json={"creator_id": cid, **kw})


def test_drafts_are_sent_only_after_confirm_and_never_twice(login, db):
    b = login("br_senpai")
    assert _draft(b, "cr_g08").status_code == 409  # shortlist first
    b.client.put(f"/api/campaigns/{L}/shortlist/cr_g08", json={}, headers=b.headers)
    d = _draft(b, "cr_g08").json()
    assert d["created"] and d["status"] == "draft" and d["amount"] == d["fair_estimate"]["total"]
    assert _draft(b, "cr_g08").json()["id"] == d["id"]  # one draft per creator per campaign
    assert not db.deals.count_documents({"listing_id": L, "creator_id": "cr_g08"})  # nothing sent yet
    edited = b.patch(f"/api/offer-drafts/{d['id']}", json={"amount": 9_500, "message": "Diwali drop, two stories"}).json()
    assert edited["amount"] == 9_500 and edited["message"] == "Diwali drop, two stories"
    assert b.patch(f"/api/offer-drafts/{d['id']}", json={"amount": 10}).status_code == 422
    assert b.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": False}).status_code == 422
    assert b.post(f"/api/offer-drafts/{d['id']}/send", json={}).status_code == 422
    sent = b.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": True}).json()
    assert sent["status"] == "sent" and sent["deal_id"] and sent["duplicate"] is False
    again = b.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": True}).json()
    assert again["duplicate"] is True and again["deal_id"] == sent["deal_id"]
    assert db.deals.count_documents({"listing_id": L, "creator_id": "cr_g08", "stage": "offer"}) == 1
    assert db.deals.find_one({"_id": sent["deal_id"]})["amount"] == 9_500
    # No second open offer, by draft or directly.
    assert _draft(b, "cr_g08").status_code == 409
    assert b.post("/api/offers", json={"creator_id": "cr_g08", "listing_id": L, "amount": 9_000}).status_code == 409
    assert b.patch(f"/api/offer-drafts/{d['id']}", json={"amount": 9_000}).status_code == 409


def test_a_draft_cant_be_sent_while_the_campaign_is_paused(login, db):
    b = login("br_senpai")
    b.client.put(f"/api/campaigns/{L}/shortlist/cr_g04", json={}, headers=b.headers)
    d = _draft(b, "cr_g04").json()
    b.post(f"/api/campaigns/{L}/status", json={"action": "pause"})
    r = b.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": True})
    assert r.status_code == 409 and "paused" in r.json()["detail"]
    assert db.offer_drafts.find_one({"_id": d["id"]})["status"] == "draft"  # still editable
    assert b.delete(f"/api/offer-drafts/{d['id']}").json()["ok"]


def test_drafts_belong_to_their_brand(client, login):
    b = login("br_senpai")
    b.client.put(f"/api/campaigns/{L}/shortlist/cr_g04", json={}, headers=b.headers)
    d = _draft(b, "cr_g04").json()
    other = login("br_thalam")
    assert other.patch(f"/api/offer-drafts/{d['id']}", json={"amount": 600}).status_code == 403
    assert other.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": True}).status_code == 403
    assert client.post(f"/api/offer-drafts/{d['id']}/send", json={"confirm": True}).status_code == 401
    assert other.post(f"/api/campaigns/{L}/offer-drafts", json={"creator_id": "cr_g04"}).status_code == 403
