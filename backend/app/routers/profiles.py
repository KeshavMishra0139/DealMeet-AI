from fastapi import APIRouter, HTTPException

from ..db import get_db, out
from ..services.views import creator_view

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/creators/{creator_id}")
def get_creator(creator_id: str):
    c = get_db().creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    return creator_view(c)


@router.get("/creators/by-handle/{handle}")
def get_creator_by_handle(handle: str):
    c = get_db().creators.find_one({"handle": handle.lstrip("@")})
    if not c:
        raise HTTPException(404, "Creator not found")
    return creator_view(c)


@router.get("/brands/{brand_id}")
def get_brand(brand_id: str):
    b = get_db().brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    return out(b)
