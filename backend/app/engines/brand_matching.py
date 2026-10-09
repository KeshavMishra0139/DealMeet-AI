"""Brand-side matching: ranked creators for a campaign, with reasons, a fair
price per match and the silent Trust badge. Only discoverable creators appear,
and only the fields each creator has consented to share with this brand."""
from __future__ import annotations

import math

from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from ..services.consent import scopes_for
from ..services.views import audience_stage
from . import brand_safety, metrics
from .common import clamp
from .fair_price import fair_price
from .matching import listing_fit, redact, redact_cautions
from .trust import trust_score


def rank_creator(c: dict, listing: dict, brand: dict, scopes: dict) -> dict:
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    fit = listing_fit(c, listing, brand)
    t = trust_score(c)
    fp = fair_price(c, brand, terms, with_model=False)
    niche = NICHES[c["niche"]]
    eng = clamp(metrics.ss_rate(c) / niche["ss_bench"], 0, 2) / 2 if metrics.has_reels(c) else 0.5
    b = listing.get("budget") or {}
    cap = b.get("per_creator_max")
    budget_fit = 1.0 if not cap else clamp(cap / fp["total"], 0, 1)
    # Reach on a log scale: 1K median views scores 0, 300K scores 1.
    reach = clamp(math.log10(max(metrics.median_views(c), 1_000) / 1_000) / math.log10(300), 0, 1)
    rank = 0.45 * fit["fit"] + 0.2 * reach + 0.15 * eng + 0.1 * ((t["score"] if t else 70) / 100) + 0.1 * budget_fit
    stats = scopes.get("stats")
    return {
        "id": c["_id"],
        "name": c["name"],
        "handle": c["handle"],
        "avatar_hue": c.get("avatar_hue", 260),
        "is_reference": c.get("is_reference", False),
        "reference_note": c.get("reference_note") if c.get("is_reference") else None,
        "niche_label": niche["label"],
        "languages": [LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS],
        "location": c.get("city") or c.get("region"),
        "audience_stage": audience_stage(c.get("followers", 0))["label"],
        "followers": c.get("followers") if stats else None,
        "median_views": round(metrics.median_views(c)) if stats else None,
        "engagement": round(metrics.ss_rate(c), 4) if stats else None,
        "fit": fit["score"],
        "rank": round(rank, 4),
        "reasons": redact(fit["reasons"], scopes)[:3],
        "cautions": redact_cautions(fit["cautions"], scopes)[:2],
        "trust": t,
        "safety": brand_safety.public(c),
        "fair": {"range": fp["range"], "total": fp["total"], "per_reel": fp["per_reel"], "deliverables": fp["deliverables"]},
        "within_budget": not cap or fp["total"] <= cap,
        "rate_card": c.get("current_rate") if scopes.get("rate_card") else None,
        "scopes": scopes,
    }


def matches(listing: dict, brand: dict, limit: int = 30) -> dict:
    db = get_db()
    applied = {a["creator_id"]: a["status"] for a in db.applications.find({"listing_id": listing["_id"]})}
    deals = {d["creator_id"]: d["stage"] for d in db.deals.find({"listing_id": listing["_id"]})}
    rows = []
    hidden_low_trust = 0
    for c in db.creators.find({"_id": {"$regex": "^cr_"}}):
        scopes = scopes_for(c, brand["_id"])
        if scopes is None:
            continue
        fit = listing_fit(c, listing, brand)
        if fit["score"] < 50:
            continue
        row = rank_creator(c, listing, brand, scopes)
        row["application"] = applied.get(c["_id"])
        row["deal_stage"] = deals.get(c["_id"])
        if row["trust"] and row["trust"]["score"] < 50:
            hidden_low_trust += 1
        rows.append(row)
    rows.sort(key=lambda r: (r["trust"] is not None and r["trust"]["score"] < 50, -r["rank"]))
    strong = sum(1 for r in rows if r["fit"] >= 85 and not (r["trust"] and r["trust"]["score"] < 50))
    applied_n = sum(1 for r in rows if r["application"])
    within = sum(1 for r in rows if r["within_budget"])
    summary = f"{len(rows)} creators fit; {strong} are a strong match."
    if applied_n:
        summary += f" {applied_n} applied."
    detail = f"{within} quote within your per-creator budget."
    if hidden_low_trust:
        detail += f" {hidden_low_trust} with weak trust signals {'is' if hidden_low_trust == 1 else 'are'} ranked last."
    return {"listing_id": listing["_id"], "summary": summary, "detail": detail, "items": rows[:limit], "total": len(rows)}

