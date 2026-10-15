"""Public search: creators who keep a public page, found by their own words.

The visitor version of finding creators. It replaced a lookup that let anyone price any
YouTube channel by its handle, which put a number on people who never claimed it here.

What comes back is only what a creator's public page already shows at a glance: name,
handle, niche, languages, city, their own tags, and a follower band when they share stats
publicly. Never exact numbers, reach, rates or audience data. Creators who aren't
discoverable, who turned their public page off, or who are the anonymised reference
profile never appear.

Results are ranked by how many of the search's words match the creator's own words: name
and handle first, then their tags (sub-niches and skills), their niche and its keywords,
city and language, then bio. Each card says which of its words matched.

Signed-out visitors get the best few matches and are asked to sign in for the rest; the
server enforces that, not the page.
"""
from __future__ import annotations

import re

from fastapi import HTTPException

from ..ai.brand_setup import BRAND_WORDS
from ..ai.regional import NICHE_WORDS
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from .media_kit import public_scopes
from .views import audience_stage

VISITOR_LIMIT = 6
MEMBER_LIMIT = 24
STOP = {"the", "and", "for", "with", "who", "in", "of", "on", "a", "an", "to", "me", "my", "i", "creator", "creators",
        "brand", "brands", "content", "channel", "page", "videos", "video", "reels", "find", "best", "top", "near"}

VISIBLE = {"discoverable": {"$ne": False}, "public_page": {"$ne": False}, "is_reference": {"$ne": True},
           "handle": {"$nin": [None, ""]}}
FIELDS = {"name": 1, "handle": 1, "avatar_hue": 1, "niche": 1, "languages": 1, "city": 1, "followers": 1, "bio": 1,
          "sub_niches": 1, "skills": 1, "expertise": 1, "public_scopes": 1, "consent_defaults": 1}


def words(text: str | None) -> list[str]:
    """Lower-case words in any script, with a plural 's' dropped ("snacks" -> "snack")."""
    out = []
    for w in re.findall(r"[^\W_]+", (text or "").lower()):
        if len(w) > 3 and w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        out.append(w)
    return out


def query_words(q: str) -> list[str]:
    return list(dict.fromkeys(w for w in words(q) if len(w) >= 2 and w not in STOP))


def _hit(w: str, bag: set[str]) -> bool:
    """A query word matches a word, the start of a longer one ("cook" finds "cooking"), or
    a longer form of one ("cooking" finds "cook")."""
    return w in bag or (len(w) >= 3 and any(b.startswith(w) or (len(b) >= 4 and w.startswith(b)) for b in bag))


def niche_words(niche: str) -> set[str]:
    """Words that mean a niche: its label, the content keywords the app reads captions with,
    and the words brands in that space use."""
    bag = set(words(NICHES[niche]["label"])) | {x for k in NICHE_WORDS.get(niche, []) for x in words(k)}
    return bag | {x for k in BRAND_WORDS.get(niche, []) for x in words(k)}


NICHE_BAGS = {n: niche_words(n) for n in NICHES}


def niches_for(qw: list[str]) -> list[str]:
    """Niches the search words point at, best first ("dosa" -> food)."""
    scores = {n: sum(1 for w in qw if _hit(w, bag)) for n, bag in NICHE_BAGS.items()}
    return [n for n, s in sorted(scores.items(), key=lambda x: -x[1]) if s]


def _lang_labels(codes: list[str] | None) -> list[str]:
    return [LANGS[x]["label"] for x in codes or [] if x in LANGS]


def _score(c: dict, qw: list[str], phrase: str) -> tuple[int, list[str]]:
    score, matched = 0, []
    name_bag = set(words(c.get("name"))) | set(words(c.get("handle")))
    tags = [t for t in [*(c.get("sub_niches") or []), *(c.get("skills") or []), c.get("expertise")] if t]
    bio = set(words(c.get("bio")))
    langs = _lang_labels(c.get("languages"))
    handle = (c.get("handle") or "").lower()
    if phrase and phrase.lstrip("@") == handle:
        score += 20  # their exact handle
    elif phrase and (phrase in (c.get("name") or "").lower() or phrase.lstrip("@") in handle):
        score += 4
    for w in qw:
        if _hit(w, name_bag):
            score += 6
            continue
        tag = next((t for t in tags if _hit(w, set(words(t)))), None)
        if tag:
            score += 5
            matched.append(tag)
            continue
        if _hit(w, NICHE_BAGS.get(c.get("niche"), set())):
            score += 4
            matched.append(NICHES[c["niche"]]["label"])
            continue
        if c.get("city") and _hit(w, set(words(c["city"]))):
            score += 3
            matched.append(c["city"])
            continue
        lang = next((x for x in langs if _hit(w, set(words(x)))), None)
        if lang:
            score += 3
            matched.append(lang)
            continue
        if _hit(w, bio):
            score += 2
            matched.append("their bio")
    return score, list(dict.fromkeys(matched))


def _card(c: dict, matched: list[str]) -> dict:
    stats = public_scopes(c).get("stats")
    return {
        "handle": c["handle"],
        "name": c["name"],
        "avatar_hue": c.get("avatar_hue", 260),
        "niche": {"id": c["niche"], "label": NICHES[c["niche"]]["label"]} if c.get("niche") in NICHES else None,
        "languages": _lang_labels(c.get("languages")),
        "city": c.get("city"),
        "tags": [t for t in (c.get("sub_niches") or [])][:3],
        "followers_band": audience_stage(int(c.get("followers") or 0))["label"] if stats and c.get("followers") else None,
        "matched": matched[:3],
        "page": f"/c/{c['handle']}",
    }


def niche_counts() -> list[dict]:
    """Every niche, most creators first, so the picker can show the busiest few."""
    counts: dict[str, int] = {}
    for c in get_db().creators.find(VISIBLE, {"niche": 1}):
        counts[c.get("niche")] = counts.get(c.get("niche"), 0) + 1
    return sorted(({"id": n, "label": v["label"], "count": counts.get(n, 0)} for n, v in NICHES.items()),
                  key=lambda x: (-x["count"], x["label"]))


def creators(q: str = "", niche: str | None = None, signed_in: bool = False) -> dict:
    if niche and niche not in NICHES:
        raise HTTPException(422, "Unknown niche.")
    q = re.sub(r"\s+", " ", q).strip()
    qw, phrase = query_words(q), q.lower()
    find = {**VISIBLE, **({"niche": niche} if niche else {})}
    ranked = []
    for c in get_db().creators.find(find, FIELDS):
        if q:
            score, matched = _score(c, qw, phrase)
            if score <= 0:
                continue
        else:
            score, matched = 0, []
        ranked.append((score, c, matched))
    ranked.sort(key=lambda x: (-x[0], x[1]["name"].lower()))
    limit = MEMBER_LIMIT if signed_in else VISITOR_LIMIT
    hint = None
    if qw and not niche:
        pointed = niches_for(qw)
        if pointed:
            hint = {"id": pointed[0], "label": NICHES[pointed[0]]["label"]}
    return {
        "items": [_card(c, m) for _, c, m in ranked[:limit]],
        "total": len(ranked),
        "limit": limit,
        "locked": not signed_in and len(ranked) > limit,
        "niche_hint": hint,
        "niches": niche_counts(),
    }
