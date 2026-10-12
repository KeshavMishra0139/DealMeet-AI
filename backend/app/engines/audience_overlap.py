"""How much of a creator's audience overlaps a brand's target, per dimension.

Pure and minimal on purpose: it's the job the TEE runs (services/tee.py), so its input
is only bucket percentages and the target's lists, never ids, names or handles."""
from __future__ import annotations

from ..seed.catalog import LANGS

JOB = "audience_overlap"


def minimise(audience: dict, target: dict) -> dict:
    """Only what the overlap needs: the shares for the dimensions the brand targets."""
    t_ages = list(target.get("ages") or [])
    t_gender = target.get("gender") if target.get("gender") in ("female", "male") else None
    t_cities = list(target.get("cities") or [])
    t_langs = set(target.get("languages") or [])
    if "hinglish" in t_langs:
        t_langs |= {"hi", "en"}
    ages = audience.get("age") or {}
    cities = {x["name"]: x["share"] for x in audience.get("cities") or [] if x.get("name") in t_cities}
    langs = audience.get("languages") or {}
    return {
        "ages": {a: float(ages.get(a, 0)) for a in t_ages} if t_ages and ages else None,
        "gender": {t_gender: float((audience.get("gender") or {}).get(t_gender, 0))} if t_gender and audience.get("gender") else None,
        "cities": cities if t_cities and audience.get("cities") else None,
        "languages": {k: float(v) for k, v in langs.items() if k in t_langs} if t_langs and langs else None,
        "target": {"ages": t_ages, "gender": t_gender, "cities": t_cities, "languages": sorted(t_langs)},
    }


def compute(m: dict) -> dict:
    """Share of the audience in each targeted dimension (0..1), or None when there's no data."""
    def total(d: dict | None) -> float | None:
        return round(min(sum(d.values()), 1.0), 2) if d is not None else None

    t = m["target"]
    rows = []
    if t["ages"]:
        rows.append({"key": "ages", "label": f"In your target ages ({', '.join(t['ages'])})", "share": total(m["ages"])})
    if t["gender"]:
        rows.append({"key": "gender", "label": f"{t['gender'].capitalize()}", "share": total(m["gender"])})
    if t["cities"]:
        rows.append({"key": "cities", "label": f"In your target cities ({', '.join(t['cities'][:4])}{'…' if len(t['cities']) > 4 else ''})", "share": total(m["cities"])})
    if t["languages"]:
        names = [LANGS[k]["label"] for k in t["languages"] if k in LANGS and k != "hinglish"][:3]
        rows.append({"key": "languages", "label": f"Speaks {' or '.join(names) or 'your languages'}", "share": total(m["languages"])})
    return {"dimensions": rows}
