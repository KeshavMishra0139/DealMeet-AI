"""Deleting an account removes the user and what is only theirs; others' data stays."""
import uuid

from conftest import Actor
from test_youtube import CHANNEL, youtube  # noqa: F401  (fixture)
from test_youtube_profile import _new_creator

from app.services import auth as au


def _brand(client) -> Actor:
    user = au.new_user("brand", "Real Brand", email=f"brand-{uuid.uuid4().hex[:8]}@example.test")
    return Actor(client, au.create_session(user["_id"], "test"), au.public_user(user))


def test_a_creator_deletes_their_account_and_everything_that_is_theirs(client, youtube, db):
    a, cid = _new_creator(client, db, channel=CHANNEL)
    a.get(f"/api/creators/{cid}/home")
    others = db.creators.count_documents({}) - 1
    assert a.post("/api/auth/delete-account", json={"confirm": "DELETE"}).json() == {"deleted": True}
    assert db.creators.find_one({"_id": cid}) is None and db.creators.count_documents({}) == others
    for name in ("posts", "metric_snapshots", "plans"):
        assert db[name].count_documents({"creator_id": cid}) == 0, name
    assert db.users.find_one({"_id": a.user["id"]}) is None
    assert a.get("/api/auth/me").status_code == 401  # signed out everywhere
    assert db.audit.find_one({"action": "account_deleted", "user_id": a.user["id"]})
    # The channel is free again for a new account.
    b, cid2 = _new_creator(client, db, channel=CHANNEL)
    assert db.creators.find_one({"_id": cid2})["channels"]["youtube"]["channel_id"] == CHANNEL


def test_a_brand_deletes_their_account(client, db):
    b = _brand(client)
    r = b.post("/api/brands", json={"name": "Real Brand Co", "category": "Food", "niches": ["food"], "ages": ["25-34"], "languages": ["ta"], "budget_monthly": 50_000})
    assert r.status_code == 200, r.text
    bid = r.json()["id"]
    assert bid and db.brands.find_one({"_id": bid})
    db.listings.insert_one({"_id": "ls_real", "owner_id": bid, "title": "Draft", "status": "draft"})
    sample_brands = db.brands.count_documents({}) - 1
    assert b.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 200
    assert db.users.find_one({"_id": b.user["id"]}) is None and db.brands.find_one({"_id": bid}) is None
    assert db.listings.count_documents({"owner_id": bid}) == 0 and db.brands.count_documents({}) == sample_brands


def test_deletion_needs_the_word_a_session_and_a_real_account(client, db, login, admin):
    a, _ = _new_creator(client, db)
    assert a.post("/api/auth/delete-account", json={"confirm": "delete"}).status_code == 422
    assert client.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 401
    assert admin.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 403
    assert login("cr_b").post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 409  # demo persona
    assert a.get("/api/auth/me").status_code == 200  # nothing happened


def test_deals_in_progress_block_deletion(client, db):
    a, cid = _new_creator(client, db)
    db.deals.insert_one({"_id": "dl_real", "creator_id": cid, "brand_id": "br_senpai", "stage": "escrow_funded", "amount": 5000})
    r = a.post("/api/auth/delete-account", json={"confirm": "DELETE"})
    assert r.status_code == 409 and "in progress" in r.json()["detail"]
    db.deals.update_one({"_id": "dl_real"}, {"$set": {"stage": "paid"}})
    assert a.post("/api/auth/delete-account", json={"confirm": "DELETE"}).status_code == 200
    assert db.deals.find_one({"_id": "dl_real"})  # the brand keeps its record of a paid deal
