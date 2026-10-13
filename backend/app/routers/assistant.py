"""The AI growth coach (questions about the signed-in creator's own numbers, and goals)
and assistant actions (tools that run as the signed-in user, with confirmation)."""
from __future__ import annotations

import time
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..db import get_db
from ..services import assistant_tools as at
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
    lang: Literal["en", "hi", "hinglish", "ta", "te", "kn", "ml", "bn", "mr", "gu"] = "en"


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


# ------------------------------------------------------------------ actions (tools)
class ToolCallIn(BaseModel):
    args: dict = Field(default={})


class ActIn(BaseModel):
    message: str = Field(min_length=2, max_length=300)


@router.get("/assistant/tools")
def tools(user: dict = Depends(au.current_user)):
    return {"tools": at.tools_for(user)}


@router.post("/assistant/tools/{name}")
def call_tool(name: str, body: ToolCallIn, user: dict = Depends(au.current_user)):
    """Runs a read or draft tool, or returns a proposal to confirm for anything that sends,
    publishes or touches money."""
    ratelimit.enforce(f"tools:{user['_id']}", 60, 3600, "That's a lot of assistant actions this hour. Try again later.")
    return at.call(name, body.args, user)


@router.post("/assistant/act")
def act(body: ActIn, user: dict = Depends(au.current_user)):
    """Picks one tool for a message (the model only chooses and fills arguments)."""
    ratelimit.enforce(f"act:{user['_id']}", 30, 3600, "That's a lot of assistant requests this hour. Try again later.")
    return at.act(body.message.strip(), user)


@router.get("/assistant/proposals")
def proposals(user: dict = Depends(au.current_user)):
    rows = get_db().assistant_proposals.find({"user_id": user["_id"], "status": "pending", "expires_ts": {"$gte": time.time()}}).sort("created_at", -1)
    return {"items": [{"id": p["_id"], "tool": p["tool"], "summary": p["summary"], "expires_in_s": int(p["expires_ts"] - time.time())} for p in rows]}


@router.post("/assistant/proposals/{proposal_id}/confirm")
def confirm(proposal_id: str, user: dict = Depends(au.current_user)):
    return at.confirm(proposal_id, user)


@router.post("/assistant/proposals/{proposal_id}/cancel")
def cancel(proposal_id: str, user: dict = Depends(au.current_user)):
    return at.cancel(proposal_id, user)
