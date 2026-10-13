"""The week's moves, worded by the AI for this creator.

The rule engine (engines/next_step.py) still decides which 3 moves a creator gets, what each
asks them to do, and every number in them. Once a week's plan is saved, the language model
rewrites each move's title and reason, in English and Hindi, so it speaks to this creator:
their niche, format, language and recent topics. It runs in the background (the plan is
there at once, worded by the templates) and is kept only when:
- it returns the same moves, with titles and reasons of a sensible length;
- the Hindi is in Devanagari;
- it keeps the copy rules and quotes no number that isn't in the facts (llm.generate).
Moves someone has already acted on aren't reworded.
"""
from __future__ import annotations

import logging
import re
import threading

from pydantic import BaseModel, Field

from ..config import get_settings
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from .llm import generate

log = logging.getLogger("jodidar.ai")
DEVANAGARI = re.compile(r"[ऀ-ॿ]")


class MoveCopy(BaseModel):
    id: str
    title: str = Field(description="At most 70 characters. What to do, as an instruction.")
    reason: str = Field(description="One or two sentences, at most 220 characters: why this move, for this creator.")
    title_hi: str = Field(description="The title in Hindi, Devanagari script")
    reason_hi: str = Field(description="The reason in Hindi, Devanagari script")


class MovesCopy(BaseModel):
    moves: list[MoveCopy]


def _facts(c: dict, moves: list[dict]) -> str:
    from ..engines import metrics

    posts, audience = metrics.post_noun(c), metrics.audience_noun(c)
    langs = ", ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS) or "not given"
    titles = [x.get("caption") for x in metrics.recent(c) if x.get("caption")][:6]
    lines = [
        f"Creator: {c.get('name')} on {metrics.platform(c).capitalize()}, niche {NICHES[c['niche']]['label']}, languages {langs}, "
        f"city {c.get('city') or c.get('region') or 'not given'}.",
        f"{audience.capitalize()}: {c.get('followers', 0)}. Median views of recent {posts}s: {round(metrics.median_views(c))}. "
        f"{posts.capitalize()}s per week: {metrics.posts_per_week(c):.1f}.",
    ]
    if titles:
        lines.append(f"Recent {posts} titles:\n" + "\n".join(f"- {t[:120]}" for t in titles))
    lines.append("This week's moves:")
    for m in moves:
        reasons = " ".join(((m.get("why") or {}).get("reasons") or [])[:2])
        lines.append(f"- id {m['id']} ({m['category']}): title \"{m['title']}\". Reason: {m['reason']} Details: {reasons}")
    return "\n".join(lines)


PROMPT = (
    "Rewrite each move's title and reason so it speaks to this creator: use their niche, format, language or "
    "recent topics where it helps. Keep what each move asks them to do, and copy every number exactly as the "
    "facts write it; add no other numbers. Title at most 70 characters, as an instruction. Reason one or two "
    "sentences, at most 220 characters. Also give title_hi and reason_hi in Hindi (Devanagari) with the same "
    "meaning and numbers. Return every move, with the same ids."
)


def _usable(out: MovesCopy, ids: set[str]) -> dict[str, MoveCopy] | None:
    by_id = {m.id: m for m in out.moves}
    if set(by_id) != ids:
        return None
    for m in by_id.values():
        if not (4 <= len(m.title) <= 90 and 10 <= len(m.reason) <= 300 and 2 <= len(m.title_hi) <= 120 and 10 <= len(m.reason_hi) <= 400):
            return None
        if not DEVANAGARI.search(m.title_hi) or not DEVANAGARI.search(m.reason_hi):
            return None
    return by_id


def personalize(plan_id: str) -> bool:
    """Rewords a saved plan's open moves for its creator. True when the AI's wording was used."""
    if not get_settings().has_ai:
        return False
    db = get_db()
    plan = db.plans.find_one({"_id": plan_id})
    c = db.creators.find_one({"_id": (plan or {}).get("creator_id")})
    if not plan or not c:
        return False
    moves = [m for m in plan["moves"] if m.get("status") == "open" and m.get("written_by") != "ai"]
    if not moves:
        return False
    facts = _facts(c, moves)
    out, source = generate("moves_copy", f"{facts}\n\n{PROMPT}", MovesCopy, lambda: MovesCopy(moves=[]), facts=facts, max_tokens=1500)
    if source == "template":
        return False
    by_id = _usable(out, {m["id"] for m in moves})
    if not by_id:
        log.info("AI moves for %s: answer didn't fit; keeping the template wording", plan_id)
        return False
    for mid, m in by_id.items():
        # Only a move still open: someone may have acted on it while the AI was writing.
        db.plans.update_one(
            {"_id": plan_id, "moves": {"$elemMatch": {"id": mid, "status": "open"}}},
            {"$set": {"moves.$.title": m.title.strip(), "moves.$.reason": m.reason.strip(),
                      "moves.$.hi": {"title": m.title_hi.strip(), "reason": m.reason_hi.strip()}, "moves.$.written_by": "ai"}},
        )
    return True


def personalize_soon(plan_id: str) -> None:
    """personalize() in the background; the plan shows with template wording until then."""
    if not get_settings().has_ai:
        return

    def run() -> None:
        try:
            personalize(plan_id)
        except Exception:  # wording never breaks a plan
            log.exception("AI moves for %s failed", plan_id)

    threading.Thread(target=run, name=f"moves-{plan_id}", daemon=True).start()
