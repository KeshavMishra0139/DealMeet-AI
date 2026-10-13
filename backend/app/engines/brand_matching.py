"""Brand-side matching: ranked creators for a campaign, with reasons, a fair
price per match and the silent Trust badge. Only discoverable creators appear,
and only the fields each creator has consented to share with this brand."""
from __future__ import annotations

import math

from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from ..services.consent import scopes_for
from ..services.views import audience_stage, source_of
from . import brand_safety, metrics
from .common import clamp, inr_full, short
from .fair_price import fair_price
from .matching import listing_fit, redact, redact_cautions
from .trust import trust_score


# The ranking: each part is scored 0 to 1, then weighted. Documented in the README and
# returned with every result.
WEIGHTS = {"fit": 0.45, "reach": 0.20, "engagement": 0.15, "trust": 0.10, "budget": 0.10}
CRITERIA = [
    {"key": "fit", "label": "Audience fit", "weight": WEIGHTS["fit"],
     "how": "Niche, language, region and audience match with this campaign (0 to 100)."},
    {"key": "reach", "label": "Reach", "weight": WEIGHTS["reach"],
     "how": "Median views of recent posts on a log scale: 1K views scores 0, 300K scores 1."},
    {"key": "engagement", "label": "Engagement", "weight": WEIGHTS["engagement"],
     "how": "Saves and shares per view against the niche's typical rate; typical scores 0.5."},
    {"key": "trust", "label": "Trust Score", "weight": WEIGHTS["trust"],
     "how": "The Trust Score out of 100."},
    {"key": "budget", "label": "Budget fit", "weight": WEIGHTS["budget"],
     "how": "1 when the estimated price is within your per-creator cap, lower the further above it."},
]
# Missing data is scored as neutral, never as a penalty.
NEUTRAL = {"reach": 0.5, "engagement": 0.5, "trust": 0.75}


def _components(c: dict, fit: dict, t: dict | None, fp: dict, cap: int | None, scopes: dict) -> list[dict]:
    niche = NICHES[c["niche"]]
    manual = (c.get("manual") or {}).get("avg_views")
    out = []

    def add(key: str, score: float, missing: bool = False, note: str | None = None, private: bool = False):
        out.append({
            "key": key,
            "label": next(x["label"] for x in CRITERIA if x["key"] == key),
            "weight": WEIGHTS[key],
            # A score built from stats the creator hasn't shared with you stays hidden.
            "score": None if private else round(score, 3),
            "missing": missing,
            "note": note,
            "_score": score,
        })

    add("fit", fit["fit"])
    stats = bool(scopes.get("stats"))
    if metrics.has_reels(c) or manual or c.get("followers"):
        views = metrics.median_views(c)
        reach = clamp(math.log10(max(views, 1_000) / 1_000) / math.log10(300), 0, 1)
        note = None if metrics.has_reels(c) else ("From self-reported average views." if manual else "Estimated from the follower count.")
        add("reach", reach, note=note if stats else "Not shared with you: used in the ranking, not shown.", private=not stats)
    else:
        add("reach", NEUTRAL["reach"], True, "Data missing: scored as neutral.")
    if metrics.ss_known(c):
        eng = clamp(metrics.ss_rate(c) / niche["ss_bench"], 0, 2) / 2
        add("engagement", eng, note=None if stats else "Not shared with you: used in the ranking, not shown.", private=not stats)
    elif metrics.has_reels(c):
        add("engagement", NEUTRAL["engagement"], True, "YouTube doesn't report saves or shares: scored as typical for the niche.")
    else:
        add("engagement", NEUTRAL["engagement"], True, "Data missing: scored as typical for the niche.")
    if t:
        add("trust", t["score"] / 100)
    else:
        add("trust", NEUTRAL["trust"], True, "Not measured yet: scored as neutral (75/100).")
    add("budget", 1.0 if not cap else clamp(cap / fp["total"], 0, 1), note=None if not cap else ("Within your cap." if fp["total"] <= cap else "Estimated price is above your cap."))
    return out


def evidence(c: dict, scopes: dict) -> list[dict]:
    """What the creator chose to share with this brand, each with its data source."""
    rows = []
    if scopes.get("stats"):
        rows.append({"key": "followers", "label": "Followers", "value": short(c.get("followers", 0)), "source": source_of(c, "followers")})
        if metrics.has_reels(c):
            rows.append({"key": "median_views", "label": f"Median views, last {len(metrics.recent(c))} posts", "value": short(metrics.median_views(c)), "source": source_of(c, "reels.0.views")})
            if metrics.ss_known(c):
                rows.append({"key": "engagement", "label": "Saves + shares per view", "value": f"{metrics.ss_rate(c) * 100:.1f}%", "source": source_of(c, "reels.0.saves")})
        elif (c.get("manual") or {}).get("avg_views"):
            rows.append({"key": "median_views", "label": "Average views (self-reported)", "value": short(c["manual"]["avg_views"]), "source": "manual"})
    if scopes.get("demographics") and c.get("audience"):
        a = c["audience"]
        src = source_of(c, "audience")
        if a.get("age"):
            age, share = max(a["age"].items(), key=lambda kv: kv[1])
            rows.append({"key": "age", "label": "Largest age group", "value": f"{age} ({round(share * 100)}%)", "source": src})
        if a.get("gender"):
            rows.append({"key": "women", "label": "Women in the audience", "value": f"{round(a['gender'].get('female', 0) * 100)}%", "source": src})
        if a.get("cities"):
            rows.append({"key": "cities", "label": "Top cities", "value": ", ".join(x["name"] for x in a["cities"][:3]), "source": src})
    if scopes.get("rate_card") and c.get("current_rate"):
        rows.append({"key": "rate", "label": "Their typical rate per reel", "value": inr_full(c["current_rate"]), "source": source_of(c, "current_rate")})
    return rows


PRICE_BASIS = {
    "Estimate from Instagram data": "Price estimated from their connected Instagram data.",
    "Estimate from sample data": "Price estimated from sample data.",
    "Estimate from self-reported numbers": "Price estimated from numbers they reported.",
    "Estimate from YouTube data": "Price estimated from their YouTube channel's public data.",
    "Estimate from your follower count": "Price estimated from their follower count.",
    "Estimate from your subscriber count": "Price estimated from their subscriber count.",
}


def limitations(c: dict, scopes: dict, comps: list[dict], fp: dict, ev: list[dict]) -> list[str]:
    out = [x["note"] for x in comps if x["missing"]]
    if not scopes.get("stats"):
        out.append("Reach and engagement aren't shared with you.")
    if not scopes.get("demographics"):
        out.append("Audience demographics aren't shared with you.")
    if any(e["source"] == "synthetic" for e in ev) or (not ev and source_of(c, "reels.0.views") == "synthetic"):
        out.append("Some numbers are sample data, not the creator's own.")
    out.append(PRICE_BASIS.get(fp.get("data_label"), "Price estimated from the data available.") + " It's an estimate, not a quote.")
    return out


def rank_creator(c: dict, listing: dict, brand: dict, scopes: dict) -> dict:
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    fit = listing_fit(c, listing, brand)
    t = trust_score(c)
    fp = fair_price(c, brand, terms, with_model=False, scopes=scopes)
    niche = NICHES[c["niche"]]
    b = listing.get("budget") or {}
    cap = b.get("per_creator_max")
    comps = _components(c, fit, t, fp, cap, scopes)
    rank = sum(x["weight"] * x.pop("_score") for x in comps)
    stats = scopes.get("stats")
    ev = evidence(c, scopes)
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
        "engagement": round(metrics.ss_rate(c), 4) if stats and metrics.ss_known(c) else None,
        "fit": fit["score"],
        "rank": round(rank, 4),
        "ranking": comps,
        "reasons": redact(fit["reasons"], scopes)[:3],
        "cautions": redact_cautions(fit["cautions"], scopes)[:2],
        "evidence": ev,
        "limitations": limitations(c, scopes, comps, fp, ev),
        "trust": t,
        "safety": brand_safety.public(c),
        "fair": {"range": fp["range"], "total": fp["total"], "per_reel": fp["per_reel"], "deliverables": fp["deliverables"], "estimate": True},
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
    shortlisted = {x["creator_id"] for x in db.shortlists.find({"listing_id": listing["_id"]}, {"creator_id": 1})}
    for r in rows:
        r["shortlisted"] = r["id"] in shortlisted
    return {"listing_id": listing["_id"], "summary": summary, "detail": detail, "items": rows[:limit], "total": len(rows), "criteria": CRITERIA}

