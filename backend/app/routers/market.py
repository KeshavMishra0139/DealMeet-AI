"""Creator-side marketplace and the consent ledger."""
from __future__ import annotations

import uuid
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..config import now_iso
from ..db import get_db, out_many
from ..engines.opportunities import matched
from ..services import cache
from ..services import consent as cs
from ..services import social
from ..services.auth import own_creator
from ..services.creator_ctx import load_creator

# Every route here acts on one creator's own data: only that creator's account may call it.
router = APIRouter(prefix="/api/creators/{creator_id}", tags=["marketplace"], dependencies=[Depends(own_creator)])


@router.get("/opportunities")
def opportunities(creator_id: str):
    c = load_creator(creator_id)
    db = get_db()
    data = matched(c)
    apps = {a["listing_id"]: a for a in db.applications.find({"creator_id": creator_id})}
    for item in data["items"]:
        lister_id = item["lister"]["id"]
        item["scopes"] = cs.scopes_for(c, lister_id) or {k: False for k in cs.SCOPES}
        item["scope_source"] = cs.source_for(creator_id, lister_id)
        app = apps.get(item["id"])
        item["application"] = app["status"] if app else None
    counts: dict[str, int] = {}
    for item in data["items"]:
        counts[item["type"]] = counts.get(item["type"], 0) + 1
    return {"items": data["items"], "hidden": data["hidden"], "counts": counts}


class ApplyIn(BaseModel):
    listing_id: str
    scopes: dict[str, bool]
    message: str | None = Field(default=None, max_length=400)


@router.post("/apply")
def apply(creator_id: str, body: ApplyIn):
    c = load_creator(creator_id)
    db = get_db()
    listing = db.listings.find_one({"_id": body.listing_id})
    if not listing:
        raise HTTPException(404, "Listing not found")
    cs.grant(c["_id"], listing["owner_id"], body.scopes)
    status = "opted_in" if listing["type"] == "collective" else "applied"
    doc = {
        "_id": f"ap_{creator_id}_{body.listing_id}",
        "creator_id": creator_id,
        "listing_id": body.listing_id,
        "lister_id": listing["owner_id"],
        "status": status,
        "message": body.message,
        "at": now_iso(),
    }
    db.applications.replace_one({"_id": doc["_id"]}, doc, upsert=True)
    return {"status": status}


@router.delete("/apply/{listing_id}")
def withdraw(creator_id: str, listing_id: str):
    get_db().applications.update_one({"_id": f"ap_{creator_id}_{listing_id}"}, {"$set": {"status": "withdrawn"}})
    return {"status": "withdrawn"}


class CollabIn(BaseModel):
    title: str = Field(min_length=4, max_length=90)
    summary: str = Field(min_length=10, max_length=300)
    languages: list[Annotated[str, Field(max_length=40)]] = Field(default=[], max_length=10)


@router.post("/collabs")
def post_collab(creator_id: str, body: CollabIn):
    c = load_creator(creator_id)
    if get_db().listings.count_documents({"owner_id": creator_id}) >= 20:
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    lid = f"lst_cc_{uuid.uuid4().hex[:8]}"
    get_db().listings.insert_one(
        {
            "_id": lid,
            "type": "creator_collab",
            "owner_id": c["_id"],
            "title": body.title.strip(),
            "summary": body.summary.strip(),
            "niches": [c["niche"]],
            "languages": body.languages or c.get("languages", []),
            "regions": ["Pan-India"],
            "deal_kind": "collab",
            "deliverables": [{"kind": "reel", "count": 1}],
            "usage_rights_days": 0,
            "exclusivity_days": 0,
            "min_followers": 0,
            "budget": {},
            "posted_on": now_iso()[:10],
            "deadline": None,
            "status": "open",
        }
    )
    cache.invalidate("spam")
    return {"id": lid}


# ------------------------------------------------------------- privacy ledger
@router.get("/privacy")
def privacy(creator_id: str):
    c = load_creator(creator_id)
    db = get_db()
    listers = {b["_id"]: b for b in db.brands.find({})}
    creators = {x["_id"]: x["name"] for x in db.creators.find({}, {"name": 1})}

    def name(lid: str) -> str:
        return listers.get(lid, {}).get("name") or creators.get(lid) or "Unknown lister"

    grants = []
    for g in db.consents.find({"creator_id": creator_id}):
        grants.append(
            {
                "lister_id": g["lister_id"],
                "lister": name(g["lister_id"]),
                "kind": listers.get(g["lister_id"], {}).get("kind", "creator"),
                "verified": listers.get(g["lister_id"], {}).get("verified", True),
                "scopes": g["scopes"],
                "status": g["status"],
                "granted_at": g.get("granted_at"),
                "revoked_at": g.get("revoked_at"),
            }
        )
    grants.sort(key=lambda g: (g["status"] != "active", g["lister"]))
    requests = []
    for n in db.notifications.find({"to": creator_id, "kind": "access_request", "status": "pending"}):
        requests.append({"id": n["_id"], "lister_id": n["lister_id"], "lister": name(n["lister_id"]), "scopes": n["scopes"], "at": n["at"]})
    audit = []
    for a in db.consent_audit.find({"creator_id": creator_id}, sort=[("at", -1)]).limit(40):
        audit.append({"id": a["_id"], "lister": name(a["lister_id"]), "action": a["action"], "scopes": a["scopes"], "at": a["at"], "actor": a["actor"]})
    return {
        "discoverable": c.get("discoverable", True),
        "defaults": c.get("consent_defaults") or {},
        "scope_labels": cs.SCOPE_LABELS,
        "grants": grants,
        "requests": requests,
        "audit": audit,
        "sources": [
            {
                "platform": p["platform"],
                "connected": p["status"] == "connected",
                "status": p["status"],
                "via": "Official login, read-only" if p["status"] == "connected" else None,
            }
            for p in social.status(c)["platforms"]
        ],
        "is_reference": c.get("is_reference", False),
    }


class PrivacyIn(BaseModel):
    discoverable: bool | None = None
    defaults: dict[str, bool] | None = None


@router.post("/privacy")
def update_privacy(creator_id: str, body: PrivacyIn):
    load_creator(creator_id)
    update = {}
    if body.discoverable is not None:
        update["discoverable"] = body.discoverable
    if body.defaults is not None:
        update["consent_defaults"] = {k: bool(body.defaults.get(k)) for k in cs.SCOPES}
    if update:
        get_db().creators.update_one({"_id": creator_id}, {"$set": update})
        cs.audit(creator_id, "*", "settings", [k for k, v in (update.get("consent_defaults") or {}).items() if v], "creator")
    return privacy(creator_id)


class ScopesIn(BaseModel):
    scopes: dict[str, bool]


@router.post("/consents/{lister_id}")
def set_consent(creator_id: str, lister_id: str, body: ScopesIn):
    load_creator(creator_id)
    cs.grant(creator_id, lister_id, body.scopes)
    return privacy(creator_id)


@router.delete("/consents/{lister_id}")
def revoke_consent(creator_id: str, lister_id: str):
    load_creator(creator_id)
    cs.revoke(creator_id, lister_id)
    return privacy(creator_id)


class RequestAnswer(BaseModel):
    answer: Literal["approve", "decline"]


@router.post("/requests/{request_id}")
def answer_request(creator_id: str, request_id: str, body: RequestAnswer):
    db = get_db()
    n = db.notifications.find_one({"_id": request_id, "to": creator_id})
    if not n:
        raise HTTPException(404, "Request not found")
    db.notifications.update_one({"_id": request_id}, {"$set": {"status": body.answer + "d"}})
    if body.answer == "approve":
        c = load_creator(creator_id)
        current = cs.scopes_for(c, n["lister_id"]) or {}
        cs.grant(creator_id, n["lister_id"], {**current, **{s: True for s in n["scopes"]}})
    else:
        cs.audit(creator_id, n["lister_id"], "declined", n["scopes"], "creator")
    return privacy(creator_id)


@router.get("/export")
def export(creator_id: str):
    """Everything JodiDar holds about this creator, as JSON."""
    c = load_creator(creator_id)
    db = get_db()
    c = dict(c)
    c["id"] = c.pop("_id")
    c.pop("seed_low_trust", None)
    return {
        "profile": c,
        "consents": out_many(db.consents.find({"creator_id": creator_id})),
        "audit": out_many(db.consent_audit.find({"creator_id": creator_id})),
        "deals": out_many(db.deals.find({"creator_id": creator_id})),
    }
