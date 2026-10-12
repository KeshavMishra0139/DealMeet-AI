"""Assistant actions: a small set of tools the assistant can use for the signed-in user.

- Each tool has a Pydantic argument model. Arguments are validated before anything
  runs, whether they came from the language model or the app.
- Tools act only as the session's user: creator and brand ids come from the session,
  never from arguments, and every tool runs the same ownership checks and service
  functions as the app's own endpoints. There is no database access beyond those and
  no admin tool.
- Read-only tools and drafts run directly. Sending offers or pitches and publishing or
  pausing a campaign return a proposal instead: nothing happens until the user
  confirms it. A proposal expires after 10 minutes and runs at most once.
- Every call, confirmation and cancellation is audited.
"""
from __future__ import annotations

import re
import secrets
import time
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException
from pydantic import BaseModel, Field, ValidationError

from ..ai.llm import generate
from ..config import now_iso
from ..db import get_db
from ..engines.common import inr, inr_range
from ..engines.fair_price import fair_price
from . import auth as au
from . import campaigns as camp
from . import coach, offers, pitches
from . import media_kit as mk
from .creator_ctx import load_creator

PROPOSAL_TTL_S = 600


# ------------------------------------------------------------------ argument models
class NoArgs(BaseModel):
    pass


class MetricArgs(BaseModel):
    metric: Literal["views", "engagement", "fair_rate", "trust", "brands"]


class PriceArgs(BaseModel):
    brand_id: str | None = Field(default=None, max_length=40)


class KitVersionArgs(BaseModel):
    headline: str = Field(min_length=3, max_length=120)
    bio: str = Field(default="", max_length=420)
    lang: Literal["en", "hi"] = "en"


class PitchArgs(BaseModel):
    brand_id: str = Field(min_length=3, max_length=40)
    lang: Literal["en", "hi"] = "en"


class PitchIdArgs(BaseModel):
    pitch_id: str = Field(min_length=3, max_length=40)


class ListingArgs(BaseModel):
    listing_id: str = Field(min_length=3, max_length=60)


class BriefArgs(BaseModel):
    title: str = Field(min_length=4, max_length=90)
    summary: str | None = Field(default=None, max_length=400)
    niches: list[str] | None = Field(default=None, max_length=12)
    languages: list[str] | None = Field(default=None, max_length=10)
    budget_min: int | None = Field(default=None, ge=0, le=100_000_000)
    budget_max: int | None = Field(default=None, ge=0, le=100_000_000)
    deadline: str | None = Field(default=None, max_length=10)


class DraftOfferArgs(BaseModel):
    listing_id: str = Field(min_length=3, max_length=60)
    creator_id: str = Field(min_length=3, max_length=40)
    amount: int | None = Field(default=None, ge=500, le=10_000_000)


class DraftIdArgs(BaseModel):
    draft_id: str = Field(min_length=3, max_length=120)


# ------------------------------------------------------------------ the tools
def _creator(user: dict) -> dict:
    au.require_role(user, "creator")
    au.require_creator(user, user.get("creator_id") or "")
    return load_creator(user["creator_id"])


def _brand(user: dict) -> dict:
    au.require_role(user, "brand")
    au.require_brand(user, user.get("brand_id") or "")
    b = get_db().brands.find_one({"_id": user["brand_id"]})
    if not b:
        raise HTTPException(409, "Set up your brand profile first.")
    return b


def _own_listing(user: dict, listing_id: str) -> dict:
    _brand(user)
    x = get_db().listings.find_one({"_id": listing_id})
    if not x:
        raise HTTPException(404, "Campaign not found")
    au.require_listing_owner(user, x)
    return x


METRIC_QUESTIONS = {
    "views": "Are my views growing?",
    "engagement": "How is my engagement?",
    "fair_rate": "What should I charge for a reel?",
    "trust": "What is my trust score?",
    "brands": "Which brands fit me now?",
}


def t_explain_metric(user: dict, a: MetricArgs) -> dict:
    return coach.ask(_creator(user), METRIC_QUESTIONS[a.metric])


def t_explain_price(user: dict, a: PriceArgs) -> dict:
    c = _creator(user)
    b = get_db().brands.find_one({"_id": a.brand_id}) if a.brand_id else None
    if a.brand_id and not b:
        raise HTTPException(404, "Brand not found")
    fp = fair_price(c, b if b and b.get("target") else None, None, with_model=False)
    return {"range": fp["range"], "label": inr_range(fp["range"]["low"], fp["range"]["high"]), "data_label": fp["data_label"],
            "for": (b or {}).get("name"), "steps": [{"label": s["label"], "amount": s["amount"], "reason": s["reason"]} for s in fp["steps"]],
            "note": "An estimate, not a quote."}


def t_growth_plan(user: dict, a: NoArgs) -> dict:
    return coach.make_plan(_creator(user))


def t_create_kit_version(user: dict, a: KitVersionArgs) -> dict:
    summary, created = mk.create_version(_creator(user), mk.VersionIn(headline=a.headline, bio=a.bio, lang=a.lang))
    return {**summary, "created": created}


def t_draft_pitch(user: dict, a: PitchArgs) -> dict:
    return pitches.create(_creator(user), a.brand_id, a.lang, user)


def t_send_pitch(user: dict, a: PitchIdArgs) -> dict:
    c = _creator(user)
    return pitches.send(pitches.own(a.pitch_id, c["_id"]), user)


def t_campaign_status(user: dict, a: ListingArgs) -> dict:
    x = _own_listing(user, a.listing_id)
    apps = camp.applications(x)
    return {"id": x["_id"], "title": x["title"], "status": camp.status_of(x), "missing": camp.missing(x) if camp.status_of(x) == "draft" else [],
            "applications": apps["counts"], "deadline": x.get("deadline")}


def t_draft_campaign_brief(user: dict, a: BriefArgs) -> dict:
    from ..routers.brands import CampaignIn, create_campaign

    b = _brand(user)
    body = CampaignIn(**a.model_dump(exclude_none=True))
    return create_campaign(b["_id"], body, user=user)


def t_draft_offer(user: dict, a: DraftOfferArgs) -> dict:
    x = _own_listing(user, a.listing_id)
    draft, created = offers.create_draft(x, _brand(user), a.creator_id, a.amount, None, user)
    return {**draft, "created": created}


def t_send_offer(user: dict, a: DraftIdArgs) -> dict:
    _brand(user)
    return offers.send_draft(offers.own_draft(a.draft_id, user), user)


def t_publish(user: dict, a: ListingArgs) -> dict:
    x, changed = camp.transition(_own_listing(user, a.listing_id), "publish", user)
    return {"id": x["_id"], "status": camp.status_of(x), "changed": changed}


def t_pause(user: dict, a: ListingArgs) -> dict:
    x, changed = camp.transition(_own_listing(user, a.listing_id), "pause", user)
    return {"id": x["_id"], "status": camp.status_of(x), "changed": changed}


# Checks a confirm tool runs when the proposal is made, so the user hears "no" before confirming.
def p_send_pitch(user: dict, a: PitchIdArgs) -> str:
    p = pitches.own(a.pitch_id, _creator(user)["_id"])
    if p["status"] != "draft":
        raise HTTPException(409, "That pitch was already sent.")
    return f"Send your pitch “{p['subject']}” to {p['brand_name']}" + ("" if p.get("on_platform", True) else " (as a share link you send yourself)")


def p_send_offer(user: dict, a: DraftIdArgs) -> str:
    _brand(user)
    d = offers.own_draft(a.draft_id, user)
    if d["status"] != "draft":
        raise HTTPException(409, "That offer was already sent.")
    c = get_db().creators.find_one({"_id": d["creator_id"]}, {"name": 1}) or {}
    x = get_db().listings.find_one({"_id": d["listing_id"]}, {"title": 1}) or {}
    return f"Send a {inr(d['amount'])} offer to {c.get('name', 'the creator')} for “{x.get('title', 'your campaign')}”"


def p_publish(user: dict, a: ListingArgs) -> str:
    x = _own_listing(user, a.listing_id)
    if camp.status_of(x) != "draft":
        raise HTTPException(409, f"That campaign is {camp.status_of(x)}, not a draft.")
    return f"Publish “{x['title']}” so matching creators can see it and apply"


def p_pause(user: dict, a: ListingArgs) -> str:
    x = _own_listing(user, a.listing_id)
    if camp.status_of(x) != "live":
        raise HTTPException(409, f"That campaign is {camp.status_of(x)}, not live.")
    return f"Pause “{x['title']}”: no new applications or offers until you resume it"


@dataclass(frozen=True)
class Tool:
    name: str
    role: str
    mode: Literal["read", "draft", "confirm"]
    args: type[BaseModel]
    run: Callable[[dict, Any], dict]
    describe: str
    preview: Callable[[dict, Any], str] | None = None


TOOLS: dict[str, Tool] = {
    t.name: t
    for t in [
        Tool("explain_metric", "creator", "read", MetricArgs, t_explain_metric, "Explain one of your numbers (views, engagement, fair rate, trust, brands that fit)."),
        Tool("explain_price", "creator", "read", PriceArgs, t_explain_price, "Explain your fair price, optionally for one brand."),
        Tool("growth_plan", "creator", "draft", NoArgs, t_growth_plan, "Make a growth plan with measurable goals."),
        Tool("create_kit_version", "creator", "draft", KitVersionArgs, t_create_kit_version, "Save your media kit as a new version with a headline."),
        Tool("draft_pitch", "creator", "draft", PitchArgs, t_draft_pitch, "Draft a pitch to a brand (not sent)."),
        Tool("send_pitch", "creator", "confirm", PitchIdArgs, t_send_pitch, "Send one of your draft pitches.", p_send_pitch),
        Tool("campaign_status", "brand", "read", ListingArgs, t_campaign_status, "Get one of your campaign's status, what's missing and applications."),
        Tool("draft_campaign_brief", "brand", "draft", BriefArgs, t_draft_campaign_brief, "Draft a campaign brief (saved as a draft, hidden from creators)."),
        Tool("draft_offer", "brand", "draft", DraftOfferArgs, t_draft_offer, "Draft an offer to a shortlisted creator (not sent)."),
        Tool("send_offer", "brand", "confirm", DraftIdArgs, t_send_offer, "Send one of your draft offers.", p_send_offer),
        Tool("publish_campaign", "brand", "confirm", ListingArgs, t_publish, "Publish one of your draft campaigns.", p_publish),
        Tool("pause_campaign", "brand", "confirm", ListingArgs, t_pause, "Pause one of your live campaigns.", p_pause),
    ]
}


def tools_for(user: dict) -> list[dict]:
    return [{"name": t.name, "mode": t.mode, "description": t.describe, "args": t.args.model_json_schema()} for t in TOOLS.values() if t.role == user.get("role")]


def _validate(tool: Tool, user: dict, args: dict) -> BaseModel:
    if tool.role != user.get("role"):
        raise HTTPException(403, f"That tool is for {tool.role} accounts.")
    try:
        return tool.args.model_validate(args or {})
    except ValidationError as e:
        problems = "; ".join(f"{'.'.join(str(p) for p in err['loc']) or 'arguments'}: {err['msg']}" for err in e.errors()[:3])
        raise HTTPException(422, f"Those arguments aren't valid for {tool.name}: {problems}") from e


def call(name: str, args: dict, user: dict, via: str = "app") -> dict:
    """Run a read or draft tool, or make a proposal for a confirm tool."""
    tool = TOOLS.get(name)
    if not tool:
        raise HTTPException(404, "Unknown tool")
    a = _validate(tool, user, args)
    if tool.mode == "confirm":
        summary = tool.preview(user, a) if tool.preview else tool.describe
        pid = f"ap_{secrets.token_urlsafe(12)}"
        get_db().assistant_proposals.insert_one({
            "_id": pid, "user_id": user["_id"], "tool": name, "args": a.model_dump(), "summary": summary,
            "status": "pending", "created_at": now_iso(), "expires_ts": time.time() + PROPOSAL_TTL_S,
        })
        au.audit("assistant_tool", user["_id"], user.get("role"), tool=name, mode="proposal", proposal_id=pid, via=via)
        return {"tool": name, "mode": "confirm", "proposal": {"id": pid, "summary": summary, "expires_in_s": PROPOSAL_TTL_S}}
    try:
        result = tool.run(user, a)
    except HTTPException as e:
        au.audit("assistant_tool", user["_id"], user.get("role"), tool=name, mode=tool.mode, outcome=f"refused {e.status_code}", via=via)
        raise
    au.audit("assistant_tool", user["_id"], user.get("role"), tool=name, mode=tool.mode, outcome="ok", via=via)
    return {"tool": name, "mode": tool.mode, "result": result}


def confirm(proposal_id: str, user: dict) -> dict:
    """Runs a pending proposal, once, if it belongs to this user and hasn't expired."""
    db = get_db()
    p = db.assistant_proposals.find_one({"_id": proposal_id})
    if not p or p["user_id"] != user["_id"]:
        raise HTTPException(404, "Proposal not found")
    if p["status"] == "pending" and p["expires_ts"] < time.time():
        db.assistant_proposals.update_one({"_id": proposal_id, "status": "pending"}, {"$set": {"status": "expired"}})
        p["status"] = "expired"
    if p["status"] == "expired":
        raise HTTPException(410, "That proposal expired. Ask again to make a new one.")
    # Claim it: only one confirmation can move it out of pending.
    res = db.assistant_proposals.update_one({"_id": proposal_id, "status": "pending", "expires_ts": {"$gte": time.time()}}, {"$set": {"status": "running"}})
    if not res.modified_count:
        raise HTTPException(409, f"That proposal was already {db.assistant_proposals.find_one({'_id': proposal_id})['status']}.")
    tool = TOOLS[p["tool"]]
    try:
        result = tool.run(user, tool.args.model_validate(p["args"]))  # the same checks run again now
    except HTTPException as e:
        db.assistant_proposals.update_one({"_id": proposal_id}, {"$set": {"status": "failed", "error": e.detail, "done_at": now_iso()}})
        au.audit("assistant_confirm", user["_id"], user.get("role"), proposal_id=proposal_id, tool=p["tool"], outcome=f"failed {e.status_code}")
        raise
    db.assistant_proposals.update_one({"_id": proposal_id}, {"$set": {"status": "done", "done_at": now_iso()}})
    au.audit("assistant_confirm", user["_id"], user.get("role"), proposal_id=proposal_id, tool=p["tool"], outcome="done")
    return {"tool": p["tool"], "mode": "confirmed", "result": result}


def cancel(proposal_id: str, user: dict) -> dict:
    db = get_db()
    p = db.assistant_proposals.find_one({"_id": proposal_id})
    if not p or p["user_id"] != user["_id"]:
        raise HTTPException(404, "Proposal not found")
    res = db.assistant_proposals.update_one({"_id": proposal_id, "status": "pending"}, {"$set": {"status": "cancelled"}})
    if res.modified_count:
        au.audit("assistant_cancel", user["_id"], user.get("role"), proposal_id=proposal_id, tool=p["tool"])
    return {"id": proposal_id, "status": db.assistant_proposals.find_one({"_id": proposal_id})["status"]}


# ------------------------------------------------------------------ choosing a tool from a message
class ToolChoice(BaseModel):
    tool: str = Field(max_length=40)
    args: dict[str, str | int | bool | list[str] | None] = {}


def _match(text: str, options: list[tuple[str, str]]) -> str | None:
    """The id whose name shares the most words with the message."""
    words = set(re.findall(r"[a-z0-9]{3,}", text))
    best, score = None, 0
    for oid, name in options:
        s = len(words & set(re.findall(r"[a-z0-9]{3,}", name.lower())))
        if s > score:
            best, score = oid, s
    return best


def _rules(message: str, user: dict) -> tuple[str, dict] | None:
    """A plain fallback router for when no language model is configured."""
    m = message.lower()
    db = get_db()
    if user.get("role") == "brand":
        mine = list(db.listings.find({"owner_id": user.get("brand_id")}, {"title": 1, "status": 1}))
        named = [(x["_id"], x["title"]) for x in mine]
        pick = _match(m, named)
        if "publish" in m:
            drafts = [x["_id"] for x in mine if x.get("status") == "draft"]
            lid = pick if pick in drafts else (drafts[0] if len(drafts) == 1 else pick)
            return ("publish_campaign", {"listing_id": lid}) if lid else None
        if "pause" in m:
            live = [x["_id"] for x in mine if camp.status_of(x) == "live"]
            lid = pick if pick in live else (live[0] if len(live) == 1 else pick)
            return ("pause_campaign", {"listing_id": lid}) if lid else None
        if "send" in m and "offer" in m:
            drafts = list(db.offer_drafts.find({"brand_id": user.get("brand_id"), "status": "draft"}))
            names = [(d["_id"], (db.creators.find_one({"_id": d["creator_id"]}, {"name": 1}) or {}).get("name", "")) for d in drafts]
            did = _match(m, names) or (drafts[0]["_id"] if len(drafts) == 1 else None)
            return ("send_offer", {"draft_id": did}) if did else None
        if "brief" in m or "new campaign" in m:
            title = message.split(":", 1)[1].strip() if ":" in message else "New campaign"
            return "draft_campaign_brief", {"title": title if len(title) >= 4 else "New campaign"}
        if pick and ("status" in m or "how is" in m or "how's" in m):
            return "campaign_status", {"listing_id": pick}
        return None
    if "send" in m and "pitch" in m:
        drafts = list(db.pitches.find({"creator_id": user.get("creator_id"), "status": "draft"}))
        pid = _match(m, [(p["_id"], p["brand_name"]) for p in drafts]) or (drafts[0]["_id"] if len(drafts) == 1 else None)
        return ("send_pitch", {"pitch_id": pid}) if pid else None
    if "pitch" in m:
        brands = [(b["_id"], b["name"]) for b in db.brands.find({"removed": {"$ne": True}, "guest": {"$ne": True}}, {"name": 1}) if not b["_id"].startswith("xx_")]
        bid = _match(m, brands)
        return ("draft_pitch", {"brand_id": bid, "lang": "hi" if "hindi" in m else "en"}) if bid else None
    if "plan" in m:
        return "growth_plan", {}
    if "kit" in m and "version" in m:
        c = load_creator(user["creator_id"])
        return "create_kit_version", {"headline": mk.build_kit(c)["copy"]["headline"]}
    if any(w in m for w in ("price", "charge", "rate")):
        brands = [(b["_id"], b["name"]) for b in db.brands.find({"claimed": {"$ne": False}}, {"name": 1})]
        return "explain_price", {"brand_id": _match(m, brands)}
    for word, metric in (("view", "views"), ("engag", "engagement"), ("trust", "trust"), ("brand", "brands")):
        if word in m:
            return "explain_metric", {"metric": metric}
    return None


def choose(message: str, user: dict) -> tuple[str, dict, str] | None:
    """(tool, args, chosen_by). The model only picks a tool and fills arguments."""
    db = get_db()
    context = ""
    if user.get("role") == "brand":
        context = "Your campaigns: " + "; ".join(f"{x['_id']} = {x['title']} ({camp.status_of(x)})" for x in db.listings.find({"owner_id": user.get("brand_id")}))
        context += "\nYour draft offers: " + "; ".join(f"{d['_id']} to {d['creator_id']} for {d['listing_id']}" for d in db.offer_drafts.find({"brand_id": user.get("brand_id"), "status": "draft"}))
    else:
        context = "Your draft pitches: " + "; ".join(f"{p['_id']} to {p['brand_name']} ({p['brand_id']})" for p in db.pitches.find({"creator_id": user.get("creator_id"), "status": "draft"}))
    catalog = "\n".join(f"- {t['name']} ({t['mode']}): {t['description']} Args schema: {t['args'].get('properties', {})}" for t in tools_for(user))
    prompt = (
        f"Tools:\n{catalog}\n\n{context}\n\nUser message: {message}\n\n"
        "Pick the one tool that does what the user asks and fill its arguments using only ids listed above. "
        "If no tool fits, answer with tool \"none\"."
    )
    rule = _rules(message, user)

    def fallback() -> ToolChoice:
        return ToolChoice(tool=rule[0], args=rule[1]) if rule else ToolChoice(tool="none")

    pick, how = generate("assistant_route", prompt, ToolChoice, fallback, max_tokens=300)
    if pick.tool == "none" or pick.tool not in TOOLS:
        return None
    return pick.tool, dict(pick.args), "ai" if how in ("ai", "cache") else "rules"


def act(message: str, user: dict) -> dict:
    picked = choose(message, user)
    if not picked:
        au.audit("assistant_tool", user["_id"], user.get("role"), tool=None, mode="none", via="message")
        return {"tool": None, "reply": "I can't do that one. Try one of the suggestions, or do it from the app."}
    name, args, how = picked
    return {**call(name, args, user, via=f"message:{how}"), "args": args, "chosen_by": how}
