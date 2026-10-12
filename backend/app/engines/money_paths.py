"""Ranked monetisation paths: brand collaborations, services, digital products,
affiliate, PR, collectives and page features. Each has a fit, an effort, a
rupee range per month with its assumptions, and why it suits this creator.

Expertise-first: creators under 1K followers with a real skill see services
and digital products first, and audience-led income later.
"""
from __future__ import annotations

import math

from ..db import get_db
from ..seed.catalog import NICHES
from ..services.campaigns import LIVE_QUERY
from . import metrics
from .common import clamp, estimate, inp, inr, inr_range, short, why
from .opportunities import affiliate_estimate, monthly_views

EFFORT_EASE = {"S": 1.0, "M": 0.6, "L": 0.3}

DIGITAL = {
    "food": ("recipe e-book", 199),
    "anime_edits": ("editing preset pack", 199),
    "gaming": ("settings and sensitivity guide", 149),
    "finance": ("budgeting template pack", 299),
    "tech": ("project-based mini course", 499),
    "fitness": ("4-week home workout plan", 299),
    "education": ("revision notes pack", 99),
    "fashion": ("festive styling guide", 149),
    "beauty": ("skincare routine guide", 149),
    "comedy": ("sketch-writing template", 99),
    "travel": ("itinerary pack", 199),
    "parenting": ("lunchbox recipe book", 149),
}
# Share of monthly viewers who buy a low-priced product, by how practical the niche is.
DIGITAL_INTENT = {"food": 1.0, "finance": 1.2, "tech": 1.2, "education": 1.2, "fitness": 1.0, "parenting": 1.0,
                  "travel": 0.8, "beauty": 0.7, "fashion": 0.6, "gaming": 0.3, "anime_edits": 0.12, "comedy": 0.15}
DIGITAL_FIT = {"food": 0.85, "finance": 0.85, "tech": 0.85, "education": 0.85, "fitness": 0.8, "parenting": 0.8,
               "travel": 0.65, "beauty": 0.6, "fashion": 0.55, "gaming": 0.5, "anime_edits": 0.55, "comedy": 0.3}
SERVICES = {
    "food": ("Online cooking class", 299, "students"),
    "anime_edits": ("Editing for other creators", 2_500, "edits"),
    "gaming": ("Coaching sessions", 500, "sessions"),
    "finance": ("Paid tax-filing help", 999, "clients"),
    "tech": ("Freelance build or code review", 3_000, "projects"),
    "fitness": ("Online classes", 499, "students"),
    "education": ("Doubt-clearing sessions", 299, "students"),
    "fashion": ("Personal styling calls", 799, "clients"),
    "beauty": ("Skincare consults", 599, "clients"),
    "comedy": ("Scriptwriting for brands", 3_000, "scripts"),
    "travel": ("Trip planning", 999, "clients"),
    "parenting": ("Meal-plan consults", 499, "clients"),
}


def _income_score(mid: float, goal: float) -> float:
    return clamp(math.sqrt(max(mid, 0) / max(goal, 1)), 0, 1)


def _listings(niche: str):
    db = get_db()
    return list(db.listings.find({"status": LIVE_QUERY, "niches": niche, "owner_id": {"$not": {"$regex": "^xx_"}}}))


def build(c: dict, fair_any: dict, opps: list[dict]) -> list[dict]:
    niche = c["niche"]
    label = NICHES[niche]["label"].lower()
    followers = c.get("followers", 0)
    goal = (c.get("income_goal") or {}).get("monthly", 10_000)
    expert_first = followers < 1_000 and bool(c.get("expertise"))
    listings = _listings(niche)
    lang = (c.get("languages") or ["en"])[0]
    lang_name = {"ta": "Tamil", "te": "Telugu", "kn": "Kannada", "ml": "Malayalam", "bn": "Bengali", "mr": "Marathi", "hi": "Hindi", "gu": "Gujarati"}.get(lang, "")
    sources = set(metrics.income_by_source(c))
    paths = []

    # Brand collaborations at a reach-based rate.
    dpm = metrics.brand_deals_per_month(c)
    lo_d, hi_d = (max(0.5, dpm * 0.6), max(1.0, dpm * 1.4)) if dpm else (0.25, 1.0)
    per = fair_any["range"]
    rate = c.get("current_rate")
    underpriced = bool(rate and rate < 0.7 * per["low"])
    brand_fit = clamp(0.35 + 0.55 * clamp(metrics.median_views(c) / 50_000, 0, 1) + (0.1 if dpm else 0), 0, 0.95)
    if expert_first:
        brand_fit = 0.15
    paths.append(
        {
            "type": "brand",
            "title": "Brand reels at your fair rate" if underpriced else "Brand collaborations",
            "fit": brand_fit,
            "effort": "S" if dpm else "M",
            "estimate": estimate(
                lo_d * per["low"],
                hi_d * per["high"],
                "inr",
                "month",
                [
                    f"{lo_d:.1f} to {hi_d:.1f} brand deals a month"
                    + (f" (you averaged {dpm:.1f} over the last 6 months)" if dpm else ""),
                    f"Each at your fair rate of {inr_range(per['low'], per['high'])} a reel",
                ],
                "medium" if dpm else "low",
            ),
            "reasons": (
                [
                    f"Brands already come to you: {round(dpm * 6)} deals in 6 months.",
                    f"You're quoting about {inr(rate)}; your reach supports {inr_range(per['low'], per['high'])}.",
                ]
                if underpriced
                else [f"Your reels reach about {short(metrics.median_views(c))} people, which brands pay for."]
                if not expert_first
                else ["With under 1K followers, brand budgets will be small for now. Your expertise earns sooner."]
            ),
            "first_step": "Quote your fair rate with the price breakdown" if underpriced else "Share your media kit with 3 matched brands",
            "simulated": metrics.fields_simulated(c, "income_history", "current_rate") if dpm else [],
        }
    )

    # Affiliate.
    aff = next((x for x in listings if x.get("deal_kind") == "affiliate"), None)
    if aff:
        owner = get_db().brands.find_one({"_id": aff["owner_id"]}) or {}
        est = affiliate_estimate(c, aff)
        product = owner.get("category", "product").lower()
        paths.append(
            {
                "type": "affiliate",
                "title": f"{owner.get('category', 'Product')} affiliate link".replace("Anime merch store", "Anime-merch"),
                "fit": 0.85,
                "effort": "S",
                "estimate": est,
                "reasons": [
                    f"{owner.get('name')} pays {aff['budget'].get('commission_pct')}% on every sale from your link.",
                    f"Your audience already watches {label}; {product} fits what you post.",
                    "Recurring income that doesn't depend on landing the next brand deal.",
                ],
                "first_step": f"Add the {owner.get('name')} link to your bio and pin it on your next reel",
                "listing_id": aff["_id"],
                "simulated": [],
            }
        )

    # Collectives.
    coll = [o for o in opps if o["type"] == "collective"]
    if coll:
        best = max(coll, key=lambda o: o["fit"])
        share = best["value"]["estimate"]
        per_month = (0.5, 2.0) if followers < 10_000 else (0.25, 1.0)
        paths.append(
            {
                "type": "collective",
                "title": {"food": "Food collectives", "anime_edits": "Gaming and anime collectives", "gaming": "Gaming collectives"}.get(
                    niche, f"{NICHES[niche]['label']} collectives"
                ),
                "fit": 0.9 if followers < 50_000 else 0.6,
                "effort": "S",
                "estimate": estimate(
                    share["low"] * per_month[0],
                    share["high"] * per_month[1],
                    "inr",
                    "month",
                    [
                        f"{per_month[0]:g} to {per_month[1]:g} collective deals a month",
                        f"Your share is priced on your reach: {inr_range(share['low'], share['high'])} per deal",
                        "One escrow payment from the brand, split among the members",
                    ],
                    "medium",
                ),
                "reasons": [
                    f"Brands book small creators together. {best['lister']['name']} has one open now ({best['collective_size']} creators).",
                    "You get a big-brand deal without needing a big following.",
                ],
                "first_step": f"Opt in to '{best['title']}'",
                "listing_id": best["id"],
                "simulated": [],
            }
        )

    # Digital product.
    prod, price = DIGITAL[niche]
    top = metrics.by_topic(c)
    top_saved = max(top, key=lambda t: t["save_rate"] or 0) if top else None
    best_topic = top_saved["topic"] if top_saved else None
    saves_known = bool(top_saved) and top_saved["save_rate"] is not None  # YouTube videos don't report saves
    if niche == "food" and best_topic == "Quick breakfast":
        prod = f"{lang_name} quick-breakfast e-book".strip()
    views = monthly_views(c)
    intent = DIGITAL_INTENT[niche] * (3 if expert_first else 1)
    # Small products sell mostly to engaged followers, plus a sliver of wider viewers.
    buyers_lo = (followers * 0.0008 + views * 0.0001) * intent
    buyers_hi = (followers * 0.002 + views * 0.0003) * intent
    paths.append(
        {
            "type": "digital",
            "title": f"₹{price} {prod}",
            "fit": clamp(DIGITAL_FIT[niche] + (0.1 if c.get("expertise") else 0), 0, 0.95),
            "effort": "M",
            "estimate": estimate(
                buyers_lo * price,
                buyers_hi * price,
                "inr",
                "month",
                [
                    f"{max(1, round(buyers_lo))} to {max(2, round(buyers_hi))} buyers a month at ₹{price}",
                    f"Mostly from your {short(followers)} {metrics.audience_noun(c)}, plus some of your {short(views)} monthly views",
                    "Sold through a UPI checkout link in your bio",
                ],
                "low",
            ),
            "reasons": (
                [f"People save your {metrics.topic_plural(best_topic)} to come back to. A {prod} packages them."]
                if saves_known and niche in ("food", "finance", "education", "fitness", "tech", "parenting")
                else ["A small product earns between brand deals."]
            )
            + [f"A low price (₹{price}) keeps the decision easy for your audience."],
            "first_step": f"Outline 10 {metrics.topic_name(best_topic) if best_topic else 'favourite'} recipes for the e-book" if niche == "food" else f"Draft the {prod} outline",
            "simulated": metrics.fields_simulated(c, "reels.saves") if saves_known else [],
        }
    )

    # Services.
    svc, svc_price, unit = SERVICES[niche]
    has_skill = bool(c.get("expertise")) or bool(c.get("skills"))
    lo_n, hi_n = (2, 6) if niche in ("anime_edits", "tech", "comedy") else (5, 15)
    svc_fit = 0.95 if expert_first else 0.75 if c.get("expertise") else 0.6 if has_skill else 0.3
    if c.get("expertise") and niche == "finance":
        svc = "Paid tax-filing help"
    paths.append(
        {
            "type": "services",
            "title": svc,
            "fit": svc_fit,
            "effort": "S" if expert_first else "L",
            "estimate": estimate(
                lo_n * svc_price,
                hi_n * svc_price,
                "inr",
                "month",
                [f"{lo_n} to {hi_n} {unit} a month at ₹{svc_price:,} each", "Booked through your link-in-bio page"],
                "low",
            ),
            "reasons": (
                [f"You're a {c['expertise'].lower()}; people pay for that before you have an audience."]
                if expert_first
                else [f"Your skill ({(c.get('expertise') or (c.get('skills') or ['your craft'])[0]).lower()}) is worth paying for directly."]
                if has_skill
                else ["A direct service can earn steadily alongside content."]
            ),
            "first_step": "Put a booking button on your link-in-bio page",
            "simulated": metrics.fields_simulated(c, "skills") if c.get("skills") else [],
        }
    )

    # PR and events.
    pr = [o for o in opps if o["type"] == "pr_service"]
    if pr:
        best = max(pr, key=lambda o: o["fit"])
        est = best["value"]["estimate"]
        paths.append(
            {
                "type": "pr",
                "title": "PR and event coverage",
                "fit": 0.6 if followers >= 5_000 else 0.3,
                "effort": "M",
                "estimate": estimate(est["low"] * 0.25, est["high"] * 0.5, "inr", "month", ["One event every 2 to 4 months", f"{inr_range(est['low'], est['high'])} per event"], "low"),
                "reasons": [f"{best['lister']['name']} is looking for {label} creators: {best['title']}."],
                "first_step": f"Apply to '{best['title']}'",
                "listing_id": best["id"],
                "simulated": [],
            }
        )

    # Paid features on pages.
    pages = [o for o in opps if o["type"] == "page" and o["value"].get("estimate")]
    if pages:
        best = max(pages, key=lambda o: o["fit"])
        est = best["value"]["estimate"]
        paths.append(
            {
                "type": "page",
                "title": "Paid features on pages",
                "fit": 0.5,
                "effort": "S",
                "estimate": estimate(est["low"] * 0.5, est["high"] * 2, "inr", "month", ["Half a feature to 2 features a month", f"{inr_range(est['low'], est['high'])} per feature"], "low"),
                "reasons": [f"{best['lister']['name']} pays for features and credits you, which also brings followers."],
                "first_step": f"Send a reel to {best['lister']['name']}",
                "listing_id": best["id"],
                "simulated": [],
            }
        )

    for p in paths:
        mid = (p["estimate"]["low"] + p["estimate"]["high"]) / 2
        p["score"] = round(0.45 * p["fit"] + 0.35 * _income_score(mid, goal) + 0.20 * EFFORT_EASE[p["effort"]], 4)
        p["fit_score"] = int(round(p["fit"] * 100))
        p["active"] = p["type"] in sources
        p["why"] = why(
            p["reasons"],
            [inp("Fit", f"{p['fit_score']}/100"), inp("Effort", {"S": "Small", "M": "Medium", "L": "Large"}[p["effort"]])],
            p.pop("simulated"),
            title=f"Why {p['title'].lower() if p['type'] != 'digital' else 'a ' + p['title']}",
            source="Ranked by 45% fit, 35% income against your goal, 20% ease.",
        )
    paths.sort(key=lambda p: p["score"], reverse=True)
    for i, p in enumerate(paths):
        p["rank"] = i + 1
    return paths


def next_stream(paths: list[dict]) -> dict | None:
    """The best-ranked path the creator doesn't earn from yet."""
    for p in paths:
        if not p["active"] and p["type"] != "brand":
            return {"type": p["type"], "title": p["title"], "estimate": p["estimate"], "first_step": p["first_step"]}
    return None


def goal_summary(c: dict, paths: list[dict]) -> dict:
    goal = (c.get("income_goal") or {}).get("monthly", 10_000)
    top = paths[:3]
    lo = sum(p["estimate"]["low"] for p in top)
    hi = sum(p["estimate"]["high"] for p in top)
    return {
        "goal": goal,
        "top3": estimate(
            lo,
            hi,
            "inr",
            "month",
            [f"You pursue {', '.join(p['title'].lower() if p['type'] != 'digital' else 'a ' + p['title'] for p in top)}", "Each path's own assumptions hold"],
            "low",
        ),
        "reachable": hi >= goal,
    }
