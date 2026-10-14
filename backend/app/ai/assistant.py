"""DealMeet AI: the assistant window for creators and brands.

One conversation window that answers like a person and does tasks. It replaces the
separate "Ask" (questions about your numbers) and "Assistant" (do something) buttons:

- Each turn sends the model the account's own data as context (creators: their numbers,
  price, moves, deals; brands: campaigns, deals, shortlists, only what creators share),
  the conversation so far and the tools it may use (services/assistant_tools.py).
- Read and draft tools run straight away; anything that sends, publishes or pauses
  becomes a proposal the user confirms in the window (it expires after 10 minutes).
- Every rupee amount in a reply must be one of the account's own amounts; replies that
  promise results or quote other amounts are asked again once, then answered from
  templates. Without AI the window still works, from templates and simple rules.
- Conversations are stored per account (`chats`) and deleted with the account.
"""
from __future__ import annotations

import json
import logging
import re
import secrets

from fastapi import HTTPException
from pydantic import BaseModel, Field

from ..config import now_iso
from ..db import get_db
from ..engines import metrics
from ..engines.common import inr, inr_range
from ..seed.catalog import LANGS, NICHES
from ..services import assistant_tools as at
from ..services import auth as au
from ..services import campaigns as camp
from .llm import converse

log = logging.getLogger("jodidar.ai")

HISTORY = 16  # messages the model sees
KEEP = 200  # messages kept per conversation
SHOWN = 80  # messages the window loads


class ChatAction(BaseModel):
    tool: str = Field(description="One tool name from the list")
    args_json: str = Field(default="{}", description='The tool\'s arguments as a JSON object, for example {"brand_id": "br_x"}. Use "{}" when it takes none.')


class ChatTurn(BaseModel):
    reply: str = Field(description="Your message to the user. Plain text in short paragraphs; **bold** and lines starting with '- ' for lists are fine.")
    action: ChatAction | None = Field(default=None, description="A tool to use for this reply, only when the user asked for that task; otherwise null")
    suggestions: list[str] = Field(default=[], description="Up to 3 short messages the user might send next, in their language")


STARTERS = {
    "creator": ["What should I charge a brand?", "Are my views growing?", "Draft a pitch to a brand that fits me", "What should I do this week?"],
    "brand": ["How are my campaigns doing?", "What needs my attention?", "Draft a campaign brief for a festive launch", "Who is on my shortlist?"],
}

TOOL_LABEL = {
    "explain_metric": "Looked up your numbers",
    "explain_price": "Looked up your price",
    "growth_plan": "Made a growth plan",
    "create_kit_version": "Saved a media kit version",
    "draft_pitch": "Drafted a pitch (not sent)",
    "send_pitch": "Send a pitch",
    "campaign_status": "Looked up a campaign",
    "draft_campaign_brief": "Drafted a campaign (hidden from creators)",
    "draft_offer": "Drafted an offer (not sent)",
    "send_offer": "Send an offer",
    "publish_campaign": "Publish a campaign",
    "pause_campaign": "Pause a campaign",
}


# ------------------------------------------------------------------ what the model knows
def _creator_context(user: dict) -> str:
    from ..engines.fair_price import fair_price
    from ..services import coach
    from ..services.creator_ctx import load_creator

    c = load_creator(user["creator_id"])
    db = get_db()
    facts, _ = coach.facts_for(c, "general")
    platform = metrics.platform(c)
    langs = ", ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS) or "not given"
    channels = [k for k in ("youtube", "instagram") if (c.get("channels") or {}).get(k)]
    lines = [
        f"Creator: {c['name']} (@{c.get('handle')}), {NICHES[c['niche']]['label']} on {platform.capitalize()}, languages {langs}, city {c.get('city') or c.get('region') or 'not given'}.",
        f"Connected accounts: {', '.join(channels) or 'none yet (numbers are typed in or sample data)'}.",
        "Their numbers (label: value [source]):",
        *[f"- {f['label']}: {f['value']} [{f['source']}]" for f in facts],
    ]
    fp = fair_price(c, None, with_model=False)
    steps = "; ".join(f"{s['label']} {'+' if s['amount'] >= 0 else ''}{inr(s['amount'])}" for s in fp["steps"])
    lines.append(f"Fair price for one {metrics.post_noun(c)}: {inr_range(fp['range']['low'], fp['range']['high'])} ({fp['data_label']}). Steps: {steps}.")
    review = fp.get("ai_review") or {}
    if review.get("status") == "applied":
        lines.append(f"AI market review on the price: {review['adjust_pct']:+d}%: {' '.join(review['reasons'])}")
    plan = db.plans.find_one({"creator_id": c["_id"]}, sort=[("week", -1)])
    if plan:
        lines.append("This week's moves: " + "; ".join(f"{m['title']} ({m['status']})" for m in plan["moves"]))
    drafts = list(db.pitches.find({"creator_id": c["_id"], "status": "draft"}, {"brand_name": 1, "subject": 1}).limit(10))
    if drafts:
        lines.append("Draft pitches (id: brand): " + "; ".join(f"{p['_id']}: {p['brand_name']}" for p in drafts))
    brands = list(db.brands.find({"niches": c["niche"], "removed": {"$ne": True}, "guest": {"$ne": True}}, {"name": 1}).limit(12))
    if brands:
        lines.append("Brands in their niche they could pitch (id: name): " + "; ".join(f"{b['_id']}: {b['name']}" for b in brands if not b["_id"].startswith("xx_")))
    return "\n".join(lines)


def _brand_context(user: dict) -> str:
    from ..routers.brands import console
    from ..services import shortlist

    db = get_db()
    bid = user["brand_id"]
    con = console(bid, {})
    b = con["brand"]
    lines = [
        f"Brand: {b.get('name')}, category {b.get('category') or 'not given'}, niches {', '.join(NICHES[n]['label'] for n in b.get('niches') or [] if n in NICHES) or 'not given'}.",
        f"Summary: {con['headline']}",
        "Campaigns (id: title, status, applications, deals, committed):",
        *[f"- {x['id']}: {x['title']}, {x['status']}, {x['applications']} applications, {x['deals']} deals, {inr(x['committed'])} committed" for x in con["campaigns"][:15]],
        "Deals by stage: " + "; ".join(f"{s['label']} {s['count']} ({inr(s['amount'])})" for s in con["stages"] if s["count"]),
    ]
    if con["needs_you"]:
        lines.append("Needs their attention: " + "; ".join(f"{n['text']} ({n['detail']})" for n in con["needs_you"][:8]))
    if con["recent"]:
        lines.append("Recent deals: " + "; ".join(f"{d['creator']}: {inr(d['amount'])}, {d['stage_label']}" for d in con["recent"][:8]))
    drafts = list(db.offer_drafts.find({"brand_id": bid, "status": "draft"}).limit(10))
    if drafts:
        names = {c["_id"]: c["name"] for c in db.creators.find({"_id": {"$in": [d["creator_id"] for d in drafts]}}, {"name": 1})}
        lines.append("Draft offers (id: creator, amount): " + "; ".join(f"{d['_id']}: {names.get(d['creator_id'], 'a creator')}, {inr(d['amount'])}" for d in drafts))
    brand = db.brands.find_one({"_id": bid}) or {}
    for x in db.listings.find({"owner_id": bid}):
        if camp.status_of(x) not in ("live", "draft"):
            continue
        rows = [r for r in shortlist.items(x, brand)["items"] if r.get("available")]
        if rows:
            lines.append(f"Shortlist for {x['title']} (creator id: name, fit, fair price): " + "; ".join(
                f"{r['id']}: {r['name']}, fit {r['fit']}, {inr_range(r['fair']['range']['low'], r['fair']['range']['high'])}" for r in rows[:10]))
    return "\n".join(lines)


def context_for(user: dict) -> str:
    return _brand_context(user) if user.get("role") == "brand" else _creator_context(user)


def _system(user: dict, context: str, ui_lang: str) -> str:
    role = user.get("role")
    who = "a brand team using the Brand Console" if role == "brand" else "a creator using the Creator Studio"
    tools = "\n".join(f"- {t['name']} ({t['mode']}): {t['description']} Arguments: {json.dumps(t['args'].get('properties', {}))}" for t in at.tools_for(user))
    return (
        "You are DealMeet AI, the assistant inside DealMeet, an Indian platform where creators and brands make fair, "
        f"escrow-backed deals. You are talking with {who}.\n\n"
        "How you talk: like a smart, warm friend who knows India's creator economy. Answer the question first, then add "
        "what helps. Natural, conversational, short paragraphs; **bold** sparingly and '- ' bullets for lists. No emojis, "
        "no exclamation marks, no hype. Reply in the language the user writes in (Hindi in Devanagari, Hinglish in Latin "
        f"letters, Tamil, Telugu and others in their own script); the app is shown in {'Hindi' if ui_lang == 'hi' else 'English'}. "
        "Write numbers in 0-9.\n\n"
        "What you know: the context below is this account's real data in DealMeet, with where each number comes from. "
        "When a number is sample or synthetic data, say so. Never invent a number about this account: if it isn't in the "
        "context, say you don't have it and where in the app to find or add it. Every rupee amount you write must be one "
        "from the context. For general advice you may use common knowledge of the creator economy, said as general advice. "
        "Never promise results: no promised income, reach, followers or deals.\n\n"
        "What you can do: answer questions, explain their numbers and price, give advice, and do tasks with the tools "
        "below. Read and draft tools run straight away; tools that send, publish or pause wait for the user to press "
        "Confirm in this window. Use at most one tool per reply, and only when the user asks for that task. Use ids from "
        "the context; if you only know a name, put the name and it will be looked up. Prices come from DealMeet's "
        "fair-price engine (a formula plus a capped AI review): you explain them, you never set them.\n\n"
        f"Tools:\n{tools}\n\nContext:\n{context}"
    )


# ------------------------------------------------------------------ checks
_AMOUNT = r"(\d[\d,]*(?:\.\d+)?)\s*(k|l|lakh|lakhs|cr|crore|crores)?\b"
# "₹7.3K", "Rs 1.2 lakh", and both ends of a range: "₹17K–18K", "₹1,500-2,200", "₹2.5L to ₹3L".
_MONEY = re.compile(rf"(?:₹|\brs\.?|\binr)\s*{_AMOUNT}(?:\s*(?:–|-|to)\s*(?:₹|\brs\.?|\binr)?\s*{_AMOUNT})?", re.IGNORECASE)
_SCALE = {"k": 1e3, "l": 1e5, "lakh": 1e5, "lakhs": 1e5, "cr": 1e7, "crore": 1e7, "crores": 1e7}


def _value(num: str, unit: str) -> float:
    return float(num.replace(",", "")) * _SCALE.get((unit or "").lower(), 1)


def _ranges(text: str) -> list[tuple[float, float]]:
    """Rupee amounts as (low, high): a single amount is (x, x); a range keeps both ends."""
    out = []
    for n1, u1, n2, u2 in _MONEY.findall(text):
        try:
            if n2:
                if not u1 and float(n1.replace(",", "")) <= float(n2.replace(",", "")):
                    u1 = u2
                lo, hi = sorted((_value(n1, u1), _value(n2, u2)))
                out.append((lo, hi))
            else:
                v = _value(n1, u1)
                out.append((v, v))
        except ValueError:
            continue
    return out


def rupees(text: str) -> list[float]:
    """Every rupee amount in a text, in rupees (₹17K -> 17000, Rs 1.2 lakh -> 120000, and
    both ends of ₹17K–18K)."""
    out = []
    for n1, u1, n2, u2 in _MONEY.findall(text):
        try:
            if n2:
                if not u1 and float(n1.replace(",", "")) <= float(n2.replace(",", "")):
                    u1 = u2  # "₹17–18K": the unit is written once (not "₹17,000 to ₹18K")
                out.append(_value(n2, u2))
            out.append(_value(n1, u1))
        except ValueError:
            continue
    return out


def money_grounded(reply: str, context: str) -> bool:
    """Every rupee amount in the reply is one of the context's, or inside one of its ranges
    ("about ₹2,100" for a ₹2,050–2,150 fair rate), within 2% for rounding."""
    known = _ranges(context)
    return all(any(lo * 0.98 - 1 <= a <= hi * 1.02 + 1 for lo, hi in known) for a in rupees(reply))


# ------------------------------------------------------------------ conversations
def _now_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_urlsafe(9)}"


def _owner(user: dict) -> dict:
    return {"creator_id": user.get("creator_id")} if user.get("role") == "creator" else {"brand_id": user.get("brand_id")}


def latest(user: dict) -> dict | None:
    return get_db().chats.find_one({"user_id": user["_id"]}, sort=[("updated_at", -1)])


def view(conv: dict | None) -> dict | None:
    if not conv:
        return None
    return {"id": conv["_id"], "title": conv.get("title"), "messages": conv["messages"][-SHOWN:], "updated_at": conv.get("updated_at")}


def _conversation(user: dict, conversation_id: str | None, first: str) -> dict:
    db = get_db()
    if conversation_id:
        conv = db.chats.find_one({"_id": conversation_id, "user_id": user["_id"]})
        if not conv:
            raise HTTPException(404, "Conversation not found")
        return conv
    conv = {"_id": _now_id("ch"), "user_id": user["_id"], "role": user.get("role"), **_owner(user), "title": first[:60],
            "messages": [], "created_at": now_iso(), "updated_at": now_iso()}
    db.chats.insert_one(conv)
    return conv


def _save(conv_id: str, *messages: dict) -> None:
    get_db().chats.update_one({"_id": conv_id}, {"$push": {"messages": {"$each": list(messages), "$slice": -KEEP}}, "$set": {"updated_at": now_iso()}})


def _history(conv: dict) -> list[dict]:
    """The conversation as model turns: actions taken are noted in the assistant's turn."""
    turns = []
    for m in conv["messages"][-HISTORY:]:
        text = m["text"]
        a = m.get("action")
        if a:
            text += f"\n[{a.get('label')}: {a.get('status')}]"
        turns.append({"role": "user" if m["role"] == "user" else "assistant", "content": text})
    while turns and turns[0]["role"] != "user":  # a conversation sent to the model starts with the user
        turns.pop(0)
    return turns


# ------------------------------------------------------------------ actions
def _resolve(name: str, args: dict, user: dict) -> dict:
    """Ids the model gave by name ("Thalam Foods") become the account's own ids."""
    db = get_db()
    out = dict(args)

    def pick(value, options):
        ids = {o[0] for o in options}
        if not value or value in ids:
            return value
        return at._match(str(value).lower(), options) or value

    if "brand_id" in out:
        out["brand_id"] = pick(out["brand_id"], [(b["_id"], b["name"]) for b in db.brands.find({"removed": {"$ne": True}, "guest": {"$ne": True}}, {"name": 1})])
    if "pitch_id" in out:
        out["pitch_id"] = pick(out["pitch_id"], [(p["_id"], p["brand_name"]) for p in db.pitches.find({"creator_id": user.get("creator_id"), "status": "draft"}, {"brand_name": 1})])
    if "listing_id" in out:
        out["listing_id"] = pick(out["listing_id"], [(x["_id"], x["title"]) for x in db.listings.find({"owner_id": user.get("brand_id")}, {"title": 1})])
    if "draft_id" in out:
        drafts = list(db.offer_drafts.find({"brand_id": user.get("brand_id"), "status": "draft"}))
        names = {c["_id"]: c["name"] for c in db.creators.find({"_id": {"$in": [d["creator_id"] for d in drafts]}}, {"name": 1})}
        out["draft_id"] = pick(out["draft_id"], [(d["_id"], names.get(d["creator_id"], "")) for d in drafts])
    if "creator_id" in out and name == "draft_offer":
        out["creator_id"] = pick(out["creator_id"], [(c["_id"], c["name"]) for c in db.creators.find({}, {"name": 1})])
    return out


# What a finished task means, when there's no AI to say it.
DONE = {
    "growth_plan": "Your plan is saved as goals on Home, each with a target and a deadline.",
    "draft_pitch": "Your pitch is drafted, not sent. Review it under Pitches.",
    "create_kit_version": "Saved: your media kit has a new version.",
    "draft_campaign_brief": "Drafted. Creators can't see it until you publish it.",
    "draft_offer": "Drafted, not sent. Review it on the campaign's shortlist.",
}

LINKS = {
    "draft_pitch": lambda r: "/creator/pitches",
    "send_pitch": lambda r: "/creator/pitches",
    "growth_plan": lambda r: "/creator",
    "create_kit_version": lambda r: "/creator/kit",
    "explain_price": lambda r: "/creator/money",
    "draft_campaign_brief": lambda r: f"/brand/campaigns/{r.get('id')}" if r.get("id") else "/brand/campaigns",
    "campaign_status": lambda r: f"/brand/campaigns/{r.get('id')}" if r.get("id") else "/brand/campaigns",
    "draft_offer": lambda r: "/brand/campaigns",
    "send_offer": lambda r: "/brand/deals",
    "publish_campaign": lambda r: f"/brand/campaigns/{r.get('id')}" if r.get("id") else "/brand/campaigns",
    "pause_campaign": lambda r: f"/brand/campaigns/{r.get('id')}" if r.get("id") else "/brand/campaigns",
}


def _run(name: str, args: dict, user: dict, via: str) -> tuple[dict, dict | None]:
    """(action record for the window, result for the model). Refusals become a record too."""
    label = TOOL_LABEL.get(name, name)
    try:
        out = at.call(name, _resolve(name, args, user), user, via=via)
    except HTTPException as e:
        return {"tool": name, "label": label, "status": "refused", "detail": str(e.detail)}, {"error": str(e.detail)}
    if out["mode"] == "confirm":
        return {"tool": name, "label": label, "status": "pending", "proposal": out["proposal"]}, None
    result = out.get("result") or {}
    link = LINKS.get(name)
    return {"tool": name, "label": label, "status": "done", "link": link(result) if link else None}, result


def _compact(result: dict) -> str:
    text = json.dumps(result, ensure_ascii=False, default=str)
    return text[:3500]


# ------------------------------------------------------------------ a turn
def _ask(system: str, turns: list[dict], context: str) -> tuple[ChatTurn | None, str]:
    """The model's reply, asked again once when it quotes a rupee amount that isn't the
    account's or breaks the copy rules."""
    turn, status = converse("assistant_chat", system, turns, ChatTurn)
    retry = None
    if status == "rules":
        retry = "Rewrite your last reply without promising results (income, reach, followers or deals)."
    elif turn and not money_grounded(turn.reply, context):
        retry = "Your reply quoted a rupee amount that isn't in the context. Rewrite it using only amounts from the context."
    if retry:
        turn, status = converse("assistant_chat", system, [*turns, {"role": "assistant", "content": (turn.reply if turn else "")}, {"role": "user", "content": f"(DealMeet check, not the user) {retry}"}], ChatTurn)
        if turn and not money_grounded(turn.reply, context):
            return None, "money"
    return turn, status


_GREETING = re.compile(r"^\s*(hi+|hello+|hey+|hiya|yo|hola|namaste|namaskar|vanakkam|good\s+(morning|afternoon|evening)|नमस्ते|नमस्कार|हेलो|हाय)\b[\s!.,?]*\w{0,12}[\s!.,?]*$", re.IGNORECASE)
_THANKS = re.compile(r"\b(thanks|thank\s+you|thx|ty|shukriya|dhanyavaad|dhanyavad|धन्यवाद|शुक्रिया)\b", re.IGNORECASE)
_HELP = re.compile(r"\b(who\s+are\s+you|what\s+(can|do)\s+you\s+do|how\s+can\s+you\s+help|help\s*me|^help$|what\s+are\s+you)\b", re.IGNORECASE)

CAN_DO = {
    "creator": "Ask me about your views, your fair price, earnings, deals or brands that fit you. I can also draft a pitch, make a growth plan or save your media kit. Anything that sends waits for your OK.",
    "brand": "Ask me how a campaign is doing, what needs your attention or who is on your shortlist. I can also draft a campaign brief or an offer, and publish, pause or send with your OK.",
}


def small_talk(user: dict, message: str) -> str | None:
    """Greetings, thanks and "what can you do?", answered warmly without the AI."""
    role = user.get("role", "creator")
    # A creator by first name; a brand account's name is usually the company's.
    first = (user.get("name") or "").split(" ")[0] if role == "creator" else ""
    if _GREETING.match(message):
        return f"Hi {first or 'there'}. I'm DealMeet AI, your assistant here.\n\n{CAN_DO[role]}\n\nWhat would you like to start with?"
    if _THANKS.search(message) and len(message) < 60:
        return "You're welcome. Anything else I can look at or do for you?"
    if _HELP.search(message):
        return f"I'm DealMeet AI. I know your {'numbers' if role == 'creator' else 'campaigns and deals'} in DealMeet and can do things for you.\n\n{CAN_DO[role]}"
    return None


def _template_reply(user: dict, message: str) -> tuple[str, list[str]]:
    """Without AI: greetings and small talk, the coach's template answers for creators, a
    summary for brands."""
    chat = small_talk(user, message)
    if chat:
        return chat, STARTERS[user.get("role", "creator")]
    if user.get("role") == "brand":
        from ..routers.brands import console

        con = console(user["brand_id"], {})
        needs = "; ".join(n["text"] for n in con["needs_you"][:3])
        return (con["headline"] + (f" Needs you: {needs}." if needs else "") +
                "\n\nI can draft a campaign brief, check a campaign, and publish, pause or send offers with your confirmation."), STARTERS["brand"]
    from ..services import coach
    from ..services.creator_ctx import load_creator

    c = load_creator(user["creator_id"])
    intent = coach.intent_of(message)
    _, raw = coach.facts_for(c, intent)
    a = coach._template(intent, c, raw)
    lead = "Here's where things stand.\n\n" if intent == "general" else ""
    text = lead + a.answer + (f"\n\n{a.uncertain}" if a.uncertain else "") + "".join(f"\n- {s}" for s in a.next_steps)
    return text, STARTERS["creator"]


def send(user: dict, message: str, conversation_id: str | None, ui_lang: str = "en") -> dict:
    message = message.strip()
    conv = _conversation(user, conversation_id, message)
    user_msg = {"id": _now_id("m"), "role": "user", "text": message, "at": now_iso()}
    conv["messages"].append(user_msg)
    context = context_for(user)
    system = _system(user, context, ui_lang)
    turns = _history(conv)
    turn, status = _ask(system, turns, context)
    action = None
    if turn:
        written_by = "ai"
        reply, suggestions = turn.reply.strip(), [s.strip()[:80] for s in turn.suggestions if s.strip()][:3]
        if turn.action and turn.action.tool in at.TOOLS and at.TOOLS[turn.action.tool].role == user.get("role"):
            try:
                args = json.loads(turn.action.args_json or "{}")
            except ValueError:
                args = {}
            action, result = _run(turn.action.tool, args if isinstance(args, dict) else {}, user, via="chat:ai")
            if result is not None:
                # The tool's result goes back to the model, which tells the user what it found or did.
                follow, _ = _ask(system, [*turns, {"role": "assistant", "content": reply},
                                          {"role": "user", "content": f"(Result of {turn.action.tool}, from DealMeet, not the user) {_compact(result)}\nNow reply to the user about it."}],
                                 context + "\n" + _compact(result))
                if follow:
                    reply = follow.reply.strip()
                    suggestions = [s.strip()[:80] for s in follow.suggestions if s.strip()][:3] or suggestions
                elif action["status"] == "refused":
                    reply = f"I couldn't do that: {action['detail']}"
    else:
        written_by = "template"
        rule = at._rules(message, user)
        if rule and at.TOOLS[rule[0]].mode == "read" and user.get("role") == "creator":
            rule = None  # a question: the coach's answer says more than "looked it up"
        if rule:
            action, result = _run(rule[0], rule[1], user, via="chat:rules")
            reply = {"pending": "Here it is. Nothing happens until you press Confirm.", "done": DONE.get(rule[0], "Done."),
                     "refused": f"I couldn't do that: {action.get('detail')}"}[action["status"]]
            if rule[0] == "campaign_status" and result:
                counts = ", ".join(f"{v} {k}" for k, v in (result.get("applications") or {}).items() if v) or "no applications yet"
                reply = f"“{result['title']}” is {result['status']}: {counts}."
            suggestions = STARTERS[user.get("role", "creator")]
        else:
            reply, suggestions = _template_reply(user, message)
        if status not in ("off",):
            log.info("Assistant answered from templates (%s)", status)
    msg = {"id": _now_id("m"), "role": "assistant", "text": reply, "at": now_iso(), "written_by": written_by,
           "ai_status": status if written_by == "template" else None, "suggestions": suggestions, "action": action}
    _save(conv["_id"], user_msg, msg)
    au.audit("assistant_chat", user["_id"], user.get("role"), conversation_id=conv["_id"], written_by=written_by, tool=(action or {}).get("tool"))
    return {"conversation_id": conv["_id"], "messages": [user_msg, msg]}


def settle(user: dict, conversation_id: str, proposal_id: str, confirm: bool) -> dict:
    """Confirms or cancels a proposal from the window, and notes the outcome in the conversation."""
    db = get_db()
    conv = db.chats.find_one({"_id": conversation_id, "user_id": user["_id"]})
    if not conv:
        raise HTTPException(404, "Conversation not found")
    if not any((m.get("action") or {}).get("proposal", {}).get("id") == proposal_id for m in conv["messages"]):
        raise HTTPException(404, "That action isn't in this conversation")
    if confirm:
        try:
            out = at.confirm(proposal_id, user)
            status, text = "done", "Done."
            link = LINKS.get(out["tool"])
            text = {"send_pitch": "Sent. The brand has your pitch now.", "send_offer": "Sent. The creator has your offer now.",
                    "publish_campaign": "Published. Matching creators can see it and apply.", "pause_campaign": "Paused. No new applications or offers until you resume it."}.get(out["tool"], text)
            extra = {"link": link(out.get("result") or {}) if link else None}
        except HTTPException as e:
            status, text, extra = "failed", f"That didn't go through: {e.detail}", {}
    else:
        at.cancel(proposal_id, user)
        status, text, extra = "cancelled", "Cancelled. Nothing was sent or changed.", {}
    db.chats.update_one({"_id": conversation_id, "messages.action.proposal.id": proposal_id},
                        {"$set": {"messages.$.action.status": status, **{f"messages.$.action.{k}": v for k, v in extra.items()}}})
    note = {"id": _now_id("m"), "role": "assistant", "text": text, "at": now_iso(), "written_by": "template", "suggestions": [], "action": None}
    _save(conversation_id, note)
    return view(db.chats.find_one({"_id": conversation_id}))


def clear(user: dict) -> int:
    return get_db().chats.delete_many({"user_id": user["_id"]}).deleted_count
