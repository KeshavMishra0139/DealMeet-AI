"""Download my data: everything tied to the account, without secrets or other people's notes."""

from app.services import data_export


def test_creator_export_has_their_records_and_no_secrets(login, db):
    cr = login("cr_a")
    cid = cr.user["creator_id"]
    db.users.update_one({"_id": cr.user["id"]}, {"$set": {"password_hash": "scrypt$x$y"}})
    db.connections.insert_one({"_id": "cn_test", "user_id": cr.user["id"], "creator_id": cid, "platform": "instagram", "token_enc": "gAAAA-secret", "expires_at": 1})
    db.shortlists.insert_one({"_id": "sl_test", "creator_id": cid, "brand_id": "br_senpai", "note": "brand's private note"})
    r = cr.get("/api/auth/export")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("application/json")
    assert r.headers["content-disposition"].startswith('attachment; filename="dealmeet-data-')
    assert r.headers["cache-control"] == "no-store"
    data = r.json()
    assert data["account"]["_id"] == cr.user["id"] and data["profile"]["_id"] == cid
    assert data["account"]["password_hash"] == "[redacted]"
    assert data["records"]["connections"][0]["token_enc"] == "[redacted]"
    assert {d["creator_id"] for d in data["records"]["deals"]} == {cid}
    assert data["devices"] and any(d["current"] for d in data["devices"])
    # A brand's private notes about the creator stay with the brand.
    assert "shortlists" not in data["records"] and "brand's private note" not in r.text
    assert "gAAAA-secret" not in r.text and "scrypt$x$y" not in r.text
    assert any(e["action"] == "signin" for e in data["activity"])
    assert db.audit.find_one({"user_id": cr.user["id"], "action": "data_exported"})


def test_brand_export_has_its_campaigns_and_deals_only(login, db):
    br = login("br_senpai")
    bid = br.user["brand_id"]
    data = br.get("/api/auth/export").json()
    assert data["profile"]["_id"] == bid
    assert data["records"]["listings"] and {x["owner_id"] for x in data["records"]["listings"]} == {bid}
    assert {d["brand_id"] for d in data["records"].get("deals", [])} <= {bid}
    # Creators' saves of the brand aren't the brand's data.
    assert "wishlists" not in data["records"]


def test_scrub_keeps_ordinary_fields():
    doc = {"keywords": ["chai"], "passed": True, "hash": "contract-sha", "creator_signature": {"name": "Asha"}, "max_tokens": 5,
           "access_token": "t", "nested": [{"client_secret": "s", "code_hash": "h", "kept": 1}]}
    out = data_export.scrub(doc)
    assert out["keywords"] == ["chai"] and out["passed"] is True and out["hash"] == "contract-sha"
    assert out["creator_signature"] == {"name": "Asha"} and out["max_tokens"] == 5
    assert out["access_token"] == "[redacted]"
    assert out["nested"] == [{"client_secret": "[redacted]", "code_hash": "[redacted]", "kept": 1}]


def test_export_needs_a_session_and_is_limited(client, login, db):
    assert client.get("/api/auth/export").status_code == 401
    cr = login("cr_b")
    codes = [cr.get("/api/auth/export").status_code for _ in range(6)]
    assert codes == [200] * 5 + [429]
