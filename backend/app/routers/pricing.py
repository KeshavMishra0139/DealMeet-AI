"""The pricing form and saved rate cards."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from ..services import auth as au
from ..services import rates
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["pricing"])

Format = Literal["reel", "story", "carousel", "live", "short", "youtube_video"]


class TermsIn(BaseModel):
    count: int = Field(default=1, ge=1, le=10)
    usage_rights_days: int = Field(default=0, ge=0, le=365)
    exclusivity_days: int = Field(default=0, ge=0, le=365)


class EstimateIn(TermsIn):
    format: Format


class RateIn(TermsIn):
    amount: int = Field(ge=100, le=10_000_000)
    note: str | None = Field(default=None, max_length=140)


@router.get("/creators/{creator_id}/rates")
def get_rates(creator_id: str, _: dict = Depends(au.own_creator)):
    c = load_creator(creator_id)
    return {"cards": rates.cards(c), "formats": rates.formats_view(c)}


@router.get("/creators/{creator_id}/pricing/estimate")
def estimate(creator_id: str, q: Annotated[EstimateIn, Query()], _: dict = Depends(au.own_creator)):
    """The pricing form's estimate (read-only). It uses the metrics that exist and names
    the missing ones; nothing is filled in."""
    c = load_creator(creator_id)
    return rates.estimate(c, q.format, q.count, q.usage_rights_days, q.exclusivity_days)


@router.put("/creators/{creator_id}/rates/{fmt}")
def save_rate(creator_id: str, fmt: Format, body: RateIn, _: dict = Depends(au.own_creator)):
    c = load_creator(creator_id)
    note = body.note.strip() if body.note else None
    return rates.save_card(c, fmt, body.amount, body.count, body.usage_rights_days, body.exclusivity_days, note or None)


@router.delete("/creators/{creator_id}/rates/{fmt}")
def delete_rate(creator_id: str, fmt: Format, _: dict = Depends(au.own_creator)):
    if not rates.delete_card(load_creator(creator_id), fmt):
        raise HTTPException(404, "No saved rate for that format")
    return {"ok": True}
