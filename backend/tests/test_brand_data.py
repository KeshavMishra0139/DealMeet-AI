"""Brand data for the public directory: CSV import, YouTube stats on brand pages, email
(fake SMTP), invites to unclaimed brands, unsubscribe, and claims proved by a domain email."""
import time
from datetime import datetime, timedelta, timezone

import httpx
import pytest

from app import config
from app.services import brand_data as bd
from app.services import mailer
from app.services import youtube_public as yt

HEADER = "name,category,website,instagram,youtube,contact_email,city,source_url\n"
SRC = "https://example.org/list"


def _csv(*rows: str) -> str:
    return HEADER + "\n".join(rows) + "\n"


def _text(msg) -> str:
    return msg.get_content()


# ------------------------------------------------------------------ import
def test_only_admins_import(login, admin, db):
    assert login("br_senpai").post("/api/admin/brands/import", json={"csv": _csv(), "dry_run": True}).status_code == 403
    r = admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,https://kumkumtea.in,@kumkumtea,,,Pune,{SRC}"), "dry_run": False})
    assert r.status_code == 422 and "reason" in r.json()["detail"]


def test_dry_run_checks_every_row_and_saves_nothing(admin, db):
    before = db.brands.count_documents({})
    text = _csv(
        f"Kumkum Tea,Beverages,https://www.kumkumtea.in,@kumkumtea,@KumkumTeaIN,partners@kumkumtea.in,Pune,{SRC}",
        f"No Source,Beverages,,,,,,",
        f"Bad Mail,Snacks,https://badmail.in,,,founder@gmail.com,,{SRC}",
        f"Other Domain,Snacks,https://otherdomain.in,,,hello@elsewhere.in,,{SRC}",
        f"Shared Host,Fashion,https://shop.myshopify.com,,,,,{SRC}",
        f"Kumkum Again,Beverages,https://kumkumtea.in,,,,,{SRC}",
    )
    r = admin.post("/api/admin/brands/import", json={"csv": text, "dry_run": True})
    assert r.status_code == 200, r.text
    rows = r.json()["rows"]
    assert [x["status"] for x in rows] == ["ready", "error", "error", "error", "error", "duplicate"]
    assert "source_url is required" in rows[1]["detail"]
    assert "own website domain" in rows[2]["detail"] and "own website domain" in rows[3]["detail"]
    assert "shared host" in rows[4]["detail"]
    assert "row 2" in rows[5]["detail"]
    assert db.brands.count_documents({}) == before


def test_import_adds_unclaimed_brands_with_public_facts_only(client, admin, db):
    text = _csv(f"Kumkum Tea,Beverages,https://www.kumkumtea.in,@kumkumtea,,partners@kumkumtea.in,Pune,{SRC}")
    r = admin.post("/api/admin/brands/import", json={"csv": text, "dry_run": False, "reason": "First batch of Pune brands"})
    assert r.json()["counts"] == {"added": 1}
    b = db.brands.find_one({"name": "Kumkum Tea"})
    assert b["claimed"] is False and b["website_host"] == "kumkumtea.in" and b["contact_email"] == "partners@kumkumtea.in"
    assert b["source"] == "import" and b["source_url"] == SRC
    assert db.audit.find_one({"action": "brands_imported", "import_id": r.json()["import_id"]})["added"] == 1
    page = client.get(f"/api/directory/brands/{b['slug']}").json()
    assert page["claimed"] is False and page["public_handles"] == {"instagram": "@kumkumtea"}
    # Unclaimed pages show public basics only: the rest is kept for checks and invites.
    for kept in ("partners@kumkumtea.in", SRC, "kumkumtea.in/", "Pune"):
        assert kept not in str(page)
    # Importing the same file again lists nothing twice.
    again = admin.post("/api/admin/brands/import", json={"csv": text, "dry_run": False, "reason": "Re-run of the batch"})
    assert again.json()["counts"] == {"duplicate": 1}


def test_duplicates_are_found_by_name_website_or_handle_and_removed_brands_stay_off(admin, db):
    admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,https://kumkumtea.in,@kumkumtea,,,,{SRC}"), "dry_run": False, "reason": "Seed one brand"})
    rows = admin.post("/api/admin/brands/import", json={"csv": _csv(
        f"KUMKUM TEA,Beverages,,,,,,{SRC}",
        f"Kumkum Chai,Beverages,https://www.kumkumtea.in/shop,,,,,{SRC}",
        f"Kumkum Brew,Beverages,,@KumkumTea,,,,{SRC}",
    ), "dry_run": True}).json()["rows"]
    assert [x["status"] for x in rows] == ["duplicate", "duplicate", "duplicate"]
    db.brands.update_one({"name": "Kumkum Tea"}, {"$set": {"removed": True}})
    rows = admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,,,,,,{SRC}"), "dry_run": True}).json()["rows"]
    assert rows[0]["status"] == "removed"


def test_file_shape_is_checked(admin, db):
    assert admin.post("/api/admin/brands/import", json={"csv": "name,category\nX Brand,Food\n", "dry_run": True}).status_code == 422
    big = _csv(*[f"Brand {i},Food,,,,,,{SRC}" for i in range(bd.MAX_ROWS + 1)])
    r = admin.post("/api/admin/brands/import", json={"csv": big, "dry_run": True})
    assert r.status_code in (413, 422)


# ------------------------------------------------------------------ YouTube stats
class FakeYT:
    def __init__(self):
        self.calls = 0

    def get(self, url, params=None, timeout=None):
        self.calls += 1
        item = {"id": "UC" + "b" * 22, "snippet": {"title": "Kumkum Tea"}, "statistics": {"subscriberCount": "48200", "viewCount": "9100000", "videoCount": "312"}}
        return httpx.Response(200, json={"items": [item]}, request=httpx.Request("GET", url))


def test_brand_pages_show_official_youtube_numbers_within_30_days(client, admin, db, monkeypatch):
    admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,,,@KumkumTeaIN,,,{SRC}"), "dry_run": False, "reason": "Brand with a channel"})
    slug = db.brands.find_one({"name": "Kumkum Tea"})["slug"]
    assert client.get(f"/api/directory/brands/{slug}").json()["youtube"] is None  # no key on the server
    monkeypatch.setenv("YOUTUBE_API_KEY", "k")
    config.get_settings.cache_clear()
    db.yt_cache.delete_many({})
    fake = FakeYT()
    monkeypatch.setattr(yt.httpx, "get", fake.get)
    y = client.get(f"/api/directory/brands/{slug}").json()["youtube"]
    assert y["subscribers"] == 48_200 and y["video_count"] == 312 and y["source"] == "youtube_api"
    client.get(f"/api/directory/brands/{slug}")
    assert fake.calls == 1  # fresh: not fetched again
    # Older than 30 days and YouTube can't be reached: the numbers aren't shown.
    old = (datetime.now(timezone.utc) - timedelta(days=31)).isoformat()
    db.brands.update_one({"slug": slug}, {"$set": {"channels.youtube.fetched_at": old}})
    monkeypatch.delenv("YOUTUBE_API_KEY")
    config.get_settings.cache_clear()
    assert client.get(f"/api/directory/brands/{slug}").json()["youtube"] is None


# ------------------------------------------------------------------ email and invites
def _saved_by_connected(db, brand_id: str, n: int):
    for i in range(n):
        cid = f"cr_conn_{i}"
        db.connections.insert_one({"_id": f"cn_{cid}", "creator_id": cid, "user_id": f"us_{cid}", "platform": "instagram", "status": "connected"})
        db.wishlists.insert_one({"_id": f"wl_{cid}_{brand_id}", "creator_id": cid, "brand_id": brand_id, "show_name": False})


def _invitable(admin, db) -> dict:
    admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,https://kumkumtea.in,,,partners@kumkumtea.in,,{SRC}"), "dry_run": False, "reason": "Brand to invite"})
    b = db.brands.find_one({"name": "Kumkum Tea"})
    _saved_by_connected(db, b["_id"], 4)
    return b


def test_invites_need_email_set_up(admin, db):
    b = _invitable(admin, db)
    assert admin.get("/api/admin/brand-invites").json()["email"] is False
    r = admin.post(f"/api/admin/brand-invites/{b['_id']}", json={"reason": "Creators keep saving it"})
    assert r.status_code == 503 and "isn't set up" in r.json()["detail"]


def test_an_invite_says_who_is_interested_with_claim_and_unsubscribe_links(client, admin, db, smtp):
    b = _invitable(admin, db)
    items = admin.get("/api/admin/brand-invites").json()["items"]
    row = next(x for x in items if x["id"] == b["_id"])
    assert row["saves"] == 4 and row["blocked"] is None
    r = admin.post(f"/api/admin/brand-invites/{b['_id']}", json={"reason": "Creators keep saving it"})
    assert r.status_code == 200, r.text
    msg = smtp.sent[-1]
    assert msg["To"] == "partners@kumkumtea.in" and "4 creators" in msg["Subject"]
    body = _text(msg)
    assert f"https://dealmeet.test/brands/{b['slug']}" in body and "not affiliated" in body
    assert msg["List-Unsubscribe"].startswith("<https://dealmeet.test/api/email/unsubscribe?t=")
    assert db.audit.find_one({"action": "brand_invited", "brand_id": b["_id"]})
    # Once a month at most.
    again = admin.post(f"/api/admin/brand-invites/{b['_id']}", json={"reason": "Trying again too soon"})
    assert again.status_code == 409 and "30 days" in again.json()["detail"]


def test_unsubscribe_asks_first_then_stops_every_invite(client, admin, db, smtp):
    b = _invitable(admin, db)
    token = mailer.unsubscribe_token("partners@kumkumtea.in")
    page = client.get(f"/api/email/unsubscribe?t={token}")
    assert page.status_code == 200 and "Stop these emails" in page.text
    assert not mailer.opted_out("partners@kumkumtea.in")  # opening the link alone changes nothing
    # A plain form post, as the page's button and mail apps' one-click send it (no app header).
    r = client.post("/api/email/unsubscribe", data={"t": token}, headers={"X-Requested-With": ""})
    assert r.status_code == 200 and "unsubscribed" in r.text
    assert mailer.opted_out("partners@kumkumtea.in")
    assert client.post("/api/email/unsubscribe", data={"t": token[:-2] + "00"}).status_code == 400
    blocked = admin.post(f"/api/admin/brand-invites/{b['_id']}", json={"reason": "Creators keep saving it"})
    assert blocked.status_code == 409 and "asked not to" in blocked.json()["detail"]


# ------------------------------------------------------------------ claim by domain email
def _claimable(admin, db, website="https://kumkumtea.in") -> dict:
    admin.post("/api/admin/brands/import", json={"csv": _csv(f"Kumkum Tea,Beverages,{website},,,,,{SRC}"), "dry_run": False, "reason": "Brand to claim"})
    return db.brands.find_one({"name": "Kumkum Tea"})


def _code(smtp) -> str:
    import re

    return re.search(r"\b(\d{6})\b", _text(smtp.sent[-1])).group(1)


def test_a_brand_claims_its_page_with_an_email_at_its_own_domain(admin, login, db, smtp):
    b = _claimable(admin, db)
    me = login("new_brand")
    page = me.get(f"/api/directory/brands/{b['slug']}").json()
    assert page["viewer"]["verify_domain"] == "kumkumtea.in"
    for bad in ("me@gmail.com", "me@kumkumtea.in.evil.com", "me@notkumkumtea.in"):
        r = me.post(f"/api/directory/brands/{b['slug']}/claim/code", json={"email": bad})
        assert r.status_code == 422 and "kumkumtea.in" in r.json()["detail"], bad
    r = me.post(f"/api/directory/brands/{b['slug']}/claim/code", json={"email": "Asha@KumkumTea.in"})
    assert r.status_code == 200 and r.json()["to"].endswith("@kumkumtea.in")
    assert db.claim_codes.find_one({})["code_hash"] != _code(smtp)  # only a hash is kept
    assert me.post(f"/api/directory/brands/{b['slug']}/claim/verify", json={"code": "000000" if _code(smtp) != "000000" else "111111"}).status_code == 400
    r = me.post(f"/api/directory/brands/{b['slug']}/claim/verify", json={"code": _code(smtp)})
    assert r.status_code == 200, r.text
    after = db.brands.find_one({"_id": b["_id"]})
    assert after["claimed"] is True and after["verification"]["domain"] == "kumkumtea.in"
    assert db.users.find_one({"_id": me.user["id"]})["brand_id"] == b["_id"]
    assert db.claim_requests.find_one({"brand_id": b["_id"]})["decided_by"] == "domain_email"


def test_claim_codes_expire_and_lock_after_five_wrong_tries(admin, login, db, smtp):
    b = _claimable(admin, db)
    me = login("new_brand")
    me.post(f"/api/directory/brands/{b['slug']}/claim/code", json={"email": "asha@kumkumtea.in"})
    right = _code(smtp)
    wrong = "000000" if right != "000000" else "111111"
    for _ in range(5):
        assert me.post(f"/api/directory/brands/{b['slug']}/claim/verify", json={"code": wrong}).status_code == 400
    assert me.post(f"/api/directory/brands/{b['slug']}/claim/verify", json={"code": right}).status_code == 429
    me.post(f"/api/directory/brands/{b['slug']}/claim/code", json={"email": "asha@kumkumtea.in"})
    db.claim_codes.update_many({}, {"$set": {"expires": time.time() - 1}})
    r = me.post(f"/api/directory/brands/{b['slug']}/claim/verify", json={"code": _code(smtp)})
    assert r.status_code == 400 and "expired" in r.json()["detail"]
    assert db.brands.find_one({"_id": b["_id"]})["claimed"] is False


def test_no_domain_check_without_a_website_of_its_own(admin, login, db, smtp):
    b = _claimable(admin, db, website="")
    me = login("new_brand")
    assert me.get(f"/api/directory/brands/{b['slug']}").json()["viewer"]["verify_domain"] is None
    r = me.post(f"/api/directory/brands/{b['slug']}/claim/code", json={"email": "asha@kumkumtea.in"})
    assert r.status_code == 409 and "admin checks it" in r.json()["detail"]


def test_shared_and_free_domains_never_count(db):
    assert not bd.email_matches_site("a@gmail.com", "gmail.com")
    assert not bd.email_matches_site("a@brand.myshopify.com", "brand.myshopify.com")
    assert bd.email_matches_site("a@in.brand.com", "brand.com")
    assert not bd.email_matches_site("a@brand.com", "shop.brand.com")
