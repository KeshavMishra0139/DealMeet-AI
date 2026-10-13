"""How well a creator's audience fits a brand (or other lister), with reasons."""
from __future__ import annotations

import re

from ..seed.catalog import LANGS, NICHES
from . import metrics
from .common import clamp

WEIGHTS = {"niche": 0.30, "age": 0.20, "gender": 0.10, "language": 0.20, "geo": 0.20}

REGION_ALIASES = {
    "North India": "North",
    "South India": "South",
    "East India": "East",
    "West India": "West",
    "Central India": "Central",
}


def _region(c: dict) -> str | None:
    r = c.get("region")
    return REGION_ALIASES.get(r, r)


# Without the demographics scope a brand keeps the conclusion but not the numbers.
# Reasons and cautions are rewritten separately: the same age sentence is a reason
# at 60% or more and a caution below that.
GENERIC_REASONS = [
    (re.compile(r"of the audience is in the target ages"), "Audience ages match your target"),
    (re.compile(r"of the audience speaks"), "Audience speaks your languages"),
    (re.compile(r"^Audience concentrated in"), "Audience is in your target regions"),
    (re.compile(r"women, matching the target"), "Audience matches your gender target"),
]
# Built from reel views, so it needs the stats scope rather than demographics.
STATS_REASONS = re.compile(r"^Reels reach about")
GENERIC_CAUTIONS = [
    (re.compile(r"of the audience is in the target ages"), "Audience ages only partly match your target"),
    (re.compile(r"of the audience speaks"), "Much of the audience speaks other languages"),
]


def _generic(texts: list[str], scopes: dict, rules: list) -> list[str]:
    if scopes.get("demographics"):
        return texts
    out = []
    for t in texts:
        for rx, generic in rules:
            if rx.search(t):
                t = generic
                break
        out.append(t)
    return out


def redact(reasons: list[str], scopes: dict) -> list[str]:
    """Fit reasons as a brand may see them under its consent scopes."""
    out = _generic(reasons, scopes, GENERIC_REASONS)
    return out if scopes.get("stats") else [r for r in out if not STATS_REASONS.search(r)]


def redact_cautions(cautions: list[str], scopes: dict) -> list[str]:
    """Fit cautions as a brand may see them under its consent scopes."""
    return _generic(cautions, scopes, GENERIC_CAUTIONS)


def pct_text(pct: int) -> str:
    """'64%', or 'All' for a whole audience: the copy rules keep 100 percent figures out of the UI."""
    return "All" if pct >= 100 else f"{pct}%"


def possessive(name: str) -> str:
    return f"{name}'" if name.endswith("s") else f"{name}'s"


def niche_affinity(niche: str, targets: list[str]) -> float:
    if not targets:
        return 0.5
    if niche in targets:
        return 1.0
    fam = NICHES[niche]["family"]
    if any(NICHES.get(t, {}).get("family") == fam for t in targets):
        return 0.6
    return 0.15


def audience_fit(c: dict, lister: dict) -> dict:
    """0..1 fit between a creator's (consented) audience and a lister's target."""
    target = lister.get("target") or {}
    aud = c.get("audience") or {}
    ages = aud.get("age") or {}
    t_ages = target.get("ages") or []
    # No audience data yet (a new account on a live site): ages and cities count as typical, not zero.
    age = sum(ages.get(a, 0) for a in t_ages) if t_ages and ages else 0.7

    gender = 1.0
    if target.get("gender") in ("female", "male"):
        share = (aud.get("gender") or {}).get(target["gender"], 0.5)
        gender = clamp(share / 0.55, 0, 1)

    t_langs = set(target.get("languages") or [])
    a_langs = aud.get("languages") or {lang: 1 / len(c.get("languages") or ["en"]) for lang in c.get("languages") or ["en"]}
    if "hinglish" in t_langs:
        t_langs |= {"hi", "en"}
    language = sum(v for k, v in a_langs.items() if k in t_langs or (k == "hinglish" and t_langs & {"hi", "en"})) if t_langs else 0.7
    language = clamp(language, 0, 1)

    t_regions = set(target.get("regions") or [])
    region_ok = 1.0 if not t_regions or _region(c) in t_regions else 0.0
    t_cities = set(target.get("cities") or [])
    city_share = sum(x["share"] for x in aud.get("cities") or [] if x["name"] in t_cities) if t_cities and aud.get("cities") else 0.5
    geo = 0.5 * region_ok + 0.5 * clamp(city_share / 0.5, 0, 1)

    niche = niche_affinity(c["niche"], lister.get("niches") or [])
    parts = {"niche": niche, "age": clamp(age, 0, 1), "gender": gender, "language": language, "geo": geo}
    fit = sum(WEIGHTS[k] * v for k, v in parts.items())

    reasons, cautions = [], []
    label = NICHES[c["niche"]]["label"].lower()
    if niche >= 1.0:
        reasons.append(f"Makes {label}, the category {lister['name']} targets")
    elif niche >= 0.6:
        reasons.append(f"Adjacent niche ({label}) to what {lister['name']} targets")
    else:
        cautions.append(f"{NICHES[c['niche']]['label']} is outside {possessive(lister['name'])} categories")
    if t_ages and ages:
        pct = round(parts["age"] * 100)
        (reasons if pct >= 60 else cautions).append(f"{pct_text(pct)} of the audience is in the target ages ({', '.join(t_ages)})")
    elif t_ages:
        cautions.append("Audience ages aren't known yet, so they count as typical")
    if t_langs:
        pct = round(language * 100)
        shared = [k for k, v in sorted(a_langs.items(), key=lambda kv: -kv[1]) if k in t_langs and k in LANGS]
        if pct >= 60 and shared:
            reasons.append(f"{pct_text(pct)} of the audience speaks {' or '.join(LANGS[k]['label'] for k in shared[:2])}")
        elif pct < 60:
            wanted = [LANGS[k]["label"] for k in sorted(t_langs) if k in LANGS and k != "hinglish"][:3]
            cautions.append(f"Only {pct}% of the audience speaks {' or '.join(wanted)}")
    if t_regions and region_ok:
        top = ", ".join(x["name"] for x in (aud.get("cities") or [])[:2])
        if top:
            reasons.append(f"Audience concentrated in {top}")
    elif t_regions:
        cautions.append(f"Audience is mostly outside {', '.join(sorted(t_regions))}")
    if target.get("gender") == "female" and gender >= 0.9:
        reasons.append(f"{pct_text(round((aud.get('gender') or {}).get('female', 0) * 100))} women, matching the target")

    return {
        "fit": round(fit, 3),
        "score": int(round(fit * 100)),
        "parts": {k: round(v, 3) for k, v in parts.items()},
        "reasons": reasons,
        "cautions": cautions,
        "simulated": bool(metrics.fields_simulated(c, "audience")),
    }


def listing_fit(c: dict, listing: dict, lister: dict) -> dict:
    """Fit of a creator for a specific listing: audience fit plus listing rules."""
    base = audience_fit(c, {**lister, "niches": listing.get("niches") or lister.get("niches")})
    score = base["fit"]
    langs = set(listing.get("languages") or [])
    if "hinglish" in langs:
        langs |= {"hi", "en"}
    if base["parts"]["niche"] < 0.5:
        score *= 0.55
    speaks = bool(set(c.get("languages") or []) & langs) or not langs
    if not speaks:
        score *= 0.55
        base["cautions"].append("Doesn't post in the listing's languages")
    regions = set(listing.get("regions") or [])
    if regions and "Pan-India" not in regions and _region(c) not in regions:
        score *= 0.7
    min_f = listing.get("min_followers") or 0
    eligible = c.get("followers", 0) >= min_f
    if not eligible:
        score *= 0.6
        base["cautions"].append(f"Listing asks for {min_f:,}+ followers or subscribers")
    if metrics.has_reels(c) and metrics.reach_ratio(c) > 2:
        base["reasons"].append(f"{metrics.post_noun(c).capitalize()}s reach about {metrics.reach_ratio(c):.0f}x the {metrics.audience_noun(c)[:-1]} count")
    base.update({"fit": round(score, 3), "score": int(round(score * 100)), "eligible": eligible, "speaks": speaks})
    return base
