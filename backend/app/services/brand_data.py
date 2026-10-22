"""Brand data for the public directory: bulk import, YouTube stats and invitations.

Brands that aren't on DealMeet AI are listed from public facts only, the same rule as
one-by-one admin listing (services/directory.add_unclaimed). Their page still shows only
name, category and official handles (plus the official channel's YouTube numbers); the
website, city, contact address and the link the facts came from are kept for duplicate
checks, claim verification and invites, never shown. No logos, nothing scraped.

- Import (admins): a CSV checked row by row before anything is saved, duplicates skipped
  against the directory (website, handles, name) and within the file, and a brand that
  was removed at its own request is never listed again. A contact email is kept private
  and only accepted on the brand's own website domain, so no personal inbox is collected.
- YouTube: a brand's official channel numbers through the YouTube Data API (public data,
  API key), refreshed when its page is viewed and a week old, and never shown once older
  than 30 days (YouTube's API policies limit how long such data may be kept unrefreshed).
- Invites (admins, one at a time, with a reason): when creators with connected accounts
  have saved an unclaimed brand, its public contact address can be told so, with a claim
  link and an unsubscribe link. At most one invite per brand every 30 days, never to an
  address that opted out.
"""
from __future__ import annotations

import csv
import io
import re
import time
import uuid
from datetime import datetime, timezone
from urllib.parse import urlparse

from fastapi import HTTPException

from ..config import get_settings, now_iso
from ..db import get_db
from . import auth as au
from . import mailer
from . import youtube_public as yt
from .brand_profile import clean_website, unique_slug

MAX_ROWS = 500
COLUMNS = ["name", "category", "website", "instagram", "youtube", "contact_email", "city", "source_url"]
REQUIRED = ("name", "category", "source_url")
HANDLE = re.compile(r"^@?[A-Za-z0-9._-]{2,40}$")
EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

# Addresses anyone can sign up for: never proof of working at a brand.
FREE_MAIL = {
    "gmail.com", "googlemail.com", "yahoo.com", "yahoo.co.in", "yahoo.in", "outlook.com", "hotmail.com", "live.com",
    "msn.com", "icloud.com", "me.com", "aol.com", "proton.me", "protonmail.com", "rediffmail.com", "zoho.com",
    "zohomail.in", "yandex.com", "mail.com", "gmx.com",
}
# Sites many brands share a host on: a page there says nothing about who owns an address.
SHARED_HOSTS = {
    "instagram.com", "facebook.com", "fb.com", "youtube.com", "linktr.ee", "wa.me", "whatsapp.com", "linkedin.com",
    "x.com", "twitter.com", "amazon.in", "amazon.com", "flipkart.com", "myntra.com", "meesho.com", "nykaa.com",
    "myshopify.com", "shopify.com", "wixsite.com", "wordpress.com", "blogspot.com", "sites.google.com", "google.com",
    "bit.ly", "notion.site", "carrd.co", "github.io", "vercel.app", "netlify.app", "onrender.com",
}
INVITE_EVERY_DAYS = 30
INVITE_MIN_SAVES = 3
YT_REFRESH_DAYS = 7
YT_MAX_AGE_DAYS = 30


# ------------------------------------------------------------------ domains
def site_host(website: str | None) -> str | None:
    """The website's host without "www.", lower case."""
    if not website:
        return None
    host = (urlparse(website).hostname or "").lower().strip(".")
    return host[4:] if host.startswith("www.") else host or None


def shared(host: str | None) -> bool:
    return bool(host) and any(host == h or host.endswith("." + h) for h in SHARED_HOSTS)


def email_matches_site(email: str, host: str | None) -> bool:
    """An address at the brand's own website domain (or a subdomain of it). Never a free
    mail provider or a shared host."""
    d = mailer.domain_of(email)
    if not host or not d or d in FREE_MAIL or shared(d) or shared(host):
        return False
    return d == host or d.endswith("." + host)


# ------------------------------------------------------------------ import
def _clean(row: dict) -> tuple[dict, list[str]]:
    errors: list[str] = []
    out: dict = {}
    for k in COLUMNS:
        out[k] = (row.get(k) or "").strip()
    for k in REQUIRED:
        if not out[k]:
            errors.append(f"{k} is required")
    if out["name"] and not 2 <= len(out["name"]) <= 60:
        errors.append("name must be 2 to 60 characters")
    if out["category"] and not 2 <= len(out["category"]) <= 60:
        errors.append("category must be 2 to 60 characters")
    if len(out["city"]) > 60:
        errors.append("city must be 60 characters or fewer")
    for k in ("website", "source_url"):
        if out[k]:
            try:
                out[k] = clean_website(out[k])
            except ValueError:
                errors.append(f"{k} must be a full address starting with https://")
    for k in ("instagram", "youtube"):
        if out[k]:
            if not HANDLE.match(out[k]):
                errors.append(f"{k} must be a public handle like @brandname")
            else:
                out[k] = out[k] if out[k].startswith("@") else f"@{out[k]}"
    host = site_host(out["website"]) if out["website"] and not any(e.startswith("website") for e in errors) else None
    if out["website"] and host and shared(host):
        errors.append(f"website is on a shared host ({host}); use the brand's own site, or leave it empty")
    if out["contact_email"]:
        if not EMAIL.match(out["contact_email"]):
            errors.append("contact_email isn't an email address")
        elif not email_matches_site(out["contact_email"], host):
            errors.append("contact_email must be at the brand's own website domain (a public address like partnerships@brand.com)")
        else:
            out["contact_email"] = mailer.normalise(out["contact_email"])
    out["website_host"] = host
    return out, errors


def _existing_keys(rows: list[dict]) -> dict[str, dict]:
    """Directory brands (removed ones included) that share a name, website or handle with the rows."""
    names = [r["name"] for r in rows if r["name"]]
    hosts = [r["website_host"] for r in rows if r.get("website_host")]
    handles = {k: [r[k] for r in rows if r[k]] for k in ("instagram", "youtube")}
    ors: list[dict] = [{"name": {"$regex": f"^{re.escape(n)}$", "$options": "i"}} for n in names[:MAX_ROWS]]
    if hosts:
        ors.append({"website_host": {"$in": hosts}})
    for k, vals in handles.items():
        if vals:
            ors.append({f"public_handles.{k}": {"$in": [re.compile(f"^{re.escape(v)}$", re.I) for v in vals]}})
    keys: dict[str, dict] = {}
    if not ors:
        return keys
    for b in get_db().brands.find({"$or": ors}, {"name": 1, "slug": 1, "website": 1, "website_host": 1, "public_handles": 1, "removed": 1}):
        info = {"id": b["_id"], "name": b["name"], "slug": b.get("slug"), "removed": bool(b.get("removed"))}
        keys[f"name:{b['name'].lower()}"] = info
        host = b.get("website_host") or site_host(b.get("website"))
        if host:
            keys[f"host:{host}"] = info
        for k, v in (b.get("public_handles") or {}).items():
            if v:
                keys[f"{k}:{v.lower()}"] = info
    return keys


def _keys_of(r: dict) -> list[str]:
    keys = [f"name:{r['name'].lower()}"]
    if r.get("website_host"):
        keys.append(f"host:{r['website_host']}")
    keys += [f"{k}:{r[k].lower()}" for k in ("instagram", "youtube") if r[k]]
    return keys


def parse(text: str) -> list[dict]:
    """CSV text with a header row -> rows keyed by lower-case column names."""
    text = (text or "").lstrip("﻿")
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(422, "The file is empty. The first row must name the columns.")
    fields = [(f or "").strip().lower() for f in reader.fieldnames]
    missing = [c for c in REQUIRED if c not in fields]
    if missing:
        raise HTTPException(422, f"Missing column{'s' if len(missing) > 1 else ''}: {', '.join(missing)}. Columns: {', '.join(COLUMNS)}.")
    rows = []
    for raw in reader:
        rows.append({(k or "").strip().lower(): (v if isinstance(v, str) else "") for k, v in raw.items()})
        if len(rows) > MAX_ROWS:
            raise HTTPException(422, f"At most {MAX_ROWS} rows per import. Split the file.")
    if not rows:
        raise HTTPException(422, "No rows under the header.")
    return rows


def run_import(text: str, admin: dict, reason: str, dry_run: bool) -> dict:
    """Checks every row; unless dry_run, adds the ones that are ready. Nothing is added
    for a row with any problem."""
    raw = parse(text)
    checked = [_clean(r) for r in raw]
    existing = _existing_keys([r for r, _ in checked])
    seen: dict[str, int] = {}
    results = []
    for i, (r, errors) in enumerate(checked, start=2):  # row 1 is the header
        res = {"row": i, "name": r["name"] or None}
        if errors:
            results.append({**res, "status": "error", "detail": "; ".join(errors)})
            continue
        clash = next((existing[k] for k in _keys_of(r) if k in existing), None)
        twin = next((seen[k] for k in _keys_of(r) if k in seen), None)
        if clash and clash["removed"]:
            results.append({**res, "status": "removed", "detail": f"{clash['name']} was taken off the directory at the brand's request; it isn't listed again."})
        elif clash:
            results.append({**res, "status": "duplicate", "detail": f"{clash['name']} is in the directory already.", "slug": clash["slug"]})
        elif twin:
            results.append({**res, "status": "duplicate", "detail": f"Same brand as row {twin} of this file."})
        else:
            for k in _keys_of(r):
                seen[k] = i
            results.append({**res, "status": "ready", "_row": r})
    ready = [x for x in results if x["status"] == "ready"]
    import_id = f"imp_{uuid.uuid4().hex[:10]}"
    if not dry_run and ready:
        db = get_db()
        taken: set[str] = set()
        docs = []
        for x in ready:
            r = x["_row"]
            slug = unique_slug(r["name"], taken)
            taken.add(slug)
            doc = {
                "_id": f"br_unc_{uuid.uuid4().hex[:8]}",
                "kind": "brand",
                "name": r["name"],
                "slug": slug,
                "category": r["category"],
                "website": r["website"] or None,
                "website_host": r["website_host"],
                "city": r["city"] or None,
                "public_handles": {k: r[k] for k in ("instagram", "youtube") if r[k]},
                "contact_email": r["contact_email"] or None,  # private: admins and invites only
                "source_url": r["source_url"],
                "claimed": False,
                "verified": False,
                "source": "import",
                "import_id": import_id,
                "added_by": admin["_id"],
                "added_reason": reason,
                "created_at": now_iso(),
            }
            docs.append(doc)
            x["status"], x["slug"] = "added", slug
        db.brands.insert_many(docs)
        au.audit("brands_imported", admin["_id"], "admin", import_id=import_id, added=len(docs), rows=len(results), reason=reason)
    for x in results:
        x.pop("_row", None)
    counts: dict[str, int] = {}
    for x in results:
        counts[x["status"]] = counts.get(x["status"], 0) + 1
    return {"dry_run": dry_run, "import_id": None if dry_run or not ready else import_id, "counts": counts, "rows": results}


# ------------------------------------------------------------------ YouTube stats
def _age_days(iso: str | None) -> float:
    if not iso:
        return 1e9
    try:
        t = datetime.fromisoformat(iso)
    except ValueError:
        return 1e9
    if t.tzinfo is None:
        t = t.replace(tzinfo=timezone.utc)
    return (datetime.now(timezone.utc) - t).total_seconds() / 86400


def youtube_for_page(b: dict) -> dict | None:
    """The brand's YouTube numbers for its page: refreshed when a week old (if the server
    has a YouTube key), and None once older than 30 days or when there's no channel."""
    handle = (b.get("public_handles") or {}).get("youtube")
    stats = (b.get("channels") or {}).get("youtube")
    if not handle:
        return None
    if yt.configured() and _age_days((stats or {}).get("fetched_at")) > YT_REFRESH_DAYS:
        try:
            stats = refresh_youtube(b["_id"], handle)
        except HTTPException:
            pass  # quota or network: keep what's stored while it's still allowed
    if not stats or _age_days(stats.get("fetched_at")) > YT_MAX_AGE_DAYS:
        return None
    return stats


def refresh_youtube(brand_id: str, handle: str) -> dict | None:
    data, fetched = yt._call("channels", {"part": "snippet,statistics", **yt.parse_query(handle)})
    items = data.get("items") or []
    db = get_db()
    if not items:
        db.brands.update_one({"_id": brand_id}, {"$unset": {"channels.youtube": ""}})
        return None
    ch, st = items[0], items[0].get("statistics") or {}
    hidden = bool(st.get("hiddenSubscriberCount"))
    stats = {
        "channel_id": ch["id"],
        "title": (ch.get("snippet") or {}).get("title"),
        "handle": handle,
        "subscribers": None if hidden else int(st.get("subscriberCount", 0)),
        "total_views": int(st.get("viewCount", 0)),
        "video_count": int(st.get("videoCount", 0)),
        "source": yt.SOURCE,
        "fetched_at": datetime.fromtimestamp(fetched, tz=timezone.utc).isoformat(timespec="seconds"),
    }
    db.brands.update_one({"_id": brand_id}, {"$set": {"channels.youtube": stats}})
    return stats


# ------------------------------------------------------------------ invites
def _saves_by_brand() -> dict[str, int]:
    """Dream Brand saves by creators with a connected account, per brand."""
    from .directory import _connected_creators

    connected = _connected_creators()
    counts: dict[str, int] = {}
    for s in get_db().wishlists.find({}, {"brand_id": 1, "creator_id": 1}):
        if s["creator_id"] in connected:
            counts[s["brand_id"]] = counts.get(s["brand_id"], 0) + 1
    return counts


def _invite_block(b: dict) -> str | None:
    """Why this brand can't be invited now, or None."""
    if b.get("claimed", True) or b.get("removed"):
        return "This page is managed by its brand or was removed."
    if not b.get("contact_email"):
        return "There's no public contact address for this brand."
    if mailer.opted_out(b["contact_email"]):
        return "This address asked not to get these emails."
    last = (b.get("invite") or {}).get("at")
    if last and _age_days(last) < INVITE_EVERY_DAYS:
        return f"Invited less than {INVITE_EVERY_DAYS} days ago."
    return None


def invite_candidates(min_saves: int = INVITE_MIN_SAVES) -> dict:
    counts = _saves_by_brand()
    ids = [bid for bid, n in counts.items() if n >= min_saves]
    items = []
    for b in get_db().brands.find({"_id": {"$in": ids}, "claimed": False, "removed": {"$ne": True}}):
        items.append({
            "id": b["_id"],
            "name": b["name"],
            "slug": b.get("slug"),
            "saves": counts[b["_id"]],
            "contact_email": b.get("contact_email"),
            "last_invite": (b.get("invite") or {}).get("at"),
            "blocked": _invite_block(b),
        })
    items.sort(key=lambda x: (x["blocked"] is not None, -x["saves"]))
    return {"items": items, "min_saves": min_saves, "email": mailer.configured()}


def send_invite(brand_id: str, admin: dict, reason: str, base_url: str) -> dict:
    db = get_db()
    b = db.brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    block = _invite_block(b)
    if block:
        raise HTTPException(409, block)
    saves = _saves_by_brand().get(brand_id, 0)
    if saves < 1:
        raise HTTPException(409, "No creators with connected accounts have saved this brand yet.")
    base = (get_settings().frontend_url or base_url).rstrip("/")
    page = f"{base}/brands/{b['slug']}"
    unsub = f"{base}/api/email/unsubscribe?t={mailer.unsubscribe_token(b['contact_email'])}"
    who = "1 creator" if saves == 1 else f"{saves} creators"
    text = (
        f"Hello {b['name']} team,\n\n"
        f"{who} on DealMeet AI with a connected Instagram or YouTube account saved {b['name']} as a brand they'd like to work with.\n\n"
        f"DealMeet AI lists {b['name']} from public information only, and the page says you aren't on DealMeet AI and not affiliated with us. "
        f"If you claim it, you can add your details, see who's interested and post campaigns:\n{page}\n\n"
        f"Not for you? Ask us to take the page down from that link, or stop these emails:\n{unsub}\n\n"
        "DealMeet AI\n"
    )
    out = mailer.send(b["contact_email"], f"{who} on DealMeet AI want to work with {b['name']}", text, kind="invite", unsubscribe_url=unsub)
    db.brands.update_one({"_id": brand_id}, {"$set": {"invite": {"at": now_iso(), "by": admin["_id"], "saves": saves, "email_id": out["id"]}}, "$inc": {"invite_count": 1}})
    au.audit("brand_invited", admin["_id"], "admin", brand_id=brand_id, saves=saves, reason=reason)
    return {"status": "sent", "saves": saves, "to": b["contact_email"], "at": time.time()}


def domain_claim_host(b: dict) -> str | None:
    """The domain a claimer can prove an email at, or None when the page has no usable website."""
    host = b.get("website_host") or site_host(b.get("website"))
    return None if not host or shared(host) else host

