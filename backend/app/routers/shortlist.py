"""Brands acting on matches: a shortlist per campaign, compare, and offer drafts."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..db import get_db
from ..services import auth as au
from ..services import offers
from ..services import shortlist as sl

router = APIRouter(prefix="/api", tags=["shortlist"])


def _own(listing_id: str, user: dict) -> tuple[dict, dict]:
    """The campaign and its brand, for the brand that owns it."""
    au.require_role(user, "brand")
    db = get_db()
    x = db.listings.find_one({"_id": listing_id})
    if not x:
        raise HTTPException(404, "Campaign not found")
    au.require_listing_owner(user, x)
    brand = db.brands.find_one({"_id": x["owner_id"]})
    if not brand:
        raise HTTPException(404, "Brand not found")
    return x, brand


class NoteIn(BaseModel):
    note: str | None = Field(default=None, max_length=280)


@router.get("/campaigns/{listing_id}/shortlist")
def get_shortlist(listing_id: str, user: dict = Depends(au.current_user)):
    return sl.items(*_own(listing_id, user))


@router.put("/campaigns/{listing_id}/shortlist/{creator_id}")
def put_shortlist(listing_id: str, creator_id: str, body: NoteIn, user: dict = Depends(au.current_user)):
    """Add a creator to the shortlist, or change their note. Repeating it changes nothing else."""
    x, brand = _own(listing_id, user)
    return sl.add(x, brand, creator_id, body.note, user)


@router.delete("/campaigns/{listing_id}/shortlist/{creator_id}")
def delete_shortlist(listing_id: str, creator_id: str, user: dict = Depends(au.current_user)):
    x, brand = _own(listing_id, user)
    return sl.remove(x, brand, creator_id, user)


@router.get("/campaigns/{listing_id}/compare")
def compare(listing_id: str, ids: str = Query(min_length=3, max_length=200), user: dict = Depends(au.current_user)):
    """2 to 4 shortlisted creators side by side. Each counts as a profile view in their ledger."""
    x, brand = _own(listing_id, user)
    return sl.compare(x, brand, [i.strip() for i in ids.split(",") if i.strip()])


# ------------------------------------------------------------------ offer drafts
class DraftIn(BaseModel):
    creator_id: str = Field(min_length=3, max_length=40)
    amount: int | None = Field(default=None, ge=500, le=10_000_000)
    message: str | None = Field(default=None, max_length=400)


class DraftEdit(BaseModel):
    amount: int | None = Field(default=None, ge=500, le=10_000_000)
    message: str | None = Field(default=None, max_length=400)


class SendIn(BaseModel):
    confirm: bool


@router.get("/campaigns/{listing_id}/offer-drafts")
def get_drafts(listing_id: str, user: dict = Depends(au.current_user)):
    x, _ = _own(listing_id, user)
    return {"items": offers.list_drafts(x)}


@router.post("/campaigns/{listing_id}/offer-drafts")
def create_draft(listing_id: str, body: DraftIn, user: dict = Depends(au.current_user)):
    """A draft offer for a shortlisted creator, priced at the fair estimate unless set.
    Nothing is sent until the draft is confirmed."""
    x, brand = _own(listing_id, user)
    draft, created = offers.create_draft(x, brand, body.creator_id, body.amount, (body.message or "").strip() or None, user)
    return {**draft, "created": created}


@router.patch("/offer-drafts/{draft_id}")
def edit_draft(draft_id: str, body: DraftEdit, user: dict = Depends(au.current_user)):
    d = offers.own_draft(draft_id, user)
    ch = body.model_dump(exclude_unset=True)
    if "amount" in ch and ch["amount"] is None:
        raise HTTPException(422, "An offer needs an amount.")
    if "message" in ch:
        ch["message"] = (ch["message"] or "").strip() or None
    return offers.update_draft(d, ch, user)


@router.post("/offer-drafts/{draft_id}/send")
def send_draft(draft_id: str, body: SendIn, user: dict = Depends(au.current_user)):
    """Sends the draft as an offer, only with an explicit confirm."""
    d = offers.own_draft(draft_id, user)
    if not body.confirm:
        raise HTTPException(422, "Confirm to send this offer.")
    return offers.send_draft(d, user)


@router.delete("/offer-drafts/{draft_id}")
def discard_draft(draft_id: str, user: dict = Depends(au.current_user)):
    offers.discard_draft(offers.own_draft(draft_id, user), user)
    return {"ok": True}
