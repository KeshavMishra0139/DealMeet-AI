"""Admin-only routes. The admin role is granted from the server (python -m app.admin_cli)."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from ..db import get_db
from ..services import auth as au
from ..services import directory as dr


def require_admin(user: dict = Depends(au.current_user)) -> dict:
    au.require_role(user, "admin")
    return user


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])


@router.post("/brands")
def add_unclaimed(body: dr.UnclaimedIn, admin: dict = Depends(require_admin)):
    """List a brand that isn't on JodiDar AI: public name, category and public handles only."""
    return dr.add_unclaimed(body, admin)


@router.get("/claims")
def claims(status: Literal["pending", "approved", "rejected"] = "pending"):
    return {"items": list(get_db().claim_requests.find({"status": status}).sort("at", 1))}


class DecideIn(BaseModel):
    action: Literal["approve", "reject"]


@router.post("/claims/{claim_id}")
def decide_claim(claim_id: str, body: DecideIn, admin: dict = Depends(require_admin)):
    return dr.decide_claim(claim_id, body.action == "approve", admin)


@router.get("/removal-requests")
def removal_requests(status: Literal["pending", "removed", "kept"] = "pending"):
    return {"items": list(get_db().removal_requests.find({"status": status}).sort("at", 1))}


class RemovalDecision(BaseModel):
    action: Literal["remove", "keep"]


@router.post("/removal-requests/{request_id}")
def decide_removal(request_id: str, body: RemovalDecision, admin: dict = Depends(require_admin)):
    return dr.decide_removal(request_id, body.action == "remove", admin)
