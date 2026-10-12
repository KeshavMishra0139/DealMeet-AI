"""The AI growth coach: questions about the signed-in creator's own numbers, and goals."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..services import auth as au
from ..services import coach, ratelimit
from ..services.creator_ctx import load_creator

router = APIRouter(prefix="/api", tags=["assistant"])

ASK_PER_HOUR = 30


def _creator(user: dict) -> dict:
    au.require_role(user, "creator")
    if not user.get("creator_id"):
        raise HTTPException(409, "Finish onboarding first.")
    return load_creator(user["creator_id"])


class AskIn(BaseModel):
    question: str = Field(min_length=2, max_length=300)
    lang: Literal["en", "hi"] = "en"


@router.post("/assistant/ask")
def ask(body: AskIn, user: dict = Depends(au.current_user)):
    """Answers from the caller's own data only, with the numbers used and their sources."""
    c = _creator(user)
    ratelimit.enforce(f"ask:{user['_id']}", ASK_PER_HOUR, 3600, "That's a lot of questions this hour. Try again a bit later.")
    return coach.ask(c, body.question, body.lang)


@router.get("/assistant/suggestions")
def suggestions(user: dict = Depends(au.current_user)):
    _creator(user)
    return {"questions": coach.SUGGESTED}


@router.post("/assistant/plan")
def make_plan(user: dict = Depends(au.current_user)):
    """Turns this week's moves into goals with a metric, a target and a deadline."""
    return coach.make_plan(_creator(user))


@router.get("/creators/{creator_id}/goals")
def goals(creator_id: str, _: dict = Depends(au.own_creator)):
    return {"plan": coach.plan_view(load_creator(creator_id))}
