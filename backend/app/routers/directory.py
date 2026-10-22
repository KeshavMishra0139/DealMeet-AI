"""The brand directory and brand pages (public), Dream Brands (creators), claim and
removal requests."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from pydantic import BaseModel, Field

from ..services import auth as au
from ..services import directory as dr
from ..services import public_search as ps
from ..services import ratelimit

router = APIRouter(prefix="/api", tags=["directory"])


@router.get("/directory/brands")
def search_brands(
    q: str = Query("", max_length=80),
    category: str | None = Query(None, max_length=60),
    city: str | None = Query(None, max_length=60),
    language: str | None = Query(None, max_length=20),
    open: bool = False,
    page: int = Query(1, ge=1, le=100),
    user: dict | None = Depends(au.optional_user),
):
    """Public. Search by keywords, category, city, language, and brands with open campaigns.
    Visitors get the first few; members get every page."""
    return dr.search(q, category, city, language, open, page, signed_in=user is not None)


@router.get("/directory/suggest")
def suggest(request: Request, q: str = Query("", max_length=80), kind: str = Query("creators", pattern="^(creators|brands)$")):
    """Public. Suggestions as someone types: names, tags, niches, cities, languages
    (creators) or brand names and categories (brands), from public data only."""
    ratelimit.enforce(f"suggest:{ratelimit.client_ip(request)}", 1200, 3600, "Too many requests from here. Try again in a bit.")
    return {"items": ps.suggest(q, kind)}


@router.get("/directory/creators")
def search_creators(
    request: Request,
    q: str = Query("", max_length=80),
    niche: str | None = Query(None, max_length=200, description="One or more niche ids, comma-separated"),
    web: bool = Query(True, description="Also search public YouTube channels"),
    user: dict | None = Depends(au.optional_user),
):
    """Public. Creators who keep a public page, matched on their own words, then public
    YouTube channels that match. Visitors get the best few; members get more."""
    ip = ratelimit.client_ip(request)
    if user is None:
        ratelimit.enforce(f"csearch:{ip}", 120, 3600, "That's a lot of searches from here. Sign in, or try again in an hour.")
    return ps.creators(q, niche, signed_in=user is not None, ip=ip, web=web)


@router.get("/directory/facets")
def facets():
    return dr.facets()


@router.get("/directory/brands/{slug}")
def brand_page(slug: str, user: dict | None = Depends(au.optional_user)):
    return dr.page(slug, user)


class ClaimIn(BaseModel):
    message: str = Field(min_length=10, max_length=600)


@router.post("/directory/brands/{slug}/claim")
def claim(slug: str, body: ClaimIn, user: dict = Depends(au.current_user)):
    """A brand account asks to own this unclaimed page. An admin decides."""
    ratelimit.enforce(f"claim:{user['_id']}", 5, 86_400, "Too many claim requests today.")
    return dr.request_claim(slug, user, body.message.strip())


class ClaimCodeIn(BaseModel):
    email: str = Field(min_length=5, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/directory/brands/{slug}/claim/code")
def claim_code(slug: str, body: ClaimCodeIn, user: dict = Depends(au.current_user)):
    """Emails a code to an address at the brand's own website domain."""
    ratelimit.enforce(f"claimcode:{user['_id']}", 5, 3600, "Too many codes asked for. Try again in an hour.")
    return dr.send_claim_code(slug, user, body.email)


class ClaimVerifyIn(BaseModel):
    code: str = Field(min_length=6, max_length=6, pattern=r"^[0-9]{6}$")


@router.post("/directory/brands/{slug}/claim/verify")
def claim_verify(slug: str, body: ClaimVerifyIn, user: dict = Depends(au.current_user)):
    """The right code hands the page over without waiting for an admin."""
    return dr.confirm_claim_code(slug, user, body.code)


class RemovalIn(BaseModel):
    reason: str = Field(min_length=10, max_length=600)
    contact: str | None = Field(default=None, max_length=120, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


@router.post("/directory/brands/{slug}/removal-request")
def removal(slug: str, body: RemovalIn, request: Request):
    """Anyone may ask for an unclaimed page to be removed. An admin decides."""
    ratelimit.enforce(f"removal:{ratelimit.client_ip(request)}", 5, 3600, "Too many requests from here. Try again in an hour.")
    return dr.request_removal(slug, body.reason.strip(), body.contact)


# ------------------------------------------------------------------ Dream Brands
class DreamIn(BaseModel):
    show_name: bool = False


@router.get("/creators/{creator_id}/dream-brands")
def dream_brands(creator_id: str, _: dict = Depends(au.own_creator)):
    return dr.dream_list(creator_id)


@router.put("/creators/{creator_id}/dream-brands/{brand_id}")
def save_dream(creator_id: str, brand_id: str, body: DreamIn, _: dict = Depends(au.own_creator)):
    return dr.save_dream(creator_id, brand_id, body.show_name)


@router.delete("/creators/{creator_id}/dream-brands/{brand_id}")
def unsave_dream(creator_id: str, brand_id: str, _: dict = Depends(au.own_creator)):
    return dr.unsave_dream(creator_id, brand_id)


@router.post("/creators/{creator_id}/dream-brands/read")
def read_notifications(creator_id: str, _: dict = Depends(au.own_creator)):
    dr.mark_read(creator_id)
    return {"ok": True}
