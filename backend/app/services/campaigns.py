"""Campaign lifecycle for brands.

draft -> live -> paused <-> live, and any -> closed (final). Publishing (and resuming)
checks the campaign is complete: required fields, a sane budget and a future deadline,
and says what is missing. Edits can't make a live or paused campaign invalid. Only live
campaigns are visible to creators, and only live campaigns take applications or offers.
Every change is kept in the campaign's history and the audit log.
"""
from __future__ import annotations

from datetime import date, timedelta

from fastapi import HTTPException

from ..config import now_iso, today
from ..db import get_db
from ..seed.catalog import CITIES, LANGS, NICHES
from . import auth as au

STATUSES = ("draft", "live", "paused", "closed")
# Older records said "open" for live.
LIVE_QUERY = {"$in": ["live", "open"]}
OBJECTIVES = {
    "awareness": "Awareness",
    "consideration": "Consideration",
    "sales": "Sales",
    "launch": "Product launch",
    "content": "Content for ads",
}
AGES = ["13-17", "18-24", "25-34", "35-44", "45+"]
REGIONS = ["Pan-India", "North", "South", "East", "West", "Central", "Northeast"]
MIN_PER_CREATOR = 500
MAX_BUDGET = 50_000_000
MAX_DAYS_AHEAD = 365
APPLICATION_STATES = ("applied", "opted_in", "shortlisted", "offered", "declined", "withdrawn")

# action -> (allowed from, to)
TRANSITIONS = {
    "publish": (("draft",), "live"),
    "pause": (("live",), "paused"),
    "resume": (("paused",), "live"),
    "close": (("draft", "live", "paused"), "closed"),
}


def status_of(x: dict) -> str:
    s = x.get("status", "live")
    return "live" if s == "open" else s


def is_live(x: dict) -> bool:
    return status_of(x) == "live"


def _date(s: str | None) -> date | None:
    try:
        return date.fromisoformat(s) if s else None
    except ValueError:
        return None


def missing(x: dict) -> list[dict]:
    """What stops this campaign going live. Empty means it's complete."""
    out: list[dict] = []

    def need(field: str, message: str) -> None:
        out.append({"field": field, "message": message})

    if len((x.get("title") or "").strip()) < 4:
        need("title", "Add a title of at least 4 characters.")
    if len((x.get("summary") or "").strip()) < 10:
        need("summary", "Write a brief of at least 10 characters.")
    if not x.get("objectives"):
        need("objectives", "Pick at least one objective.")
    if not x.get("niches"):
        need("niches", "Pick at least one creator niche.")
    if not x.get("languages"):
        need("languages", "Pick at least one language.")
    if not (x.get("audience") or {}).get("ages"):
        need("audience", "Pick the target audience's ages.")
    if not x.get("regions"):
        need("regions", "Pick where the campaign runs (Pan-India or regions).")
    if not any((d.get("count") or 0) > 0 for d in x.get("deliverables") or []):
        need("deliverables", "Add at least one deliverable.")
    b = x.get("budget") or {}
    if x.get("type") == "collective":
        size = x.get("collective_size") or 0
        total = b.get("total") or 0
        if total <= 0:
            need("budget", "Set the collective's total budget.")
        elif size and total / size < MIN_PER_CREATOR:
            need("budget", f"The total budget gives each of {size} creators less than ₹{MIN_PER_CREATOR}. Raise it or book fewer creators.")
        elif total > MAX_BUDGET:
            need("budget", "That budget is higher than this app accepts.")
    elif x.get("deal_kind") == "affiliate":
        if not 1 <= (b.get("commission_pct") or 0) <= 50:
            need("budget", "Set a commission between 1% and 50%.")
    elif x.get("deal_kind") in ("paid", "barter_plus_fee"):
        lo, hi = b.get("per_creator_min"), b.get("per_creator_max")
        if not lo or not hi:
            need("budget", "Set the budget per creator (from and up to).")
        elif lo < MIN_PER_CREATOR:
            need("budget", f"The budget per creator should start at ₹{MIN_PER_CREATOR} or more.")
        elif hi < lo:
            need("budget", "The upper budget is below the lower one.")
        elif hi > MAX_BUDGET:
            need("budget", "That budget is higher than this app accepts.")
    deadline = _date(x.get("deadline"))
    start = _date(x.get("start_date"))
    if not deadline:
        need("deadline", "Set a deadline.")
    elif deadline <= today():
        need("deadline", "The deadline has to be in the future.")
    elif deadline > today() + timedelta(days=MAX_DAYS_AHEAD):
        need("deadline", "Set a deadline within a year.")
    if x.get("start_date") and not start:
        need("start_date", "The start date isn't a valid date.")
    elif start and deadline and start > deadline:
        need("start_date", "The start date is after the deadline.")
    return out


def validate_fields(fields: dict) -> None:
    """Checks on values themselves (any status): known niches, languages, cities, regions."""
    if any(n not in NICHES for n in fields.get("niches") or []):
        raise HTTPException(422, "Unknown niche")
    if any(lang not in LANGS for lang in fields.get("languages") or []):
        raise HTTPException(422, "Unknown language")
    if any(c not in CITIES for c in fields.get("cities") or []):
        raise HTTPException(422, "Pick cities from the list")
    if any(r not in REGIONS for r in fields.get("regions") or []):
        raise HTTPException(422, "Unknown region")
    aud = fields.get("audience") or {}
    if any(a not in AGES for a in aud.get("ages") or []):
        raise HTTPException(422, "Unknown age group")
    for k in ("deadline", "start_date"):
        if fields.get(k) and not _date(fields[k]):
            raise HTTPException(422, f"{k.replace('_', ' ').capitalize()} must be a date like 2026-11-30")


def _incomplete(items: list[dict], verb: str) -> HTTPException:
    return HTTPException(422, {"message": f"Can't {verb} yet: {len(items)} thing{'s' if len(items) != 1 else ''} to fix.", "missing": items})


def _history(listing_id: str, user: dict, action: str, **detail) -> None:
    entry = {"at": now_iso(), "by": user["_id"], "action": action, **detail}
    get_db().listings.update_one({"_id": listing_id}, {"$push": {"history": entry}})
    au.audit(f"campaign_{action}", user["_id"], user.get("role"), listing_id=listing_id, **detail)


def create(listing: dict, user: dict) -> dict:
    get_db().listings.insert_one({**listing, "status": "draft", "history": []})
    _history(listing["_id"], user, "created")
    return listing


def edit(x: dict, changes: dict, user: dict) -> dict:
    status = status_of(x)
    if status == "closed":
        raise HTTPException(409, "This campaign is closed. Closed campaigns can't be edited.")
    validate_fields(changes)
    merged = {**x, **changes}
    if status in ("live", "paused"):
        problems = missing(merged)
        if problems:
            raise _incomplete(problems, "save this change: the campaign is live and would become incomplete")
    if changes:
        get_db().listings.update_one({"_id": x["_id"]}, {"$set": changes})
        _history(x["_id"], user, "edited", fields=sorted(changes))
    return get_db().listings.find_one({"_id": x["_id"]})


def transition(x: dict, action: str, user: dict) -> tuple[dict, bool]:
    """Returns (listing, changed). Asking for the state it's already in changes nothing."""
    allowed, target = TRANSITIONS[action]
    current = status_of(x)
    if current == target:
        return x, False
    if current not in allowed:
        raise HTTPException(409, f"A {current} campaign can't be {'published' if action == 'publish' else action + 'd'}.")
    if target == "live":
        problems = missing(x)
        if problems:
            raise _incomplete(problems, "publish" if action == "publish" else "resume")
    db = get_db()
    # Only move from the state we read, so two requests at once can't both apply.
    res = db.listings.update_one({"_id": x["_id"], "status": x.get("status")}, {"$set": {"status": target, f"{target}_at": now_iso()}})
    if res.modified_count == 0:
        fresh = db.listings.find_one({"_id": x["_id"]})
        if fresh and status_of(fresh) == target:
            return fresh, False
        raise HTTPException(409, "The campaign changed at the same time. Reload and try again.")
    _history(x["_id"], user, action, **{"from": current, "to": target})
    return db.listings.find_one({"_id": x["_id"]}), True


def visible_to(x: dict, user: dict | None) -> bool:
    """Owners see their campaigns in any state. Others see live ones, plus paused or
    closed ones they already applied to or have a deal on. Drafts stay private."""
    if user and x.get("owner_id") in (user.get("brand_id"), user.get("creator_id")):
        return True
    status = status_of(x)
    if status == "live":
        return True
    if status == "draft" or not user or not user.get("creator_id"):
        return False
    db = get_db()
    cid = user["creator_id"]
    return bool(db.applications.count_documents({"listing_id": x["_id"], "creator_id": cid}) or db.deals.count_documents({"listing_id": x["_id"], "creator_id": cid}))


def require_live(x: dict, what: str) -> None:
    if not is_live(x):
        raise HTTPException(409, f"This campaign is {status_of(x)}, so it isn't {what} right now.")


# ------------------------------------------------------------------ applications
def applications(x: dict) -> dict:
    db = get_db()
    apps = list(db.applications.find({"listing_id": x["_id"]}))
    creators = {c["_id"]: c for c in db.creators.find({"_id": {"$in": [a["creator_id"] for a in apps]}}, {"name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1, "niche": 1, "followers": 1})}
    items = []
    for a in sorted(apps, key=lambda a: a.get("at", ""), reverse=True):
        c = creators.get(a["creator_id"])
        if not c:
            continue
        status = "applied" if a["status"] == "opted_in" else a["status"]
        items.append(
            {
                "creator_id": c["_id"],
                "name": c["name"],
                "handle": c["handle"],
                "avatar_hue": c.get("avatar_hue", 260),
                "is_reference": c.get("is_reference", False),
                "niche": NICHES[c["niche"]]["label"],
                "status": status,
                "message": a.get("message"),
                "at": a.get("at"),
                "deal_id": a.get("deal_id"),
            }
        )
    groups = {s: sum(1 for i in items if i["status"] == s) for s in ("applied", "shortlisted", "offered", "declined", "withdrawn")}
    return {"listing_id": x["_id"], "status": status_of(x), "items": items, "counts": groups}


def set_application(x: dict, creator_id: str, status: str, user: dict) -> dict:
    db = get_db()
    a = db.applications.find_one({"listing_id": x["_id"], "creator_id": creator_id})
    if not a:
        raise HTTPException(404, "No application from that creator")
    if a["status"] in ("offered", "withdrawn"):
        raise HTTPException(409, f"This application is {a['status']}; it can't be changed here.")
    if status_of(x) == "closed":
        raise HTTPException(409, "This campaign is closed.")
    if a["status"] != status:
        db.applications.update_one({"_id": a["_id"]}, {"$set": {"status": status, "updated_at": now_iso()}})
        _history(x["_id"], user, "application", creator_id=creator_id, **{"from": a["status"], "to": status})
        # A shortlisted applicant is on the campaign's shortlist, and leaves it when moved on.
        key = {"listing_id": x["_id"], "creator_id": creator_id}
        if status == "shortlisted":
            at = now_iso()
            db.shortlists.update_one(
                {"_id": f"sl_{x['_id']}_{creator_id}"},
                {"$set": {**key, "brand_id": x["owner_id"], "updated_at": at}, "$setOnInsert": {"note": None, "added_at": at, "added_by": user["_id"]}},
                upsert=True,
            )
        elif a["status"] == "shortlisted":
            db.shortlists.delete_one(key)
    return applications(x)


def mark_offered(listing_id: str | None, creator_id: str, deal_id: str) -> None:
    """An offer on a campaign moves that creator's application (if any) to offered."""
    if listing_id:
        get_db().applications.update_one(
            {"listing_id": listing_id, "creator_id": creator_id, "status": {"$nin": ["withdrawn"]}},
            {"$set": {"status": "offered", "deal_id": deal_id, "updated_at": now_iso()}},
        )
