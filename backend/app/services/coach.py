"""The AI growth coach: answers about the signed-in creator's own numbers.

- Data comes only from the functions below, each scoped to one creator record that
  the route has already checked belongs to the caller. Nothing the model writes is
  ever run as a query.
- The model (ai/llm.py `generate`) only phrases an answer from a fixed list of facts.
  Its output is validated by Pydantic, checked against the copy rules and must use
  only numbers that are in the facts; otherwise the template answer is used.
- Every answer lists the numbers it used with their source (Live data,
  Self-reported, Sample data) and says what's uncertain. With fewer than 6 posts it
  says it can't tell a trend. It never promises growth or earnings.
- "Make me a plan" attaches measurable goals (metric, target, deadline) to the
  current weekly plan; progress is read from the creator's own data, and when new
  data arrives the plan is recalculated and records what changed.
"""
from __future__ import annotations

import hashlib
import json
import re
from datetime import date, timedelta
from statistics import median

from pydantic import BaseModel, Field

from ..ai.llm import generate
from ..config import now_iso, today
from ..db import get_db
from ..engines import metrics
from ..engines.common import inr, inr_range, short
from ..engines.opportunities import matched
from . import creator_ctx as cc
from .views import source_of

INTENTS = {
    "trend": r"grow|growth|trend|views|reach|going|improv|declin|drop|better|worse",
    "price": r"charge|rate|price|quote|fee|worth|pay me",
    "earnings": r"earn|income|money|made|revenue|month",
    "opportunities": r"brand|opportunit|campaign|collab|match|apply|work with",
    "deals": r"deal|offer|payment|paid|escrow|invoice|counter",
}
SUGGESTED = ["Are my views growing?", "What should I charge for a reel?", "How much have I earned lately?", "Which brands fit me now?", "Where are my deals?"]


class CoachAnswer(BaseModel):
    answer: str = Field(max_length=700)
    uncertain: str = Field(max_length=300)
    next_steps: list[str] = Field(default=[], max_length=3)


def intent_of(question: str) -> str:
    q = question.lower()
    for name, rx in INTENTS.items():
        if re.search(rx, q):
            return name
    return "general"


# ------------------------------------------------------------------ facts (scoped to one creator)
def _fact(key: str, label: str, value: str, source: str) -> dict:
    return {"key": key, "label": label, "value": value, "source": source}


def views_trend(c: dict) -> dict:
    """Last 3 posts against the 3 before. Needs 6 posts; otherwise no trend."""
    r = metrics.recent(c, 6)
    if len(r) < 6:
        return {"enough": False, "posts": len(r)}
    newer = median(x["views"] for x in r[:3])
    older = median(x["views"] for x in r[3:6])
    change = (newer - older) / older if older else 0.0
    return {"enough": True, "posts": 6, "newer": newer, "older": older, "change": change}


def facts_for(c: dict, intent: str) -> tuple[list[dict], dict]:
    """The facts an answer may use, with their sources, plus raw values for templates."""
    reels_src = source_of(c, "reels")
    raw: dict = {"trend": views_trend(c)}
    facts = [_fact("followers", "Followers", short(c.get("followers") or 0), source_of(c, "followers"))]
    if metrics.has_reels(c):
        facts.append(_fact("median_views", "Median views, last 6 posts", short(metrics.median_views(c)), reels_src))
    t = raw["trend"]
    if t["enough"]:
        facts.append(_fact("trend", "Median views, last 3 vs the 3 before", f"{short(t['newer'])} vs {short(t['older'])}", reels_src))
    if intent in ("price", "general", "deals"):
        ctx = cc.build(c, with_plan=False)
        fair = ctx["fair"]
        raw["fair"] = fair
        facts.append(_fact("fair", "Fair rate per reel (estimate)", inr_range(fair["range"]["low"], fair["range"]["high"]), fair.get("data_source", reels_src)))
        if c.get("current_rate"):
            facts.append(_fact("rate", "Your typical rate", inr(c["current_rate"]), source_of(c, "current_rate")))
    if intent in ("earnings", "general"):
        hist = [h for h in c.get("income_history") or [] if h.get("amount", 0) > 0]
        cutoff = (today() - timedelta(days=92)).isoformat()
        last3 = [h for h in hist if (h.get("month") or h.get("date") or "") >= cutoff[:7]]
        total = sum(h["amount"] for h in last3)
        raw["earnings"] = {"total": total, "count": len(last3)}
        facts.append(_fact("earnings", "Income logged, last 3 months", inr(total), source_of(c, "income_history")))
    if intent in ("opportunities", "general"):
        items = matched(c)["items"]
        raw["opportunities"] = items[:3]
        facts.append(_fact("opportunities", "Open opportunities that fit you", str(len(items)), "synthetic" if c.get("insights_source") == "synthetic" else "manual"))
        if items:
            facts.append(_fact("top_opportunity", "Best fit", f"{items[0]['title']} (fit {items[0]['fit']})", "manual"))
    if intent in ("deals", "general"):
        p = cc.pipeline(c)
        raw["pipeline"] = p
        facts.append(_fact("deals", "Deals: offers, active, awaiting payout", f"{len(p['offers'])}, {len(p['active'])}, {len(p['awaiting'])}", "manual"))
    return facts, raw


# ------------------------------------------------------------------ answers
def _template(intent: str, c: dict, raw: dict) -> CoachAnswer:
    t = raw["trend"]
    trend_line = (
        f"I can't tell a trend yet: there are only {t['posts']} posts to compare, and I need 6."
        if not t["enough"]
        else (
            f"Your last 3 posts have a median of {short(t['newer'])} views, against {short(t['older'])} for the 3 before"
            + (" — about the same." if abs(t["change"]) < 0.1 else f": {'up' if t['change'] > 0 else 'down'} about {abs(round(t['change'] * 100))}%.")
        )
    )
    uncertain = "Views swing a lot from post to post, and 6 posts is a small sample." if t["enough"] else "With fewer than 6 posts, any trend would be a guess."
    if intent == "trend":
        nxt = ["Post at least 2 reels this week so there's more to compare."] if not t["enough"] else ["Repeat the format of your best recent post and compare next week."]
        return CoachAnswer(answer=trend_line, uncertain=uncertain, next_steps=nxt)
    if intent == "price":
        f = raw["fair"]
        rate = f" Your typical rate is {inr(c['current_rate'])}." if c.get("current_rate") else ""
        return CoachAnswer(
            answer=f"Your fair rate is about {inr_range(f['range']['low'], f['range']['high'])} a reel ({f.get('data_label', 'estimate').lower()}), priced on your median views, not your followers.{rate}",
            uncertain="It's an estimate: the brand's budget, deliverables and usage rights change the final number.",
            next_steps=["Open Money to see each step of the price.", "Counter low offers at the fair rate, with its reasons."],
        )
    if intent == "earnings":
        e = raw["earnings"]
        return CoachAnswer(
            answer=f"You've logged {inr(e['total'])} across {e['count']} payments in the last 3 months." if e["count"] else "There's no income logged for the last 3 months.",
            uncertain="This counts only income logged in DealMeet; payments made elsewhere aren't included.",
            next_steps=["Log off-platform deals under Deals, so invoices and reminders cover them."],
        )
    if intent == "opportunities":
        items = raw["opportunities"]
        if not items:
            return CoachAnswer(answer="No open opportunities fit you right now.", uncertain="New campaigns open every week.", next_steps=["Check your collaboration preferences under Profile."])
        top = ", ".join(f"{o['title']} (fit {o['fit']})" for o in items)
        return CoachAnswer(answer=f"The best fits right now: {top}.", uncertain="Fit is based on your niche, languages and audience; brands decide who they pick.", next_steps=["Open Opportunities to apply and choose what each brand can see."])
    if intent == "deals":
        p = raw["pipeline"]
        return CoachAnswer(
            answer=f"You have {len(p['offers'])} offers waiting, {len(p['active'])} deals in progress and {len(p['awaiting'])} waiting on the brand or payout.",
            uncertain="Payout timing depends on the brand's review and on payouts being connected.",
            next_steps=["Open Deals to answer offers and submit post links."],
        )
    parts = [trend_line]
    if raw.get("fair"):
        parts.append(f"Your fair rate is about {inr_range(raw['fair']['range']['low'], raw['fair']['range']['high'])} a reel.")
    if raw.get("opportunities") is not None:
        parts.append(f"{len(raw['opportunities'])} top opportunities fit you now.")
    return CoachAnswer(answer=" ".join(parts), uncertain=uncertain, next_steps=["Ask about views, pricing, earnings, brands or deals."])


def _fingerprint(c: dict, facts: list[dict]) -> str:
    return hashlib.sha1(json.dumps([c["_id"], facts], sort_keys=True).encode()).hexdigest()[:16]


def ask(c: dict, question: str, lang: str = "en") -> dict:
    intent = intent_of(question)
    facts, raw = facts_for(c, intent)
    db = get_db()
    q = re.sub(r"\s+", " ", question.strip().lower())
    key = f"{_fingerprint(c, facts)}:{hashlib.sha1(f'{q}|{lang}'.encode()).hexdigest()[:16]}"
    cached = db.coach_answers.find_one({"_id": key})
    if cached:
        return {**cached["answer"], "cached": True}
    facts_text = "\n".join(f"- {f['label']}: {f['value']} (source: {f['source']})" for f in facts)
    prompt = (
        f"A creator asks: {question.strip()}\n\nTheir numbers (the only facts you may use):\n{facts_text}\n\n"
        f"Answer in {'Hindi (Devanagari)' if lang == 'hi' else 'English'} in 2 to 4 short sentences. Say what is uncertain. "
        "If there are fewer than 6 posts, say you can't tell a trend. Suggest up to 3 next steps inside the app."
    )
    result, how = generate("coach", prompt, CoachAnswer, lambda: _template(intent, c, raw), facts=facts_text, max_tokens=500)
    out = {
        "question": question.strip(),
        "intent": intent,
        "answer": result.answer,
        "uncertain": result.uncertain,
        "next_steps": result.next_steps,
        "used": facts,
        "trend_known": raw["trend"]["enough"],
        "written_by": "ai" if how in ("ai", "cache") else "template",
        "at": now_iso(),
    }
    db.coach_answers.replace_one({"_id": key}, {"_id": key, "creator_id": c["_id"], "answer": out}, upsert=True)
    return {**out, "cached": False}


# ------------------------------------------------------------------ goals on the weekly plan
GOALS = {
    "raise_rate": ("rate", "Your typical rate", "rupees", 30),
    "lock_rate": ("rate", "Your typical rate", "rupees", 30),
    "rate_card": ("rate", "Your typical rate", "rupees", 14),
    "apply_matches": ("applications", "Applications sent", "count", 7),
    "join_collective": ("applications", "Collectives or campaigns joined", "count", 14),
    "double_down": ("posts", "Reels posted", "count", 14),
    "content_gap": ("posts", "Reels posted", "count", 14),
    "make_series": ("posts", "Reels posted", "count", 14),
    "new_hook": ("posts", "Reels posted", "count", 14),
}


def _goal_for(m: dict, c: dict, fair_low: int) -> dict:
    measure, label, unit, days = GOALS.get(m["kind"], ("done", "Move done", "count", 7))
    target = {"rate": fair_low, "applications": 3 if m["kind"] == "apply_matches" else 1, "posts": 2, "done": 1}[measure]
    return {
        "move_id": m["id"],
        "title": m["title"],
        "metric": label,
        "measure": measure,
        "unit": unit,
        "target": target,
        "deadline": (today() + timedelta(days=days)).isoformat(),
    }


def _progress(c: dict, plan: dict, g: dict) -> dict:
    db = get_db()
    since = plan.get("goals_set_at") or plan.get("generated_at") or ""
    move = next((m for m in plan["moves"] if m["id"] == g["move_id"]), {})
    if g["measure"] == "rate":
        current = int(c.get("current_rate") or 0)
    elif g["measure"] == "applications":
        current = db.applications.count_documents({"creator_id": c["_id"], "at": {"$gte": since}, "status": {"$in": ["applied", "opted_in"]}})
    elif g["measure"] == "posts":
        connected = db.posts.count_documents({"creator_id": c["_id"], "published_at": {"$gte": since[:10]}})
        current = connected or (g["target"] if move.get("status") == "done" else 0)
    else:
        current = 1 if move.get("status") == "done" else 0
    done = current >= g["target"] or move.get("status") == "done"
    late = not done and date.fromisoformat(g["deadline"]) < today()
    return {**g, "current": current, "done": done, "late": late, "tracked": g["measure"] != "done"}


def make_plan(c: dict) -> dict:
    ctx = cc.build(c)
    plan_out = ctx["plan"]
    db = get_db()
    plan = db.plans.find_one({"_id": plan_out["id"]})
    goals = [_goal_for(m, c, ctx["fair"]["range"]["low"]) for m in plan["moves"]]
    db.plans.update_one(
        {"_id": plan["_id"]},
        {"$set": {"goals": goals, "goals_set_at": now_iso(), "baseline": baseline(c, ctx)}},
    )
    return plan_view(c)


def plan_view(c: dict) -> dict | None:
    plan = get_db().plans.find_one({"creator_id": c["_id"]}, sort=[("week", -1)])
    if not plan or not plan.get("goals"):
        return None
    goals = [_progress(c, plan, g) for g in plan["goals"]]
    return {
        "plan_id": plan["_id"],
        "week": plan["week"],
        "goals": goals,
        "done": sum(1 for g in goals if g["done"]),
        "total": len(goals),
        "data_changes": plan.get("data_changes") or [],
        "note": "Targets, not promises. Progress updates from your own data; tick moves you finish on Home.",
    }


def baseline(c: dict, ctx: dict | None = None) -> dict:
    ctx = ctx or cc.build(c, with_plan=False)
    return {
        "followers": int(c.get("followers") or 0),
        "median_views": round(metrics.median_views(c)),
        "fair_low": ctx["fair"]["range"]["low"],
        "fair_high": ctx["fair"]["range"]["high"],
    }


def on_new_data(creator_id: str, reason: str) -> None:
    """New data arrived (a sync, self-reported numbers, a finished deal): recalculate the
    plan's open moves and record what changed against the numbers it was built on."""
    db = get_db()
    plan = db.plans.find_one({"creator_id": creator_id}, sort=[("week", -1)])
    c = db.creators.find_one({"_id": creator_id})
    if not plan or not c:
        return
    from ..engines import next_step

    ctx = cc.build(c, with_plan=False)
    now = baseline(c, ctx)
    before = plan.get("baseline") or now
    changes = []
    if now["followers"] != before["followers"]:
        changes.append(f"Followers: {short(before['followers'])} to {short(now['followers'])}")
    if now["median_views"] != before["median_views"]:
        changes.append(f"Median views: {short(before['median_views'])} to {short(now['median_views'])}")
    if (now["fair_low"], now["fair_high"]) != (before["fair_low"], before["fair_high"]):
        changes.append(f"Fair rate: {inr_range(before['fair_low'], before['fair_high'])} to {inr_range(now['fair_low'], now['fair_high'])}")
    fresh, _ = next_step.generate_moves(c, ctx)
    by_kind = {m["kind"]: m for m in fresh}
    for m in plan["moves"]:
        new = by_kind.get(m["kind"])
        if m["status"] == "open" and new and (new["title"] != m["title"] or new["reason"] != m["reason"]):
            m.update({k: new[k] for k in ("title", "reason", "impact", "why", "hi") if k in new})
            changes.append(f"Updated move: {m['title']}")
    if not changes:
        return
    entry = {"at": now_iso(), "reason": reason, "changes": changes}
    db.plans.update_one(
        {"_id": plan["_id"]},
        {"$set": {"moves": plan["moves"], "baseline": now}, "$push": {"data_changes": {"$each": [entry], "$slice": -10}}},
    )
    db.coach_answers.delete_many({"creator_id": creator_id})
