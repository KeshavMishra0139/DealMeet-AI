"""AI Pitch Builder (creators), share links (public) and the Brand Fan Inbox (brands)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..services import auth as au
from ..services import pitches as pt
from ..services import ratelimit
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["pitches"])


class NewPitch(BaseModel):
    brand_id: str = Field(min_length=3, max_length=40)
    lang: Literal["en", "hi"] = "en"


class PitchEdit(BaseModel):
    subject: str | None = Field(default=None, min_length=3, max_length=90)
    pitch: str | None = Field(default=None, min_length=20, max_length=1200)
    content_ideas: list[str] | None = Field(default=None, min_length=3, max_length=3)


@router.get("/creators/{creator_id}/pitches")
def list_pitches(creator_id: str, _: dict = Depends(au.own_creator)):
    rows = get_db().pitches.find({"creator_id": creator_id}).sort("created_at", -1)
    notes = list(get_db().notifications.find({"to": creator_id, "kind": "pitch_declined"}).sort("at", -1).limit(10))
    return {
        "items": [pt.view(p) for p in rows],
        "sent_this_week": pt.sent_this_week(creator_id),
        "per_week": pt.PER_WEEK,
        "notifications": [{"id": n["_id"], "text": n["text"], "at": n["at"], "pitch_id": n.get("pitch_id")} for n in notes],
    }


@router.post("/creators/{creator_id}/pitches")
def new_pitch(creator_id: str, body: NewPitch, user: dict = Depends(au.own_creator)):
    """Writes a draft pitch from your own numbers. Nothing is sent until you send it."""
    ratelimit.enforce(f"pitchgen:{creator_id}", 20, 3600, "That's a lot of drafts this hour. Edit one of them, or try again later.")
    return pt.create(load_creator(creator_id), body.brand_id, body.lang, user)


@router.patch("/creators/{creator_id}/pitches/{pitch_id}")
def edit_pitch(creator_id: str, pitch_id: str, body: PitchEdit, _: dict = Depends(au.own_creator)):
    return pt.edit(pt.own(pitch_id, creator_id), body.model_dump(exclude_none=True))


@router.post("/creators/{creator_id}/pitches/{pitch_id}/send")
def send_pitch(creator_id: str, pitch_id: str, user: dict = Depends(au.own_creator)):
    return pt.send(pt.own(pitch_id, creator_id), user)


@router.post("/creators/{creator_id}/pitches/{pitch_id}/revoke")
def revoke_pitch(creator_id: str, pitch_id: str, _: dict = Depends(au.own_creator)):
    return pt.revoke(pt.own(pitch_id, creator_id))


@router.delete("/creators/{creator_id}/pitches/{pitch_id}")
def delete_pitch(creator_id: str, pitch_id: str, _: dict = Depends(au.own_creator)):
    p = pt.own(pitch_id, creator_id)
    if p["status"] != "draft":
        raise HTTPException(409, "Only drafts can be deleted. Revoke a share link instead.")
    get_db().pitches.delete_one({"_id": pitch_id})
    return {"ok": True}


@router.get("/p/{slug}")
def shared_pitch(slug: str):
    """Public: a pitch the creator shared with a brand that isn't on DealMeet AI."""
    return pt.public(slug)


# ------------------------------------------------------------------ Brand Fan Inbox
@router.get("/brands/{brand_id}/fan-inbox")
def fan_inbox(brand_id: str, connected_only: bool = False, _: dict = Depends(au.own_brand)):
    b = get_db().brands.find_one({"_id": brand_id})
    if not b:
        raise HTTPException(404, "Brand not found")
    return pt.inbox(b, connected_only)


class AcceptIn(BaseModel):
    amount: int | None = Field(default=None, ge=500, le=10_000_000)


@router.post("/fan-inbox/{pitch_id}/accept")
def accept(pitch_id: str, body: AcceptIn, user: dict = Depends(au.current_user)):
    p, b = pt.own_received(pitch_id, user)
    return pt.accept(p, b, body.amount, user)


class DeclineIn(BaseModel):
    note: str | None = Field(default=None, max_length=300)


@router.post("/fan-inbox/{pitch_id}/decline")
def decline(pitch_id: str, body: DeclineIn, user: dict = Depends(au.current_user)):
    p, b = pt.own_received(pitch_id, user)
    return pt.decline(p, b, (body.note or "").strip() or None, user)
