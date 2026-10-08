"""Opportunities matched to a creator, each valued at this creator's fair price."""
from __future__ import annotations

from ..db import get_db
from ..seed.catalog import NICHES
from . import metrics
from .common import estimate, inp, inr, inr_range, short, why
from .fair_price import PRODUCTION_FLOOR, fair_price
from .matching import listing_fit
from .spam import is_flagged, scan

TYPE_LABELS = {
    "brand_campaign": "Brand campaign",
    "pr_service": "PR service",
    "page": "Page",
    "creator_collab": "Creator collab",
    "collective": "Collective",
}


def monthly_views(c: dict) -> float:
    per_month = max(metrics.posts_per_week(c), 1.0) * 4.3
    return per_month * metrics.median_views(c)


def affiliate_estimate(c: dict, listing: dict) -> dict:
    b = listing.get("budget") or {}
    per_order = b.get("avg_order", 1_200) * b.get("commission_pct", 8) / 100
    views = monthly_views(c)
    intent = 2.5 if c["niche"] in ("food", "parenting", "beauty", "tech") else 1.0
    lo = views * 0.0012 * intent * 0.015 * per_order
    hi = views * 0.003 * intent * 0.03 * per_order
    return estimate(
        lo,
        hi,
        "inr",
        "month",
        [
            f"About {short(views)} views a month at your current posting pace",
            f"{0.12 * intent:.2g}% to {0.3 * intent:.2g}% of viewers tap the link; 1.5% to 3% of them buy",
            f"{b.get('commission_pct', 8)}% commission on a typical {inr(b.get('avg_order', 1_200))} order",
        ],
        "low" if not metrics.has_reels(c) else "medium",
    )


def value_for(c: dict, listing: dict, lister: dict) -> dict | None:
    kind = listing.get("deal_kind")
    b = listing.get("budget") or {}
    terms = {k: listing.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}
    if kind == "affiliate":
        return {"kind": "affiliate", "estimate": affiliate_estimate(c, listing), "fair": None}
    if kind in ("collab", "revenue_share") and not b:
        return {"kind": "growth", "estimate": None, "fair": None}
    fp = fair_price(c, lister, terms, with_model=False)
    total = fp["total"]
    if listing["type"] == "collective":
        size = listing.get("collective_size") or 15
        cap = (b.get("total") or total * size) / size * 2.2
        share = max(min(total, cap), PRODUCTION_FLOOR * 1.5)
        return {
            "kind": "collective",
            "fair": fp,
            "estimate": estimate(
                share * 0.9,
                share * 1.1,
                "inr",
                "deal",
                [
                    f"Your share of a {size}-creator pack, priced on your reach",
                    "Paid from one escrow payment, split automatically",
                ],
                fp["estimate"]["confidence"],
            ),
        }
    lo_b, hi_b = b.get("per_creator_min"), b.get("per_creator_max")
    if lo_b is None:
        return {"kind": "paid", "fair": fp, "estimate": fp["estimate"]}
    # Brands pay at least their stated minimum; above it, up to your fair price.
    hi = max(lo_b, min(hi_b, total) if hi_b else total)
    lo = min(max(lo_b, total * 0.6), hi)
    return {
        "kind": "paid",
        "fair": fp,
        "estimate": estimate(
            lo,
            hi,
            "inr",
            "deal",
            [f"Listing budget {inr_range(lo_b, hi_b)} per creator", f"Your fair price for these deliverables is {inr(total)}"],
            fp["estimate"]["confidence"],
        ),
        "budget_below_fair": bool(hi_b and hi_b < total * 0.7),
    }


def matched(c: dict, limit: int | None = None, include_flagged: bool = False) -> dict:
    db = get_db()
    listers = {b["_id"]: b for b in db.brands.find({})}
    creators = {x["_id"]: x for x in db.creators.find({"_id": {"$regex": "^cr_"}}, {"name": 1, "handle": 1, "niche": 1, "languages": 1, "region": 1, "audience": 1})}
    taken = {d["listing_id"] for d in db.deals.find({"creator_id": c["_id"]})}
    flags = scan()
    items, hidden = [], []
    for listing in db.listings.find({"status": "open"}):
        if listing["owner_id"] == c["_id"]:
            continue
        if is_flagged(listing["_id"]) and not include_flagged:
            hidden.append({"id": listing["_id"], "title": listing["title"], "reasons": flags[listing["_id"]]["reasons"]})
            continue
        lister = listers.get(listing["owner_id"])
        if lister is None and listing["owner_id"] in creators:
            owner = creators[listing["owner_id"]]
            lister = {
                "_id": owner["_id"],
                "name": owner["name"],
                "kind": "creator",
                "niches": [owner["niche"]],
                "target": {"languages": owner.get("languages", []), "regions": [owner.get("region")], "ages": [], "cities": []},
            }
        if lister is None:
            continue
        fit = listing_fit(c, listing, lister)
        if fit["score"] < 45:
            continue
        val = value_for(c, listing, lister)
        items.append(
            {
                "id": listing["_id"],
                "type": listing["type"],
                "type_label": TYPE_LABELS[listing["type"]],
                "title": listing["title"],
                "summary": listing["summary"],
                "lister": {"id": lister["_id"], "name": lister["name"], "kind": lister.get("kind"), "hue": lister.get("hue", 260), "verified": lister.get("verified", True)},
                "niches": [NICHES[n]["label"] for n in listing.get("niches", []) if n in NICHES],
                "languages": listing.get("languages", []),
                "regions": listing.get("regions", []),
                "deal_kind": listing.get("deal_kind"),
                "deliverables": listing.get("deliverables"),
                "usage_rights_days": listing.get("usage_rights_days", 0),
                "deadline": listing.get("deadline"),
                "collective_size": listing.get("collective_size"),
                "budget": listing.get("budget"),
                "fit": fit["score"],
                "applied": listing["_id"] in taken,
                "value": {k: v for k, v in (val or {}).items() if k != "fair"},
                "fair_total": (val or {}).get("fair", {}).get("total") if val and val.get("fair") else None,
                "why": why(
                    fit["reasons"][:3] + [f"Watch out: {x[0].lower()}{x[1:]}" for x in fit["cautions"][:1]],
                    [inp("Fit", f"{fit['score']}/100", "simulated" if fit["simulated"] else None)],
                    ["audience demographics"] if fit["simulated"] else [],
                    title=f"Why {listing['title']} fits",
                ),
            }
        )
    items.sort(key=lambda x: (x["applied"], -x["fit"]))
    if limit:
        items = items[:limit]
    return {"items": items, "hidden": hidden}
