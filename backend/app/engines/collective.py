"""Collective Builder: bundle 10-50 matched small creators into one bookable pack.

Greedy knapsack on reach within budget:
  value density = effective reach x audience fit / price
  effective reach = median views x (1 - overlap penalty)
The overlap penalty de-duplicates audiences that are likely the same people
(same cities, same languages, same niche). Profiles below the Trust Score
threshold are excluded automatically, as are creators who aren't discoverable
or have revoked this brand.
"""
from __future__ import annotations

from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from ..services.consent import scopes_for
from ..services.views import audience_stage
from . import metrics
from .common import clamp, inr, short
from .fair_price import fair_price
from .matching import listing_fit
from .trust import trust_score

OVERLAP_WEIGHT = 0.7
TRUST_MIN = 60  # below this the trust score itself is a warning sign
FIT_MIN = 55


def _either(ways: list[str]) -> str:
    return ways[0] if len(ways) == 1 else ", ".join(ways[:-1]) + (", or " if len(ways) > 2 else " or ") + ways[-1]


def audience_overlap(a: dict, b: dict) -> float:
    """Rough share of one creator's audience likely to also follow the other."""
    aa, ab = a.get("audience") or {}, b.get("audience") or {}
    ca = {x["name"]: x["share"] for x in aa.get("cities") or []}
    cb = {x["name"]: x["share"] for x in ab.get("cities") or []}
    city = sum(min(ca[k], cb[k]) for k in ca.keys() & cb.keys())
    la, lb = aa.get("languages") or {}, ab.get("languages") or {}
    lang = sum(min(la[k], lb[k]) for k in la.keys() & lb.keys())
    same_niche = 1.0 if a["niche"] == b["niche"] else 0.5
    same_city = 0.1 if a.get("city") and a.get("city") == b.get("city") else 0
    return clamp((city + same_city) * lang * same_niche, 0, 0.6)


def build(
    listing: dict,
    brand: dict,
    budget: float | None = None,
    size_min: int = 10,
    size_max: int = 50,
    trust_min: int = TRUST_MIN,
    target_reach: float | None = None,
    must_include: list[str] | None = None,
) -> dict:
    db = get_db()
    # Creators who opted in to this collective always get a place in the pack.
    opted = [a["creator_id"] for a in db.applications.find({"listing_id": listing["_id"], "status": "opted_in"})]
    must_include = list(dict.fromkeys((must_include or []) + opted))
    budget = budget or (listing.get("budget") or {}).get("total") or 150_000
    target = listing.get("collective_size")
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    langs = set(listing.get("languages") or [])
    if "hinglish" in langs:
        langs |= {"hi", "en"}

    candidates, excluded = [], []
    for c in db.creators.find({"_id": {"$regex": "^cr_"}}):
        if NICHES[c["niche"]]["family"] not in {NICHES[n]["family"] for n in listing.get("niches") or [c["niche"]]}:
            continue
        if langs and not (set(c.get("languages") or []) & langs):
            continue
        regions = set(listing.get("regions") or [])
        if regions and "Pan-India" not in regions and c.get("region") not in regions:
            continue
        scopes = scopes_for(c, brand["_id"])
        if scopes is None:
            continue  # hidden or revoked: never shown, never counted
        t = trust_score(c)
        fit = listing_fit(c, listing, brand)
        row = {"creator": c, "trust": t, "fit": fit, "scopes": scopes}
        if t and t["score"] < trust_min:
            # A low score comes with its warning signs; a decent one only misses the brand's own higher bar.
            why = f": {t['reasons'][0].lower()}" if t["score"] < TRUST_MIN else ""
            kind = "trust_warning" if t["score"] < TRUST_MIN else "trust_minimum"
            excluded.append({"id": c["_id"], "name": c["name"], "kind": kind, "reason": f"Trust {t['score']} is below {trust_min}{why}"})
            continue
        if fit["score"] < FIT_MIN:
            excluded.append({"id": c["_id"], "name": c["name"], "kind": "fit", "reason": f"Audience fit {fit['score']} is too low for this brief"})
            continue
        fp = fair_price(c, brand, terms, with_model=False)
        row.update({"price": fp["total"], "reach": metrics.median_views(c), "ss": metrics.ss_rate(c) if metrics.ss_known(c) else None})
        candidates.append(row)

    selected: list[dict] = []
    remaining = budget
    pool = list(candidates)
    forced = [r for r in pool if r["creator"]["_id"] in (must_include or [])]
    for r in forced:
        r["overlap"], r["overlap_with"] = 0.0, None
        selected.append(r)
        remaining -= r["price"]
        pool.remove(r)

    def effective(r: dict) -> tuple[float, float, dict | None]:
        worst, with_ = 0.0, None
        for s in selected:
            o = audience_overlap(r["creator"], s["creator"])
            if o > worst:
                worst, with_ = o, s
        return r["reach"] * (1 - OVERLAP_WEIGHT * worst), worst, with_

    while pool and len(selected) < size_max:
        best, best_score = None, -1.0
        for r in pool:
            if r["price"] > remaining:
                continue
            eff, ov, with_ = effective(r)
            score = eff * r["fit"]["fit"] / r["price"]
            if score > best_score:
                best, best_score = (r, eff, ov, with_), score
        if best is None:
            break
        r, eff, ov, with_ = best
        r.update({"effective_reach": eff, "overlap": ov, "overlap_with": with_})
        selected.append(r)
        remaining -= r["price"]
        pool.remove(r)
        reach_so_far = sum(s.get("effective_reach", s["reach"]) for s in selected)
        if target and len(selected) >= target:
            break
        if target_reach and reach_so_far >= target_reach and len(selected) >= size_min:
            break

    for r in pool:
        if r["price"] > remaining:
            excluded.append({"id": r["creator"]["_id"], "name": r["creator"]["name"], "kind": "budget", "reason": "Doesn't fit in the remaining budget"})

    total = sum(r["price"] for r in selected)
    combined = sum(r.get("effective_reach", r["reach"]) for r in selected)
    raw = sum(r["reach"] for r in selected)
    # Consent: a member's reach, followers and engagement go to the brand only with the stats
    # scope; an exact overlap (built from audience cities and languages) only when both
    # creators share demographics with this brand. Pack totals would let a brand work out
    # one member's numbers, so they're shown only when every member shares stats.
    all_stats = all(r["scopes"]["stats"] for r in selected)
    members = []
    for r in sorted(selected, key=lambda x: -x["price"]):
        c = r["creator"]
        stats = r["scopes"]["stats"]
        other = r.get("overlap_with")
        exact_overlap = r["scopes"]["demographics"] and (other is None or other["scopes"]["demographics"])
        ov = r.get("overlap", 0)
        if not stats:
            reach_why = "Reach isn't shared with you: it was used to pick them, but isn't shown."
        elif ov >= 0.01 and other:
            reach_why = f"{short(r['reach'])} median views, counted as {short(r.get('effective_reach', r['reach']))} after audience overlap with {other['creator']['name']}."
        else:
            reach_why = f"{short(r['reach'])} median views, with little audience overlap with the others."
        why = [
            reach_why,
            f"Audience fit {r['fit']['score']}/100 (at least {FIT_MIN} needed).",
            f"Trust {r['trust']['score']}/100 (at least {trust_min} needed)." if r["trust"] else "Trust Score not measured yet.",
            f"Estimated fair price {inr(r['price'])} for the campaign's deliverables.",
        ]
        if c["_id"] in must_include:
            why.insert(0, "Opted in to this collective, so they always get a place.")
        members.append(
            {
                "id": c["_id"],
                "name": c["name"],
                "handle": c["handle"],
                "avatar_hue": c.get("avatar_hue", 260),
                "is_reference": c.get("is_reference", False),
                "niche_label": NICHES[c["niche"]]["label"],
                "language": LANGS.get((c.get("languages") or ["en"])[0], {}).get("label"),
                "city": c.get("city") or c.get("region"),
                "audience_stage": audience_stage(c.get("followers", 0))["label"],
                "followers": c.get("followers", 0) if stats else None,
                "reach": round(r["reach"]) if stats else None,
                "effective_reach": round(r.get("effective_reach", r["reach"])) if stats else None,
                "overlap": round(r.get("overlap", 0), 2) if exact_overlap else None,
                "overlap_level": "High" if r.get("overlap", 0) >= 0.15 else "Low",
                "overlap_with": other["creator"]["name"] if other else None,
                "price": r["price"],
                "split": round(r["price"] / total, 4) if total else 0,
                "fit": r["fit"]["score"],
                "trust": r["trust"],
                "engagement": round(r["ss"], 4) if stats and r["ss"] is not None else None,
                "opted_in": c["_id"] in must_include,
                "why": why,
                "deliverables": terms.get("deliverables") or [{"kind": "reel", "count": 1}],
            }
        )
    dedup = [r for r in selected if r.get("overlap", 0) >= 0.15]
    notes = []
    warning = [e for e in excluded if e["kind"] == "trust_warning"]
    below_bar = [e for e in excluded if e["kind"] == "trust_minimum"]
    if len(members) < size_min:
        ways = []
        if below_bar:
            ways.append(f"lower the trust minimum ({len(below_bar)} left out below {trust_min})")
        if any(e["kind"] == "budget" for e in excluded):
            ways.append("raise the budget")
        ways.append("widen languages or regions")
        notes.append(f"Only {len(members)} creators fit this brief within {inr(budget)}. To add more, {_either(ways)}.")
    if dedup:
        notes.append(f"Audience overlap reduced counted reach for {len(dedup)} creator{'s' if len(dedup) != 1 else ''}.")
    if warning:
        notes.append(f"{len(warning)} profile{'s' if len(warning) != 1 else ''} left out on trust warning signs.")
    if below_bar and len(members) >= size_min:
        notes.append(f"{len(below_bar)} more left out by your trust minimum of {trust_min}.")
    if not all_stats:
        notes.append("Some members don't share stats with you, so pack reach and engagement aren't shown.")
    return {
        "listing_id": listing["_id"],
        "brand_id": brand["_id"],
        "budget": round(budget),
        "size": len(members),
        "size_target": target,
        "total": round(total),
        "remaining": round(budget - total),
        "combined_reach": round(combined) if all_stats else None,
        "raw_reach": round(raw) if all_stats else None,
        "dedup_saved": round(raw - combined) if all_stats else None,
        "avg_engagement": _avg_engagement(selected) if all_stats else None,
        "cost_per_1k": (round(total / combined * 1000) if combined else None) if all_stats else None,
        "trust_min": trust_min,
        "method": {
            "objective": "Adds one creator at a time: the one with the most effective reach × audience fit per rupee, until the budget or the pack size is reached.",
            "effective_reach": f"Median views × (1 − {OVERLAP_WEIGHT} × overlap with the most similar creator already picked).",
            "overlap": "Estimated from shared top cities and languages, higher for the same niche and city, capped at 60%.",
            "thresholds": [f"Trust Score at least {trust_min}", f"Audience fit at least {FIT_MIN}", f"{size_min} to {size_max} creators", f"Budget {inr(budget)}"],
            "privacy": "Creators who aren't discoverable or have revoked you are never considered. Reach is shown only where a creator shares stats with you.",
        },
        "members": members,
        "excluded": excluded,
        "notes": notes,
        "summary": (
            f"{len(members)} creators, "
            + (f"{short(combined)} combined reach after de-duplication, " if all_stats else "")
            + f"{inr(total)} total"
            f"{f' ({inr(budget - total)} under budget)' if budget - total > 500 else ''}."
        ),
    }


def _avg_engagement(selected: list[dict]) -> float | None:
    """Saves + shares per view across members that report them (YouTube videos don't)."""
    known = [r["ss"] for r in selected if r["ss"] is not None]
    if not selected:
        return 0
    return round(sum(known) / len(known), 4) if known else None
