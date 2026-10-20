"""Public search: creators who keep a public page, found by their own words.

The visitor version of finding creators. It replaced a lookup that let anyone price any
YouTube channel by its handle, which put a number on people who never claimed it here.

What comes back is only what a creator's public page already shows at a glance: name,
handle, niche, languages, city, their own tags, and a follower band when they share stats
publicly. Never exact numbers, reach, rates or audience data. Creators who aren't
discoverable, who turned their public page off, or who are the anonymised reference
profile never appear.

Results are ranked by how many of the search's words match the creator's own words: name,
handle and linked channel names first (small typos allowed), then their tags (sub-niches and
skills), their niche and its keywords, city and language, then bio; ties go to the bigger
creator. Each card says which of its words matched. Browsing one or more niches with no
words lists each niche's top creators. An empty search lists nobody. Public YouTube channels that match come after
DealMeet's own creators (services/youtube_search.py).

Signed-out visitors get the best few matches and are asked to sign in for the rest; the
server enforces that, not the page.
"""
from __future__ import annotations

import re
from difflib import SequenceMatcher

from fastapi import HTTPException

from ..ai.brand_setup import BRAND_WORDS
from ..ai.regional import NICHE_WORDS
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from . import youtube_search
from .media_kit import public_scopes
from .views import audience_stage

VISITOR_LIMIT = 6
MEMBER_LIMIT = 24
YT_VISITOR_LIMIT = 4
YT_MEMBER_LIMIT = 12
MAX_NICHES = 5
# Niches most searched for in India first, when no creators set the order yet.
POPULAR = ["food", "comedy", "tech", "fitness", "beauty", "gaming", "education", "finance", "fashion", "travel",
           "parenting", "anime_edits"]
STOP = {"the", "and", "for", "with", "who", "in", "of", "on", "a", "an", "to", "me", "my", "i", "creator", "creators",
        "brand", "brands", "content", "channel", "page", "videos", "video", "reels", "find", "best", "top", "near"}

VISIBLE = {"discoverable": {"$ne": False}, "public_page": {"$ne": False}, "is_reference": {"$ne": True},
           "handle": {"$nin": [None, ""]}}
FIELDS = {"name": 1, "handle": 1, "avatar_hue": 1, "niche": 1, "languages": 1, "city": 1, "followers": 1, "bio": 1,
          "sub_niches": 1, "skills": 1, "expertise": 1, "public_scopes": 1, "consent_defaults": 1,
          "channels.youtube.title": 1, "channels.youtube.handle": 1, "channels.instagram.username": 1}


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


def _close(w: str, bag: set[str]) -> bool:
    """A small typo in a name ("vivke" for "vivek"); only for words of 5+ letters."""
    return len(w) >= 5 and any(abs(len(b) - len(w)) <= 2 and SequenceMatcher(None, w, b).ratio() >= 0.8 for b in bag)


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
    ch = c.get("channels") or {}
    name_bag = set(words(c.get("name"))) | set(words(c.get("handle")))
    name_bag |= set(words((ch.get("youtube") or {}).get("title"))) | set(words((ch.get("youtube") or {}).get("handle")))
    name_bag |= set(words((ch.get("instagram") or {}).get("username")))
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
            continue
        if _close(w, name_bag):
            score += 2  # a near spelling of their name: last, after every exact match
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
    order = {n: i for i, n in enumerate(POPULAR)}
    return sorted(({"id": n, "label": v["label"], "count": counts.get(n, 0)} for n, v in NICHES.items()),
                  key=lambda x: (-x["count"], order.get(x["id"], 99), x["label"]))


def parse_niches(niche: str | None) -> list[str]:
    """One or more niche ids, comma-separated."""
    picked = list(dict.fromkeys(x.strip() for x in (niche or "").split(",") if x.strip()))
    if len(picked) > MAX_NICHES or any(n not in NICHES for n in picked):
        raise HTTPException(422, "Unknown niche.")
    return picked


def creators(q: str = "", niche: str | None = None, signed_in: bool = False, ip: str | None = None, web: bool = True) -> dict:
    picked = parse_niches(niche)
    q = re.sub(r"\s+", " ", q).strip()
    if not q and not picked:
        # Like a search engine: nobody is listed until someone searches.
        return {"items": [], "total": 0, "limit": 0, "locked": False, "niche_hint": None, "niches": niche_counts(),
                "youtube": {"items": [], "note": None}, "idle": True}
    qw, phrase = query_words(q), q.lower()
    find = {**VISIBLE, **({"niche": {"$in": picked}} if picked else {})}
    ranked = []
    for c in get_db().creators.find(find, FIELDS):
        if q:
            score, matched = _score(c, qw, phrase)
            if score <= 0:
                continue
        else:
            score, matched = 0, []
        ranked.append((score, c, matched))
    # Best match first; then the bigger creator, as a search engine would.
    ranked.sort(key=lambda x: (-x[0], -int(x[1].get("followers") or 0), x[1]["name"].lower()))
    limit = MEMBER_LIMIT if signed_in else VISITOR_LIMIT
    hint = None
    if qw and not picked:
        pointed = niches_for(qw)
        if pointed:
            hint = {"id": pointed[0], "label": NICHES[pointed[0]]["label"]}
    youtube = (
        youtube_search.search(q, picked, ip, YT_MEMBER_LIMIT if signed_in else YT_VISITOR_LIMIT)
        if web and (q or picked) else {"items": [], "note": None}
    )
    return {
        "items": [_card(c, m) for _, c, m in ranked[:limit]],
        "total": len(ranked),
        "limit": limit,
        "locked": not signed_in and len(ranked) > limit,
        "niche_hint": hint,
        "niches": niche_counts(),
        "youtube": youtube,
        "idle": False,
    }


# ------------------------------------------------------------------ suggestions as you type
_VOCAB: dict[str, tuple[float, list[dict]]] = {}
VOCAB_SECONDS = 60
SUGGESTIONS = 8


def _vocab(kind: str) -> list[dict]:
    """Words worth suggesting, built from public data and kept for a minute."""
    import time

    hit = _VOCAB.get(kind)
    if hit and hit[0] > time.time() - VOCAB_SECONDS:
        return hit[1]
    out: list[dict] = []
    seen: set[tuple[str, str]] = set()

    def add(text: str | None, kind_: str, query: str | None = None, weight: int = 0):
        text = (text or "").strip()
        if text and (text.lower(), kind_) not in seen:
            seen.add((text.lower(), kind_))
            out.append({"text": text, "kind": kind_, "query": query or text, "weight": weight})

    db = get_db()
    if kind == "creators":
        for c in db.creators.find(VISIBLE, {"name": 1, "handle": 1, "followers": 1, "sub_niches": 1, "skills": 1, "city": 1, "languages": 1}):
            add(c["name"], "creator", f"@{c['handle']}", int(c.get("followers") or 0))
            for t in [*(c.get("sub_niches") or []), *(c.get("skills") or [])]:
                add(t, "tag")
            add(c.get("city"), "city")
            for lang in _lang_labels(c.get("languages")):
                add(lang, "language")
        for n, v in NICHES.items():
            add(v["label"], "niche", v["label"])
    else:
        from .directory import VISIBLE as BRANDS_VISIBLE

        for b in db.brands.find(BRANDS_VISIBLE, {"name": 1, "category": 1, "target.cities": 1}):
            add(b["name"], "brand")
            add(b.get("category"), "category")
            for city in (b.get("target") or {}).get("cities") or []:
                add(city, "city")
        for n, v in NICHES.items():
            add(f"{v['label']} creators", "niche", v["label"])
    _VOCAB[kind] = (time.time(), out)
    return out


def _matches(q: str, text: str, handle: str = "") -> int:
    """2: the text starts with what's typed; 1: every typed word starts a word in it
    (the last one may be half typed); 0: no match."""
    t = text.lower()
    if t.startswith(q) or (handle and handle.startswith(q)):
        return 2
    qw = re.findall(r"[^\W_]+", q)
    tw = re.findall(r"[^\W_]+", t) + re.findall(r"[^\W_]+", handle)
    if qw and all(any(w.startswith(x) for w in tw) for x in qw):
        return 1
    return 1 if len(q) >= 3 and handle and q in handle else 0


def suggest(q: str, kind: str = "creators") -> list[dict]:
    """Suggestions like YouTube's: the phrases people search for (services/suggest_web.py),
    with DealMeet's own matches (a creator, a niche, a topic) mixed in near the top."""
    from . import suggest_web

    q = re.sub(r"\s+", " ", q).strip().lower().lstrip("@")
    if not q:
        return []
    starts, inside = [], []
    for v in _vocab(kind):
        handle = v["query"].lower().lstrip("@") if v["kind"] == "creator" else ""
        m = _matches(q, v["text"], handle)
        if m == 2:
            starts.append(v)
        elif m == 1:
            inside.append(v)
    order = {"niche": 0, "tag": 1, "category": 1, "creator": 2, "brand": 2, "city": 3, "language": 4}

    def rank(v: dict):
        return (order.get(v["kind"], 5), -v["weight"], len(v["text"]))

    ours = [{k: v[k] for k in ("text", "kind", "query")} for v in sorted(starts, key=rank) + sorted(inside, key=rank)]
    web = [{"text": p, "kind": "search", "query": p} for p in suggest_web.phrases(q, kind)]
    # Up to 3 of ours first (people and niches here), then what people search for, then the rest of ours.
    out, seen = [], set()
    for item in ours[:3] + web + ours[3:]:
        key = item["text"].lower()
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out[:SUGGESTIONS]
