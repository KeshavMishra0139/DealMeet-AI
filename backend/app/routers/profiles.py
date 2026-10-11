from fastapi import APIRouter, Depends, HTTPException

from ..db import get_db, out
from ..services.auth import own_brand, own_creator
from ..services.views import creator_view

router = APIRouter(prefix="/api", tags=["profiles"])


@router.get("/creators/{creator_id}")
def get_creator(creator_id: str, _: dict = Depends(own_creator)):
    c = get_db().creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    return creator_view(c)


@router.get("/brands/{brand_id}")
def get_brand(brand_id: str, _: dict = Depends(own_brand)):
    b = get_db().brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    return out(b)
