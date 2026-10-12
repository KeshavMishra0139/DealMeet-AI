"""Auto media kit (PDF) and the public JodiDar link-in-bio page."""
from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import get_settings, now_iso
from ..db import get_db
from ..engines.fair_price import fair_price
from ..services import auth as au
from ..services import branding, creator_page, ratelimit
from ..services import media_kit as mk
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["kit"])


LangQ = Query("en", pattern="^(en|hi)$")


def _host(request: Request) -> str:
    return request.url.netloc


@router.get("/creators/{creator_id}/kit")
def kit(creator_id: str, lang: str = LangQ, _: dict = Depends(au.own_creator)):
    """The live media kit, rebuilt from current data."""
    c = load_creator(creator_id)
    return {**mk.build_kit(c, lang), "public_version": c.get("kit_public_version")}


class PublicIn(BaseModel):
    stats: bool
    demographics: bool
    rates: bool
    collabs: bool = True  # past collaborations and case studies


@router.post("/creators/{creator_id}/kit")
def update_public(creator_id: str, body: PublicIn, lang: str = LangQ, _: dict = Depends(au.own_creator)):
    load_creator(creator_id)
    get_db().creators.update_one({"_id": creator_id}, {"$set": {"public_scopes": body.model_dump()}})
    c = load_creator(creator_id)
    return {**mk.build_kit(c, lang), "public_version": c.get("kit_public_version")}


@router.get("/creators/{creator_id}/kit.pdf")
def kit_pdf(creator_id: str, request: Request, lang: str = LangQ, _: dict = Depends(au.own_creator)):
    k = mk.build_kit(load_creator(creator_id), lang)
    return Response(mk.render_pdf(k, _host(request)), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="jodidar-media-kit-{k["handle"]}{"-hi" if lang == "hi" else ""}.pdf"'})


# ------------------------------------------------------------------ saved versions
@router.get("/creators/{creator_id}/kit/versions")
def versions(creator_id: str, _: dict = Depends(au.own_creator)):
    c = load_creator(creator_id)
    return {"versions": mk.list_versions(c), "public_version": c.get("kit_public_version"), "max": mk.MAX_VERSIONS}


@router.post("/creators/{creator_id}/kit/versions")
def save_version(creator_id: str, body: mk.VersionIn, request: Request, response: Response, _: dict = Depends(au.own_creator)):
    """Save the kit as it is now, with these edits, as a version that never changes."""
    summary, created = mk.create_version(load_creator(creator_id), body, _host(request))
    response.status_code = 201 if created else 200
    return {**summary, "created": created}


@router.get("/creators/{creator_id}/kit/versions/{version_id}")
def version(creator_id: str, version_id: str, _: dict = Depends(au.own_creator)):
    c = load_creator(creator_id)
    v = mk.get_version(c, version_id)
    return {"id": v["_id"], "number": v["number"], "created_at": v["created_at"], "pdf_sha256": v["pdf_sha256"], "kit": v["content"]}


@router.get("/creators/{creator_id}/kit/versions/{version_id}/pdf")
def version_pdf(creator_id: str, version_id: str, _: dict = Depends(au.own_creator)):
    """The PDF stored when the version was saved, byte for byte."""
    v = mk.get_version(load_creator(creator_id), version_id)
    return Response(bytes(v["pdf"]), media_type="application/pdf",
                    headers={"Content-Disposition": f'inline; filename="jodidar-media-kit-v{v["number"]}.pdf"'})


@router.delete("/creators/{creator_id}/kit/versions/{version_id}")
def remove_version(creator_id: str, version_id: str, _: dict = Depends(au.own_creator)):
    mk.delete_version(load_creator(creator_id), version_id)
    return {"ok": True}


class PublicViewIn(BaseModel):
    version_id: str | None = Field(default=None, max_length=40)


@router.put("/creators/{creator_id}/kit/public-view")
def public_view(creator_id: str, body: PublicViewIn, _: dict = Depends(au.own_creator)):
    """Which kit the public page shows: a saved version, or the live view (null)."""
    mk.set_public_version(load_creator(creator_id), body.version_id)
    return {"public_version": body.version_id}


@router.get("/public/{handle}")
def public_page(handle: str, lang: str | None = Query(None, pattern="^(en|hi)$")):
    c = get_db().creators.find_one({"handle": handle.lstrip("@")})
    if not c or c.get("public_page") is False:
        raise HTTPException(404, "This page isn't here")
    return {**mk.public_kit(c, lang), **creator_page.public_extras(c, mk.public_scopes(c))}


# ------------------------------------------------------------------ positioning
class BrandingEdit(BaseModel):
    positioning: str | None = Field(default=None, min_length=10, max_length=120)
    pillars: list[str] | None = Field(default=None, min_length=3, max_length=3)
    bio_suggestions: list[str] | None = Field(default=None, min_length=2, max_length=2)
    show_on_page: bool | None = None


@router.get("/creators/{creator_id}/branding")
def get_branding(creator_id: str, _: dict = Depends(au.own_creator)):
    return {"branding": load_creator(creator_id).get("branding")}


@router.post("/creators/{creator_id}/branding/regenerate")
def regenerate_branding(creator_id: str, _: dict = Depends(au.own_creator)):
    """Writes (or rewrites) the positioning, pillars and bio suggestions."""
    ratelimit.enforce(f"branding:{creator_id}", 10, 3600, "That's a lot of rewrites this hour. Edit the current one, or try again later.")
    return {"branding": branding.generate_for(load_creator(creator_id))}


@router.patch("/creators/{creator_id}/branding")
def edit_branding(creator_id: str, body: BrandingEdit, _: dict = Depends(au.own_creator)):
    return {"branding": branding.edit(load_creator(creator_id), body.model_dump(exclude_none=True))}


class BookIn(BaseModel):
    brand_name: str = Field(min_length=2, max_length=60)
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    budget: int = Field(ge=500, le=50_000_000)
    deliverable: str = Field(default="reel", pattern=r"^(reel|reel_stories|bundle)$")
    message: str | None = Field(default=None, max_length=400)


@router.post("/public/{handle}/book")
def book(handle: str, body: BookIn, user: dict | None = Depends(au.optional_user)):
    """A brand books a creator from their public page. A signed-in brand books as itself.
    In demo mode a visitor without an account gets a guest brand account to follow the
    booking; outside demo mode they sign in first."""
    db = get_db()
    c = db.creators.find_one({"handle": handle.lstrip("@")})
    if not c:
        raise HTTPException(404, "Creator not found")
    if user and user.get("role") != "brand":
        raise HTTPException(403, "Sign in with a brand account to book a creator.")
    if not user and not get_settings().demo_mode:
        raise HTTPException(401, "Sign in with a brand account to book a creator.")
    if (
        db.deals.count_documents({"creator_id": c["_id"], "channel": "link_in_bio"}) >= 30
        or db.brands.count_documents({"_id": {"$regex": "^br_(new|guest)_"}}) >= 50
    ):
        raise HTTPException(429, "This shared demo is full. It resets soon; please try again later.")
    guest = False
    if user and user.get("brand_id") and db.brands.count_documents({"_id": user["brand_id"]}):
        bid = user["brand_id"]
    elif user:
        raise HTTPException(409, "Set up your brand profile first, then book.")
    else:
        bid = f"br_guest_{uuid.uuid4().hex[:6]}"
        db.brands.insert_one(
            {
                "_id": bid,
                "kind": "brand",
                "name": body.brand_name.strip(),
                "category": "Booked via link-in-bio",
                "description": "",
                "hue": sum(map(ord, body.brand_name)) % 360,
                "niches": [c["niche"]],
                "target": {"ages": [], "gender": "any", "regions": [], "cities": [], "languages": []},
                "verified": False,
                "guest": True,
                # The email isn't stored: other visitors of this shared demo could read it.
                "contact_given": True,
                "created_at": now_iso(),
            }
        )
        # A demo account for the guest brand, so the booking link below can open their console.
        account = au.new_user("brand", body.brand_name.strip(), brand_id=bid, demo=True)
        au.audit("signup", account["_id"], "brand", via="guest_booking")
        guest = True
    deliverables = {
        "reel": [{"kind": "reel", "count": 1}],
        "reel_stories": [{"kind": "reel", "count": 1}, {"kind": "story", "count": 2}],
        "bundle": [{"kind": "reel", "count": 2}],
    }[body.deliverable]
    fp = fair_price(c, None, {"deliverables": deliverables}, with_model=False)
    did = f"dl_{uuid.uuid4().hex[:10]}"
    at = now_iso()
    db.deals.insert_one(
        {
            "_id": did,
            "kind": "single",
            "listing_id": None,
            "brand_id": bid,
            "creator_id": c["_id"],
            "amount": body.budget,
            "fair_at_offer": fp["total"],
            "deliverables": deliverables,
            "usage_rights_days": 0,
            "exclusivity_days": 0,
            "stage": "offer",
            "message": body.message,
            "channel": "link_in_bio",  # how the booking arrived
            "timeline": [{"stage": "offer", "at": at, "note": f"Booking request from {body.brand_name.strip()} via link-in-bio"}],
            "created_at": at,
        }
    )
    return {
        "ok": True,
        "fair": fp["total"] if mk.public_scopes(c)["rates"] else None,
        "message": f"Sent to {c['name']}. Nothing is charged yet: if they accept, you e-sign and fund escrow on this booking's page. Nothing is emailed in this demo, so use Follow this booking to get back to it."
        if guest
        else f"Sent to {c['name']}. Nothing is charged yet: if they accept, you e-sign and fund escrow from Deals in your Brand Console.",
        # A guest (demo mode) follows the booking with the guest account made for them.
        "track": f"/brand/deals/{did}?as={bid}" if guest else f"/brand/deals/{did}",
    }
