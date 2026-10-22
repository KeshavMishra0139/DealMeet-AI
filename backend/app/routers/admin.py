"""Admin-only routes. The admin role is granted from the server (python -m app.admin_cli).

Every action needs a reason, and every action is audited with it."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field, StringConstraints

from ..db import get_db
from ..services import admin as adm
from ..services import auth as au
from ..services import brand_data as bd
from ..services import directory as dr
from ..services import totp


def require_admin(request: Request, user: dict = Depends(au.current_user)) -> dict:
    au.require_role(user, "admin")
    totp.require(user, request)  # this session passed two-step sign-in (services/totp.py)
    return user


router = APIRouter(prefix="/api/admin", tags=["admin"], dependencies=[Depends(require_admin)])

# Why. Saved with the decision and in the audit log.
Reason = Annotated[str, StringConstraints(strip_whitespace=True, min_length=5, max_length=300)]


class ReasonIn(BaseModel):
    reason: Reason


# ------------------------------------------------------------------ overview
@router.get("/overview")
def overview():
    return adm.overview()


# ------------------------------------------------------------------ accounts
@router.get("/accounts")
def accounts(
    q: str | None = Query(None, max_length=60),
    role: Literal["creator", "brand", "admin"] | None = None,
    suspended: bool | None = None,
):
    return {"items": adm.accounts(q, role, suspended)}


@router.post("/accounts/{user_id}/suspend")
def suspend(user_id: str, body: ReasonIn, admin: dict = Depends(require_admin)):
    """Suspending signs the account out everywhere."""
    return adm.set_suspended(user_id, True, body.reason, admin)


@router.post("/accounts/{user_id}/restore")
def restore(user_id: str, body: ReasonIn, admin: dict = Depends(require_admin)):
    return adm.set_suspended(user_id, False, body.reason, admin)


# ------------------------------------------------------------------ campaigns
@router.get("/campaigns")
def campaigns(status: Literal["draft", "live", "paused", "closed"] | None = None):
    return {"items": adm.campaigns(status)}


@router.post("/campaigns/{listing_id}/close")
def close_campaign(listing_id: str, body: ReasonIn, admin: dict = Depends(require_admin)):
    return adm.close_campaign(listing_id, body.reason, admin)


# ------------------------------------------------------------------ reports
@router.get("/reports")
def reports(status: Literal["open", "resolved"] = "open"):
    return {"items": adm.reports(status)}


class ResolveIn(BaseModel):
    resolution: Literal["action_taken", "no_action"]
    reason: Reason


@router.post("/reports/{report_id}/resolve")
def resolve_report(report_id: str, body: ResolveIn, admin: dict = Depends(require_admin)):
    return adm.resolve_report(report_id, body.resolution, body.reason, admin)


# ------------------------------------------------------------------ brand pages
class AdminUnclaimedIn(dr.UnclaimedIn):
    reason: Reason


@router.post("/brands")
def add_unclaimed(body: AdminUnclaimedIn, admin: dict = Depends(require_admin)):
    """List a brand that isn't on DealMeet AI: public name, category and public handles only."""
    return dr.add_unclaimed(body, admin, body.reason)


class ImportIn(BaseModel):
    csv: str = Field(min_length=1, max_length=200_000)
    dry_run: bool = True
    reason: Reason | None = None


@router.post("/brands/import")
def import_brands(body: ImportIn, admin: dict = Depends(require_admin)):
    """List many brands at once from a CSV of public facts (services/brand_data.py).
    A dry run checks every row and saves nothing."""
    if not body.dry_run and not body.reason:
        raise HTTPException(422, "Give a reason for the import. It's saved in the audit log.")
    return bd.run_import(body.csv, admin, body.reason or "", body.dry_run)


@router.get("/brand-invites")
def brand_invites(min_saves: int = Query(default=bd.INVITE_MIN_SAVES, ge=1, le=1000)):
    """Unclaimed brands that creators with connected accounts saved, and whether each can be invited now."""
    return bd.invite_candidates(min_saves)


@router.post("/brand-invites/{brand_id}")
def send_brand_invite(brand_id: str, body: ReasonIn, request: Request, admin: dict = Depends(require_admin)):
    """Emails the brand's public contact address once: who's interested, a claim link and
    an unsubscribe link. At most once every 30 days per brand."""
    return bd.send_invite(brand_id, admin, body.reason, str(request.base_url))


@router.get("/claims")
def claims(status: Literal["pending", "approved", "rejected"] = "pending"):
    return {"items": list(get_db().claim_requests.find({"status": status}).sort("at", 1))}


class DecideIn(BaseModel):
    action: Literal["approve", "reject"]
    reason: Reason


@router.post("/claims/{claim_id}")
def decide_claim(claim_id: str, body: DecideIn, admin: dict = Depends(require_admin)):
    return dr.decide_claim(claim_id, body.action == "approve", admin, body.reason)


@router.get("/removal-requests")
def removal_requests(status: Literal["pending", "removed", "kept"] = "pending"):
    return {"items": list(get_db().removal_requests.find({"status": status}).sort("at", 1))}


class RemovalDecision(BaseModel):
    action: Literal["remove", "keep"]
    reason: Reason


@router.post("/removal-requests/{request_id}")
def decide_removal(request_id: str, body: RemovalDecision, admin: dict = Depends(require_admin)):
    return dr.decide_removal(request_id, body.action == "remove", admin, body.reason)


# ------------------------------------------------------------------ audit log
def _ts(day: str | None, end: bool) -> float | None:
    if not day:
        return None
    try:
        d = datetime.fromisoformat(day)
    except ValueError:
        raise HTTPException(422, "Dates look like 2026-10-08.") from None
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.timestamp() + (86_400 if end and len(day) == 10 else 0)


@router.get("/audit")
def audit(
    action: str | None = Query(None, max_length=60, pattern=r"^[a-z_]*$"),
    user_id: str | None = Query(None, max_length=40),
    since: str | None = Query(None, max_length=25),
    until: str | None = Query(None, max_length=25),
    limit: int = Query(100, ge=1, le=500),
):
    """The append-only audit log, newest first. Secret-looking fields are redacted."""
    return {"items": adm.audit_log(action, user_id, _ts(since, False), _ts(until, True), limit)}
