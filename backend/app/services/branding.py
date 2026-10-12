"""Positioning for a creator: a one-line statement, 3 content pillars and 2 bio
suggestions, written by `ai/llm.generate` from the creator's niche and top posts,
with a template fallback. Cached in `creators.branding`; the creator can regenerate
it or edit it, and chooses whether the positioning line shows on their public page."""
from __future__ import annotations

from fastapi import HTTPException
from pydantic import BaseModel, Field, field_validator

from ..ai.llm import breaks_copy_rules, generate
from ..config import now_iso
from ..db import get_db
from ..engines import metrics
from ..seed.catalog import LANGS, NICHES
from .creator_page import top_posts


class Branding(BaseModel):
    positioning: str = Field(min_length=10, max_length=120)
    pillars: list[str] = Field(min_length=3, max_length=3)
    bio_suggestions: list[str] = Field(min_length=2, max_length=2)

    @field_validator("pillars")
    @classmethod
    def _pillars(cls, v: list[str]) -> list[str]:
        if any(not 2 <= len(x.strip()) <= 60 for x in v):
            raise ValueError("Each pillar is 2 to 60 characters")
        return [x.strip() for x in v]

    @field_validator("bio_suggestions")
    @classmethod
    def _bios(cls, v: list[str]) -> list[str]:
        if any(not 10 <= len(x.strip()) <= 220 for x in v):
            raise ValueError("Each bio suggestion is 10 to 220 characters")
        return [x.strip() for x in v]


def _inputs(c: dict) -> tuple[str, list[str]]:
    """Facts for the model, and the top post topics or titles they come from."""
    niche = NICHES[c["niche"]]["label"]
    langs = ", ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS)
    posts = [p["text"] for p in top_posts(c) if p["text"]]
    if not posts and metrics.has_reels(c):
        posts = [t["topic"] for t in metrics.by_topic(c)[:5]]
    facts = f"Niche: {niche}. Content categories: {', '.join(c.get('sub_niches') or []) or 'none given'}. Languages: {langs}. City: {c.get('city') or c.get('region')}.\n"
    facts += "Top posts: " + ("; ".join(posts[:6]) if posts else "none synced yet") + "."
    return facts, posts


def _template(c: dict, posts: list[str]) -> Branding:
    niche = NICHES[c["niche"]]["label"]
    langs = " and ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS) or "your languages"
    subs = [s for s in c.get("sub_niches") or [] if s][:3]
    defaults = [f"Everyday {niche.lower()}", f"{niche} tips", "Behind the scenes"]
    pillars = list(dict.fromkeys(x for x in [*subs, *(p[:60] for p in posts), *defaults] if len(x) >= 2))[:3]
    return Branding(
        positioning=f"{niche} in {langs}, made for people who come back for more"[:120],
        pillars=pillars,
        bio_suggestions=[
            f"{niche} in {langs}. New posts every week.",
            f"Making {niche.lower()} simple, in {langs}. Collabs via JodiDar.",
        ],
    )


def generate_for(c: dict) -> dict:
    facts, posts = _inputs(c)
    prompt = (
        f"{facts}\nWrite, for this creator: a one-line positioning statement (under 15 words), 3 short content pillars, "
        "and 2 Instagram bio suggestions (under 150 characters each). Base them only on the facts; quote no numbers; "
        "no promises about growth or results."
    )

    def fallback() -> Branding:
        return _template(c, posts)

    copy, how = generate("branding", prompt, Branding, fallback, facts=facts, max_tokens=500)
    try:
        copy = Branding.model_validate(copy.model_dump())
    except ValueError:
        copy, how = fallback(), "template"
    doc = {**copy.model_dump(), "written_by": "ai" if how in ("ai", "cache") else "template", "generated_at": now_iso(), "edited": False,
           "show_on_page": bool((c.get("branding") or {}).get("show_on_page"))}
    get_db().creators.update_one({"_id": c["_id"]}, {"$set": {"branding": doc}})
    return doc


def edit(c: dict, changes: dict) -> dict:
    cur = c.get("branding")
    if not cur:
        raise HTTPException(409, "Write your positioning first, then edit it.")
    merged = Branding(**{k: changes.get(k, cur[k]) for k in ("positioning", "pillars", "bio_suggestions")})
    if breaks_copy_rules(" ".join([merged.positioning, *merged.pillars, *merged.bio_suggestions])):
        raise HTTPException(422, "Positioning can't promise results. Describe your content and audience instead.")
    doc = {**cur, **merged.model_dump(), "edited": True}
    if "show_on_page" in changes:
        doc["show_on_page"] = bool(changes["show_on_page"])
    get_db().creators.update_one({"_id": c["_id"]}, {"$set": {"branding": doc}})
    return doc
