"""Shape database documents for the API."""
from __future__ import annotations

from statistics import median

from ..db import out
from ..seed.catalog import LANGS, NICHES, STAGES

HIDDEN_FIELDS = {"seed_low_trust", "twin_of"}


def audience_stage(followers: int) -> dict:
    for s in STAGES:
        if s["min"] <= followers <= s["max"]:
            return {"id": s["id"], "label": s["label"]}
    return {"id": "zero", "label": "0 followers"}


def recent_reels(c: dict, n: int = 6) -> list[dict]:
    reels = sorted(c.get("reels", []), key=lambda r: r["date"], reverse=True)
    return reels[:n]


def median_views(c: dict, n: int = 6) -> float:
    v = [r["views"] for r in recent_reels(c, n)]
    return float(median(v)) if v else 0.0


def provenance_of(c: dict, path: str) -> str:
    prov = c.get("provenance") or {}
    if path in prov:
        return prov[path]
    # Fall back to the closest parent path, then the creator's default.
    parts = path.split(".")
    while len(parts) > 1:
        parts = parts[:-1]
        p = ".".join(parts)
        if p in prov:
            return prov[p]
    return c.get("provenance_default", "seed")


def source_of(c: dict, path: str) -> str:
    """The data source of a creator field, in the app's four labels: youtube_api or
    instagram_api (Live data), manual (Self-reported) or synthetic (Sample data).
    Built on the older real/simulated provenance map."""
    prov = provenance_of(c, path)
    if prov == "manual":
        return "manual"
    if prov == "real":
        live = c.get("insights_source") in ("instagram_api", "youtube_api")
        return c["insights_source"] if live and path.split(".")[0] in ("reels", "followers", "audience") else "manual"
    return "synthetic"


def any_simulated(c: dict, paths: list[str]) -> bool:
    return any(provenance_of(c, p) == "simulated" for p in paths)


def creator_view(c: dict) -> dict:
    d = out(c)
    for k in HIDDEN_FIELDS:
        d.pop(k, None)
    d["niche_label"] = NICHES[d["niche"]]["label"]
    d["language_labels"] = [LANGS[lang]["label"] for lang in d.get("languages", []) if lang in LANGS]
    d["audience_stage"] = audience_stage(d.get("followers", 0))
    d["median_views"] = median_views(c)
    # Rule: every number says where it came from (Live data, Self-reported, Sample data).
    d["sources"] = {k: source_of(c, k) for k in ("followers", "reels", "audience", "current_rate")}
    d.pop("pre_instagram", None)
    d.pop("pre_youtube", None)
    return d


def creator_card(c: dict) -> dict:
    """Compact view for lists (no reels or income history)."""
    return {
        "id": c["_id"],
        "handle": c["handle"],
        "name": c["name"],
        "avatar_hue": c.get("avatar_hue", 260),
        "niche": c["niche"],
        "niche_label": NICHES[c["niche"]]["label"],
        "languages": c.get("languages", []),
        "language_labels": [LANGS[lang]["label"] for lang in c.get("languages", []) if lang in LANGS],
        "city": c.get("city"),
        "region": c.get("region"),
        "followers": c.get("followers", 0),
        "median_views": median_views(c),
        "audience_stage": audience_stage(c.get("followers", 0)),
        "is_reference": c.get("is_reference", False),
    }
