"""Report a campaign, profile, pitch or deal to the admins. Signed-in users only, a few a day."""
from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field, StringConstraints

from ..services import admin as adm
from ..services import auth as au

router = APIRouter(prefix="/api", tags=["reports"])


class ReportIn(BaseModel):
    target_type: Literal["campaign", "profile", "pitch", "deal"]
    target_id: str = Field(min_length=2, max_length=40, pattern=r"^[A-Za-z0-9_-]+$")
    reason: Literal[adm.REPORT_REASONS]  # type: ignore[valid-type]
    details: Annotated[str, StringConstraints(strip_whitespace=True, max_length=500)] | None = None


@router.post("/reports")
def file_report(body: ReportIn, user: dict = Depends(au.current_user)):
    """Deals can be reported only by their creator or brand. Duplicates return the open report."""
    return adm.report(user, body.target_type, body.target_id, body.reason, body.details or None)
