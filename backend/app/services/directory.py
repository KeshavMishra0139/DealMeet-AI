"""The brand directory, brand pages, unclaimed brands, claims, removal requests and
creators' Dream Brands.

Search uses Atlas Search ($search) when the app runs on MongoDB Atlas with an index
configured, and keyword matching otherwise (mongomock has no $search): the search's words
against each brand's name, category, the creators it hires, where it sells and its
description. Nothing is listed until someone searches or picks a filter. Signed-out
visitors see the first few brands; the rest is for members. Unclaimed brands are added by admins only, show just their public name,
category and public handles, and say plainly that they aren't on DealMeet AI.
"""
from __future__ import annotations

import logging
import re
import uuid

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator
from pymongo.errors import OperationFailure

from ..config import get_settings, now_iso
from ..db import db_mode, get_db
from ..seed.catalog import LANGS, NICHES
from . import auth as au
from . import fan_proof
from . import public_search as ps
from .brand_profile import unique_slug

log = logging.getLogger("jodidar.directory")

UNCLAIMED_NOTE = "Not on DealMeet AI and not affiliated with us."
# Spam examples, guest bookings and removed pages never appear.
VISIBLE = {"_id": {"$not": {"$regex": "^xx_"}}, "guest": {"$ne": True}, "removed": {"$ne": True}}
PAGE_SIZE = 24
VISITOR_LIMIT = 9
MAX_DREAM = 100
HANDLE = re.compile(r"^@?[A-Za-z0-9._-]{2,40}$")


# ------------------------------------------------------------------ search
def _live_counts(brand_ids: list[str] | None = None) -> dict[str, int]:
    q: dict = {"status": {"$in": ["live", "open"]}, "type": {"$in": ["brand_campaign", "collective", "pr_service", "page"]}}
    if brand_ids is not None:
        q["owner_id"] = {"$in": brand_ids}
    counts: dict[str, int] = {}
    for x in get_db().listings.find(q, {"owner_id": 1}):
        counts[x["owner_id"]] = counts.get(x["owner_id"], 0) + 1
    return counts


def card(b: dict, live: int = 0) -> dict:
    claimed = b.get("claimed", True)
    base = {
        "id": b["_id"],
        "slug": b.get("slug"),
        "name": b["name"],
        "category": b.get("category"),
        "kind": b.get("kind", "brand"),
        "claimed": claimed,
        "source": b.get("source"),
    }
    if not claimed:
        return {**base, "public_handles": b.get("public_handles") or {}, "note": UNCLAIMED_NOTE, "open_campaigns": 0}
    t = b.get("target") or {}
    return {
        **base,
        "hue": b.get("hue", 260),
        "verified": bool(b.get("verified")),
        "languages": [LANGS[x]["label"] for x in t.get("languages") or [] if x in LANGS],
        "cities": (t.get("cities") or [])[:3],
        "open_campaigns": live,
    }


def _atlas_ids(q: str, limit: int) -> list[str]:
    """Brand ids ranked by Atlas Search. Raises OperationFailure when the index is missing."""
    pipeline = [
        {
            "$search": {
                "index": get_settings().atlas_search_index,
                "compound": {
                    "should": [
                        {"autocomplete": {"query": q, "path": "name", "fuzzy": {"maxEdits": 1}}},
                        {"text": {"query": q, "path": ["name", "category", "description"], "fuzzy": {"maxEdits": 1}}},
                    ],
                    "minimumShouldMatch": 1,
                },
            }
        },
        {"$limit": limit},
        {"$project": {"_id": 1}},
    ]
    return [d["_id"] for d in get_db().brands.aggregate(pipeline)]


def search(q: str = "", category: str | None = None, city: str | None = None, language: str | None = None, open_only: bool = False, page: int = 1, signed_in: bool = True) -> dict:
    db = get_db()
    if not q.strip() and not (category or city or language or open_only):
        # Like a search engine: no brand is listed until someone searches or picks a filter.
        return {"items": [], "total": 0, "page": 1, "page_size": 0, "search": "all", "note": None, "locked": False, "niche_hint": None, "idle": True}
    filters: list[dict] = [VISIBLE]
    if category:
        filters.append({"category": {"$regex": f"^{re.escape(category)}$", "$options": "i"}})
    if city:
        filters.append({"target.cities": city})
    if language:
        filters.append({"target.languages": language})
    live = _live_counts()
    if open_only:
        filters.append({"_id": {"$in": [k for k, v in live.items() if v]}})
    q = q.strip()
    mode, note, order = "all", None, None
    if q:
        settings = get_settings()
        if db_mode() == "atlas" and settings.atlas_search_index:
            try:
                order = _atlas_ids(q, 200)
                filters.append({"_id": {"$in": order}})
                mode = "atlas"
            except OperationFailure as e:
                log.warning("Atlas Search failed (%s); using regex search", e.code)
                note = f"Atlas Search index '{settings.atlas_search_index}' isn't available, so this is a simpler text match."
        if mode != "atlas":
            mode = "regex"  # keyword matching (the name is kept for the web app)
    query = {"$and": filters}
    docs = list(db.brands.find(query))
    matched: dict[str, list[str]] = {}
    if order:
        rank = {bid: i for i, bid in enumerate(order)}
        docs.sort(key=lambda b: rank.get(b["_id"], 1_000))
    elif q:
        scored = [(s, b) for b in docs for s in [_keyword_score(b, q, matched)] if s > 0]
        scored.sort(key=lambda x: (-x[0], not x[1].get("claimed", True), x[1]["name"].lower()))
        docs = [b for _, b in scored]
    else:
        docs.sort(key=lambda b: (not b.get("claimed", True), -live.get(b["_id"], 0), b["name"].lower()))
    total = len(docs)
    # Visitors see the first few; the rest of the directory is for members.
    size = PAGE_SIZE if signed_in else VISITOR_LIMIT
    page = max(page, 1) if signed_in else 1
    start = (page - 1) * size
    items = [{**card(b, live.get(b["_id"], 0)), "matched": matched.get(b["_id"], [])[:3]} for b in docs[start : start + size]]
    hint = None
    pointed = ps.niches_for(ps.query_words(q)) if q else []
    if pointed:
        hint = {"id": pointed[0], "label": NICHES[pointed[0]]["label"]}
    return {"items": items, "total": total, "page": page, "page_size": size, "search": mode, "note": note,
            "locked": not signed_in and total > size, "niche_hint": hint, "idle": False}


def _keyword_score(b: dict, q: str, matched: dict[str, list[str]]) -> int:
    """How well a brand fits the search words: its name, its category, the kind of creators
    it hires (so "dosa" finds brands that hire food creators), where it sells, then its
    description. Records what matched, for the card."""
    qw, phrase = ps.query_words(q), q.lower()
    t = b.get("target") or {}
    name, cat, desc = set(ps.words(b.get("name"))), set(ps.words(b.get("category"))), set(ps.words(b.get("description")))
    places = [*(t.get("cities") or []), *(t.get("regions") or [])]
    langs = [LANGS[x]["label"] for x in t.get("languages") or [] if x in LANGS]
    score, hits = (4 if phrase in b["name"].lower() else 0), []
    for w in qw:
        if ps._hit(w, name):
            score += 6
        elif ps._hit(w, cat):
            score += 5
            hits.append(b.get("category"))
        elif hire := next((n for n in b.get("niches") or [] if n in NICHES and ps._hit(w, ps.NICHE_BAGS[n])), None):
            score += 4
            hits.append(f"Works with {NICHES[hire]['label'].lower()} creators")
        elif place := next((x for x in places + langs if ps._hit(w, set(ps.words(x)))), None):
            score += 2
            hits.append(place)
        elif ps._hit(w, desc):
            score += 2
            hits.append("their description")
    matched[b["_id"]] = list(dict.fromkeys(h for h in hits if h))
    return score


def facets() -> dict:
    db = get_db()
    # Categories busiest first, so a picker can show the few that matter most.
    counts: dict[str, int] = {}
    for b in db.brands.find(VISIBLE, {"category": 1}):
        if b.get("category"):
            counts[b["category"]] = counts.get(b["category"], 0) + 1
    cats = sorted(counts, key=lambda c: (-counts[c], c.lower()))
    cities = sorted({c for b in db.brands.find(VISIBLE, {"target.cities": 1}) for c in (b.get("target") or {}).get("cities") or []})
    langs = sorted({lang for b in db.brands.find(VISIBLE, {"target.languages": 1}) for lang in (b.get("target") or {}).get("languages") or [] if lang in LANGS})
    return {"categories": cats, "cities": cities, "languages": [{"id": x, "label": LANGS[x]["label"]} for x in langs]}


# ------------------------------------------------------------------ Dream Brands
def _connected_creators() -> set[str]:
    db = get_db()
    ids = {c["creator_id"] for c in db.connections.find({"platform": "instagram", "status": "connected"}, {"creator_id": 1})}
    ids |= {c["_id"] for c in db.creators.find({"channels.youtube.analytics_connected": True}, {"_id": 1})}
    return ids


def dream_counts(brand_id: str, with_names: bool) -> dict:
    db = get_db()
    saves = list(db.wishlists.find({"brand_id": brand_id}))
    connected = _connected_creators()
    linked = [s for s in saves if s["creator_id"] in connected]
    out = {"connected": len(linked), "others": len(saves) - len(linked)}
    if with_names:
        # Names only for creators who agreed to show them.
        agreed = [s["creator_id"] for s in saves if s.get("show_name")]
        out["names"] = [{"id": c["_id"], "name": c["name"], "handle": c["handle"]} for c in db.creators.find({"_id": {"$in": agreed}}, {"name": 1, "handle": 1})]
    return out


def _visible_brand(brand_id: str) -> dict:
    b = get_db().brands.find_one({"$and": [{"_id": brand_id}, VISIBLE]})
    if not b:
        raise HTTPException(404, "Brand not found")
    return b


def save_dream(creator_id: str, brand_id: str, show_name: bool) -> dict:
    db = get_db()
    _visible_brand(brand_id)
    key = f"wl_{creator_id}_{brand_id}"
    if not db.wishlists.find_one({"_id": key}) and db.wishlists.count_documents({"creator_id": creator_id}) >= MAX_DREAM:
        raise HTTPException(409, f"You can save up to {MAX_DREAM} Dream Brands.")
    db.wishlists.update_one(
        {"_id": key},
        {"$set": {"creator_id": creator_id, "brand_id": brand_id, "show_name": show_name, "updated_at": now_iso()}, "$setOnInsert": {"at": now_iso()}},
        upsert=True,
    )
    return {"saved": True, "show_name": show_name}


def unsave_dream(creator_id: str, brand_id: str) -> dict:
    get_db().wishlists.delete_one({"_id": f"wl_{creator_id}_{brand_id}"})
    return {"saved": False}


def dream_list(creator_id: str) -> dict:
    db = get_db()
    saves = {s["brand_id"]: s for s in db.wishlists.find({"creator_id": creator_id})}
    brands = list(db.brands.find({"$and": [{"_id": {"$in": list(saves)}}, VISIBLE]}))
    live = _live_counts([b["_id"] for b in brands])
    items = sorted(
        ({**card(b, live.get(b["_id"], 0)), "saved_at": saves[b["_id"]].get("at"), "show_name": bool(saves[b["_id"]].get("show_name")),
          "fan_proof": fan_proof.summary(creator_id, b["_id"])} for b in brands),
        key=lambda x: x["saved_at"] or "",
        reverse=True,
    )
    notes = list(db.notifications.find({"to": creator_id, "kind": "dream_brand_listing"}).sort("at", -1).limit(20))
    return {
        "items": items,
        "notifications": [{k: n.get(k) for k in ("brand_id", "brand_name", "listing_id", "title", "listing_type", "at", "read")} | {"id": n["_id"]} for n in notes],
        "unread": sum(1 for n in notes if not n.get("read")),
    }


def mark_read(creator_id: str) -> None:
    get_db().notifications.update_many({"to": creator_id, "kind": "dream_brand_listing", "read": {"$ne": True}}, {"$set": {"read": True}})


def notify_dream(listing: dict) -> int:
    """A saved brand opened a campaign or collective: tell each creator who saved it, once."""
    if listing.get("type") not in ("brand_campaign", "collective"):
        return 0
    db = get_db()
    brand = db.brands.find_one({"_id": listing["owner_id"]}, {"name": 1})
    if not brand:
        return 0
    n = 0
    for s in db.wishlists.find({"brand_id": listing["owner_id"]}):
        nid = f"nt_dream_{listing['_id']}_{s['creator_id']}"
        if db.notifications.find_one({"_id": nid}):
            continue
        db.notifications.insert_one(
            {
                "_id": nid,
                "to": s["creator_id"],
                "kind": "dream_brand_listing",
                "brand_id": listing["owner_id"],
                "brand_name": brand["name"],
                "listing_id": listing["_id"],
                "listing_type": listing["type"],
                "title": listing.get("title"),
                "at": now_iso(),
                "read": False,
            }
        )
        n += 1
    return n


# ------------------------------------------------------------------ brand page
def _campaign_summary(x: dict) -> dict:
    b = x.get("budget") or {}
    if b.get("total"):
        budget = f"₹{b['total']:,} total"
    elif b.get("per_creator_min"):
        budget = f"₹{b['per_creator_min']:,}–{b.get('per_creator_max', b['per_creator_min']):,} per creator"
    elif b.get("commission_pct"):
        budget = f"{b['commission_pct']}% commission"
    else:
        budget = None
    return {"id": x["_id"], "title": x["title"], "type": x["type"], "deadline": x.get("deadline"), "budget": budget,
            "deliverables": [{"kind": d["kind"], "count": d["count"]} for d in x.get("deliverables") or []]}


def page(slug: str, user: dict | None) -> dict:
    db = get_db()
    b = db.brands.find_one({"$and": [{"slug": slug.lower()}, VISIBLE]})
    if not b:
        raise HTTPException(404, "Brand not found")
    owner = bool(user and user.get("brand_id") == b["_id"])
    claimed = b.get("claimed", True)
    live = [x for x in db.listings.find({"owner_id": b["_id"], "status": {"$in": ["live", "open"]}})] if claimed else []
    d = {**card(b, len(live)), "dream": dream_counts(b["_id"], with_names=owner), "owner": owner}
    if claimed:
        d.update({"description": b.get("description") or "", "website": b.get("website"), "campaigns": [_campaign_summary(x) for x in live]})
    viewer: dict = {}
    if user and user.get("creator_id"):
        s = db.wishlists.find_one({"_id": f"wl_{user['creator_id']}_{b['_id']}"})
        viewer = {"role": "creator", "creator_id": user["creator_id"], "saved": bool(s), "show_name": bool(s and s.get("show_name"))}
    elif user and user.get("role") == "brand" and not claimed:
        c = db.claim_requests.find_one({"brand_id": b["_id"], "user_id": user["_id"]})
        viewer = {"role": "brand", "can_claim": not _has_brand(user), "claim": c["status"] if c else None}
    d["viewer"] = viewer
    return d


# ------------------------------------------------------------------ claims and removal
def _has_brand(user: dict) -> bool:
    return bool(user.get("brand_id") and get_db().brands.count_documents({"_id": user["brand_id"]}))


def request_claim(slug: str, user: dict, message: str) -> dict:
    au.require_role(user, "brand")
    db = get_db()
    b = db.brands.find_one({"$and": [{"slug": slug.lower()}, VISIBLE]})
    if not b:
        raise HTTPException(404, "Brand not found")
    if b.get("claimed", True):
        raise HTTPException(409, "This page is already managed by its brand.")
    if _has_brand(user):
        raise HTTPException(409, "This account already manages a brand. Claim with the account that should own this page.")
    cid = f"cl_{b['_id']}_{user['_id']}"
    existing = db.claim_requests.find_one({"_id": cid})
    if existing and existing["status"] == "pending":
        return {"status": "pending", "id": cid, "duplicate": True}
    db.claim_requests.replace_one(
        {"_id": cid},
        {"_id": cid, "brand_id": b["_id"], "brand_name": b["name"], "user_id": user["_id"], "user_name": user.get("name"), "user_email": user.get("email"),
         "message": message, "status": "pending", "at": now_iso()},
        upsert=True,
    )
    au.audit("brand_claim_requested", user["_id"], "brand", brand_id=b["_id"])
    return {"status": "pending", "id": cid, "duplicate": False}


def decide_claim(claim_id: str, approve: bool, admin: dict, reason: str) -> dict:
    db = get_db()
    c = db.claim_requests.find_one({"_id": claim_id})
    if not c:
        raise HTTPException(404, "Claim not found")
    if c["status"] != "pending":
        raise HTTPException(409, f"This claim was already {c['status']}.")
    b = db.brands.find_one({"_id": c["brand_id"]})
    if approve:
        u = db.users.find_one({"_id": c["user_id"]})
        if not b or b.get("claimed", True):
            raise HTTPException(409, "This page is already managed by a brand.")
        if not u or u.get("role") != "brand" or _has_brand(u):
            raise HTTPException(409, "That account can't take this page (it already manages a brand, or isn't a brand account).")
        db.brands.update_one({"_id": b["_id"]}, {"$set": {"claimed": True, "claimed_at": now_iso(), "owner_user_id": u["_id"],
                                                          "target": b.get("target") or {"ages": [], "gender": "any", "regions": [], "cities": [], "languages": []}}})
        au.link_profile(u, b["_id"])
        db.claim_requests.update_many({"brand_id": b["_id"], "status": "pending", "_id": {"$ne": claim_id}}, {"$set": {"status": "rejected", "decided_at": now_iso()}})
    db.claim_requests.update_one({"_id": claim_id}, {"$set": {"status": "approved" if approve else "rejected", "decided_at": now_iso(), "decided_by": admin["_id"], "decision_reason": reason}})
    au.audit("brand_claim_" + ("approved" if approve else "rejected"), admin["_id"], "admin", brand_id=c["brand_id"], claim_id=claim_id, reason=reason)
    return db.claim_requests.find_one({"_id": claim_id}, {"user_email": 0})


def request_removal(slug: str, reason: str, contact: str | None) -> dict:
    db = get_db()
    b = db.brands.find_one({"$and": [{"slug": slug.lower()}, VISIBLE]})
    if not b:
        raise HTTPException(404, "Brand not found")
    if b.get("claimed", True):
        raise HTTPException(409, "This page is managed by its brand. Contact them, or report it instead.")
    rid = f"rr_{uuid.uuid4().hex[:10]}"
    db.removal_requests.insert_one({"_id": rid, "brand_id": b["_id"], "brand_name": b["name"], "reason": reason, "contact": contact, "status": "pending", "at": now_iso()})
    au.audit("brand_removal_requested", None, None, brand_id=b["_id"], request_id=rid)
    return {"status": "pending", "id": rid}


def decide_removal(request_id: str, remove: bool, admin: dict, reason: str) -> dict:
    db = get_db()
    r = db.removal_requests.find_one({"_id": request_id})
    if not r:
        raise HTTPException(404, "Request not found")
    if r["status"] != "pending":
        raise HTTPException(409, f"This request was already {r['status']}.")
    if remove:
        db.brands.update_one({"_id": r["brand_id"]}, {"$set": {"removed": True, "removed_at": now_iso()}})
        db.wishlists.delete_many({"brand_id": r["brand_id"]})
    db.removal_requests.update_one({"_id": request_id}, {"$set": {"status": "removed" if remove else "kept", "decided_at": now_iso(), "decided_by": admin["_id"], "decision_reason": reason}})
    au.audit("brand_removal_" + ("done" if remove else "declined"), admin["_id"], "admin", brand_id=r["brand_id"], request_id=request_id, reason=reason)
    return db.removal_requests.find_one({"_id": request_id})


# ------------------------------------------------------------------ unclaimed brands (admins only)
class Handles(BaseModel):
    instagram: str | None = Field(default=None, max_length=41)
    youtube: str | None = Field(default=None, max_length=41)

    @field_validator("instagram", "youtube")
    @classmethod
    def _handle(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        v = v.strip()
        if not HANDLE.match(v):
            raise ValueError("Enter a public handle like @brandname")
        return v if v.startswith("@") else f"@{v}"


class UnclaimedIn(BaseModel):
    name: str = Field(min_length=2, max_length=60)
    category: str = Field(min_length=2, max_length=60)
    public_handles: Handles = Handles()


def add_unclaimed(body: UnclaimedIn, admin: dict, reason: str) -> dict:
    db = get_db()
    name = body.name.strip()
    if db.brands.count_documents({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}, "removed": {"$ne": True}}):
        raise HTTPException(409, "A brand with that name is already listed.")
    bid = f"br_unc_{uuid.uuid4().hex[:8]}"
    doc = {
        "_id": bid,
        "kind": "brand",
        "name": name,
        "slug": unique_slug(name),
        "category": body.category.strip(),
        "public_handles": body.public_handles.model_dump(exclude_none=True),
        "claimed": False,
        "verified": False,
        "source": "manual",
        "added_by": admin["_id"],
        "added_reason": reason,
        "created_at": now_iso(),
    }
    db.brands.insert_one(doc)
    au.audit("brand_unclaimed_added", admin["_id"], "admin", brand_id=bid, reason=reason)
    return card(doc)
