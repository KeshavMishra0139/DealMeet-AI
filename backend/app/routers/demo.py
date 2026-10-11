from fastapi import APIRouter, HTTPException

from ..config import get_settings
from ..db import get_db
from ..engines import metrics, money_paths, roadmap
from ..engines.matching import possessive
from ..engines.common import inr, inr_range, short
from ..engines.roadmap import LANG_NAMES
from ..seed.load import seed_all
from ..services import creator_ctx as cc
from .creators import _summary

router = APIRouter(prefix="/api/demo", tags=["demo"])


def _demo_only() -> None:
    # Outside demo mode these routes don't exist: a reset would wipe real accounts' data.
    if not get_settings().demo_mode:
        raise HTTPException(404, "Not found")


@router.post("/reset")
def reset():
    """Restore every seeded record. Used by the 'Reset demo' control (demo mode only)."""
    from ..services import cache

    _demo_only()

    cache.clear_runtime()
    return seed_all(get_db(), force=True)


def _side(creator_id: str) -> dict:
    c = cc.load_creator(creator_id)
    ctx = cc.build(c)
    rm = roadmap.build(c, ctx["stage"]["id"], ctx["plan"]["moves"], ctx["paths"])
    fair = ctx["fair"]
    return {
        "creator": _summary(c),
        "context": cc.context_line(c),
        "stage": ctx["stage"],
        "rate_gap": cc.rate_gap(c, fair),
        "fair": {k: fair[k] for k in ("range", "per_reel", "follower_price", "lister_name", "uplift_vs_followers", "estimate", "why")},
        "durable": ctx["durable"],
        "roadmap": {"working": rm["working"][:2], "gaps": rm["gaps"][:2], "skills": rm["skills"][:3]},
        "paths": ctx["paths"][:3],
        "goal": money_paths.goal_summary(c, ctx["paths"]),
        "opportunities": ctx["opps"][:3],
        "moves": ctx["plan"]["moves"],
    }


def _name(side: dict) -> str:
    return side["creator"]["name"]


def _lower_first(text: str) -> str:
    """Lower-case the first word unless it is a proper noun (a language name)."""
    first = text.split(" ", 1)[0]
    return text if first in LANG_NAMES.values() else text[:1].lower() + text[1:]


def _roadmap_line(side: dict) -> str:
    rm = side["roadmap"]
    gap = rm["gaps"][0] if rm["gaps"] else None
    skill = rm["skills"][0]["title"].split(":")[0].lower() if rm["skills"] else None
    if gap and gap["kind"] == "format" and rm["working"]:
        line = f"{_name(side)} keeps {metrics.topic_plural(rm['working'][0]['topic'])} and adds {_lower_first(gap['title'])}"
    elif gap:
        line = f"{_name(side)} fills a gap: {_lower_first(gap['title'])}"
    elif rm["working"]:
        line = f"{_name(side)} doubles down on {metrics.topic_plural(rm['working'][0]['topic'])}"
    else:
        line = f"{_name(side)} starts with one format and a steady posting day"
    return line + (f"; first skill: {skill}." if skill else ".")


def _price_line(side: dict) -> str:
    gap, ctx = side["rate_gap"], side["context"]
    lo, hi = gap["fair"]["low"], gap["fair"]["high"]
    if gap["current"]:
        quote = (
            f"they quote {inr(gap['current'])}, about what followers alone suggest"
            if abs(gap["current"] - gap["follower_price"]) <= 0.15 * gap["current"]
            else f"they quote {inr(gap['current'])} (followers alone suggest {inr(gap['follower_price'])})"
        )
        reach = f"reels reach about {ctx['reach_ratio']:.0f}x their followers. " if ctx.get("reach_ratio") else ""
        return f"{possessive(_name(side))} {reach}Fair price {inr_range(lo, hi)} a reel; {quote}."
    return f"{_name(side)} has no rate yet: a first rate card at {inr_range(lo, hi)} a reel, priced on {short(ctx['median_views'])} median views."


def _opportunity_line(side: dict) -> str:
    opps = side["opportunities"]
    if not opps:
        return f"{_name(side)} has no open matches yet."
    coll = next((o for o in opps if o["type"] == "collective"), None)
    if coll and side["creator"]["followers"] < 10_000:
        return f"{_name(side)} can join {possessive(coll['lister']['name'])} {coll['collective_size']}-creator collective: one escrow payment, split among the members."
    top = opps[0]
    return f"{_name(side)} matches {top['title']} from {top['lister']['name']} (fit {top['fit']}/100)."


def guide(a: dict, b: dict) -> list[dict]:
    goal_b = (b["creator"].get("income_goal") or {}).get("monthly")
    return [
        {
            "id": "who",
            "title": "Two creators, one engine",
            "caption": f"{_name(a)}: {a['creator']['niche_label'].lower()}, {short(a['creator']['followers'])} followers, already earns from brands. "
            f"{_name(b)}: {b['creator']['niche_label'].lower()} in {', '.join(b['creator']['language_labels'])}, {short(b['creator']['followers'])} followers"
            + (f", wants {inr(goal_b)} a month." if goal_b else "."),
            "route": "/creator",
        },
        {
            "id": "stage",
            "title": "Stage, not follower count",
            "caption": f"{_name(a)} is '{a['stage']['label']}'. {_name(b)} is '{b['stage']['label']}'. Every screen adapts to the stage.",
            "route": "/creator",
        },
        {
            "id": "price",
            "title": "Fair price on reach, not followers",
            "caption": f"{_price_line(a)} {_price_line(b)}",
            "route": "/creator/money",
        },
        {
            "id": "roadmap",
            "title": "A roadmap from real gaps",
            "caption": f"{_roadmap_line(a)} {_roadmap_line(b)}",
            "route": "/creator/roadmap",
        },
        {
            "id": "money",
            "title": "Money paths ranked for each goal",
            "caption": f"{_name(a)}: " + "; ".join(_lower_first(p["title"]) for p in a["paths"]) + f". {_name(b)}: " + "; ".join(_lower_first(p["title"]) for p in b["paths"]) + ".",
            "route": "/creator/money",
        },
        {
            "id": "opportunities",
            "title": "Matches they opted into",
            "caption": f"{_opportunity_line(a)} {_opportunity_line(b)} Brands see only what each creator shares.",
            "route": "/creator/opportunities",
        },
        {
            "id": "moves",
            "title": "Your next 3 moves",
            "caption": f"Each week, three moves with a reason, a range and a 'Why?'. {_name(a)} starts with '{a['moves'][0]['title']}'. "
            f"{_name(b)} starts with '{b['moves'][0]['title']}'.",
            "route": "/creator",
        },
    ]


@router.get("/compare")
def compare(a: str = "cr_a", b: str = "cr_b"):
    """Creator A and Creator B side by side, plus captions for the guided demo (demo mode only)."""
    _demo_only()
    left, right = _side(a), _side(b)
    return {"a": left, "b": right, "guide": guide(left, right)}
