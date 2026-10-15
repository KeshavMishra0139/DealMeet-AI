"""Fair-Price AI: a fair rupee rate per creator-brand match, priced on reach.

base = median views of the last 6 reels x the niche's rupees per 1,000 views
then capped adjustments for engagement quality, audience fit to this brand,
consistency, brand safety, Trust Score and deal terms. Each step carries its
reason and the provenance of its inputs so the waterfall can explain itself.
"""
from __future__ import annotations

from ..seed.catalog import NICHES
from . import brand_safety, metrics
from .common import clamp, estimate, inp, inr, inr_full, nice_round, round_to, short, why
from .matching import audience_fit, redact, redact_cautions
from .trust import trust_score

# Each adjustment is capped so no single factor can swing the price wildly.
CAPS = {
    "engagement": (-0.15, 0.15),
    "fit": (-0.20, 0.12),
    "consistency": (-0.08, 0.08),
    "safety": (-0.15, 0.0),
    "trust": (-0.20, 0.05),
    "terms": (0.0, 0.40),
    # The AI market review (ai/price_review.py): what the formula can't see, within these bounds.
    "ai": (-0.30, 0.40),
}
# The common follower-count rule of thumb for micro creators (rupees per follower).
FOLLOWER_RATE = 0.33
# Minimum fee per reel-equivalent: making a reel takes hours, whatever the reach.
PRODUCTION_FLOOR = 1_000
DELIVERABLE_UNITS = {"reel": 1.0, "video": 1.0, "short": 1.0, "story": 0.25, "carousel": 0.6, "link_in_bio": 0.15, "live": 1.2}


def _pct(v: float) -> str:
    return f"{'+' if v > 0 else ''}{v * 100:.0f}%"


def reach_base(median_views: float, niche: str) -> float:
    """The price's starting point: median views x the niche's rupees per 1,000 views."""
    return median_views / 1000 * NICHES[niche]["cpm"]


# How many recent videos a public estimate needs before it prices anything.
PUBLIC_MIN_VIDEOS = 3


def public_estimate(views: list[int], niche: str, fmt: str, newest_excluded: int = 0) -> dict:
    """An estimate from public numbers only (a channel's recent views), for a linked
    channel. Same base and production floor as fair_price; with no
    engagement, audience or trust data there are no adjustments, so the range is wider
    and the confidence lower. Too few videos -> no price, and it says so."""
    label = {"shorts": "Shorts", "long": "long videos"}[fmt]
    if len(views) < PUBLIC_MIN_VIDEOS:
        return {
            "format": fmt,
            "enough_data": False,
            "videos": len(views),
            "reason": f"Not enough recent {label} to price: {len(views)} counted, at least {PUBLIC_MIN_VIDEOS} needed.",
        }
    from .common import safe_median

    mv = safe_median(views)
    base = reach_base(mv, niche)
    floor = base < PRODUCTION_FLOOR
    per = max(base, PRODUCTION_FLOOR)
    cpm = NICHES[niche]["cpm"]
    reasons = [
        f"Priced on the median views of your last {len(views)} {label}: {short(mv)} views. Subscribers don't set the price.",
        f"{inr(cpm)} per 1,000 views is DealMeet's seeded rate for {NICHES[niche]['label'].lower()}.",
        "Engagement, audience fit and trust aren't in public data, so nothing is adjusted for them. The range is wider for that reason.",
    ]
    if newest_excluded:
        reasons.append(f"{newest_excluded} video{'s' if newest_excluded != 1 else ''} from the last 3 days aren't counted yet: their views are still climbing.")
    if floor:
        reasons.append(f"Below this reach we price at least {inr_full(PRODUCTION_FLOOR)} per video, for the time it takes to make one.")
    return {
        "format": fmt,
        "enough_data": True,
        "videos": len(views),
        "median_views": round(mv),
        "per_video": round(per),
        "estimate": estimate(per * 0.85, per * 1.15, "inr", "deal", reasons[:2] + ["No engagement, fit or trust adjustments"], "low" if len(views) < 6 else "medium"),
        "why": reasons,
    }


def data_label(c: dict) -> tuple[str, str]:
    """(label, source) for what a creator's price is built from. Connecting an account
    changes the data source, not the certainty: the price stays an estimate."""
    if c.get("insights_source") == "instagram_api" and metrics.prov(c, "reels.0.views") == "real":
        return "Estimate from Instagram data", "instagram_api"
    if c.get("insights_source") == "youtube_api" and metrics.has_reels(c) and metrics.prov(c, "reels.0.views") == "real":
        return "Estimate from YouTube data", "youtube_api"
    if not metrics.has_reels(c):
        if (c.get("manual") or {}).get("avg_views"):
            return "Estimate from self-reported numbers", "manual"
        return f"Estimate from your {metrics.audience_noun(c)[:-1]} count", "manual"
    if metrics.recent_simulated(c, "views") or metrics.prov(c, "reels.0.views") in ("simulated", "seed") or c.get("insights_source") == "synthetic":
        return "Estimate from sample data", "synthetic"
    return "Estimate from self-reported numbers", "manual"


def follower_price(c: dict) -> int:
    return nice_round(c.get("followers", 0) * FOLLOWER_RATE)


def consistency_score(c: dict) -> float:
    cadence = clamp(metrics.posts_per_week(c) / 3, 0, 1)
    steadiness = 1 - clamp(metrics.views_cv(c) / 1.2, 0, 1)
    return 0.6 * cadence + 0.4 * steadiness


def factors(c: dict, lister: dict | None = None) -> dict:
    """Raw inputs to the price, also used to train and query the cross-check model."""
    niche = NICHES[c["niche"]]
    # Saves and shares aren't known for YouTube videos: the niche typical stands in (no adjustment).
    ss_known = metrics.ss_known(c)
    ss = metrics.ss_rate(c) if ss_known else niche["ss_bench"]
    fit = audience_fit(c, lister)["fit"] if lister else None
    t = trust_score(c)
    safety = brand_safety.assess(c)
    return {
        "median_views": metrics.median_views(c),
        "cpm": niche["cpm"],
        "ss_ratio": ss / niche["ss_bench"],
        "fit": fit,
        "consistency": consistency_score(c),
        "trust": t["score"] if t else 70,
        "safety_penalty": safety["penalty"],
        "safety": safety,
        "trust_detail": t,
        "ss": ss,
        "ss_known": ss_known,
    }


def adjustments(f: dict) -> dict:
    return {
        "engagement": clamp((f["ss_ratio"] - 1) * 0.20, *CAPS["engagement"]),
        "fit": clamp(((f["fit"] if f["fit"] is not None else 0.85) - 0.75) * 0.45, *CAPS["fit"]),
        "consistency": clamp((f["consistency"] - 0.45) * 0.25, *CAPS["consistency"]),
        "safety": clamp(-f["safety_penalty"], *CAPS["safety"]),
        "trust": clamp((f["trust"] - 75) / 100 * 0.25, *CAPS["trust"]),
    }


def terms_adjustment(terms: dict | None) -> tuple[float, float, list[str]]:
    """Returns (units, uplift, notes). Units scale the per-reel price; uplift covers rights."""
    terms = terms or {}
    deliverables = terms.get("deliverables") or [{"kind": "reel", "count": 1}]
    units = sum(DELIVERABLE_UNITS.get(d["kind"], 1.0) * d.get("count", 1) for d in deliverables)
    usage = terms.get("usage_rights_days") or 0
    excl = terms.get("exclusivity_days") or 0
    uplift = min(0.25, 0.05 * usage / 15) + min(0.30, 0.10 * excl / 30)
    uplift = clamp(uplift, *CAPS["terms"])
    notes = []
    if usage:
        notes.append(f"{usage} days of paid usage rights")
    if excl:
        notes.append(f"{excl} days of category exclusivity")
    return units, uplift, notes


DELIVERABLE_NAMES = {
    "reel": ("reel", "reels"),
    "video": ("video", "videos"),
    "short": ("short", "shorts"),
    "story": ("story", "stories"),
    "carousel": ("carousel", "carousels"),
    "link_in_bio": ("link in bio", "links in bio"),
    "live": ("live session", "live sessions"),
}


def deliverables_label(terms: dict | None) -> str:
    """[{reel, 1}, {story, 2}] -> '1 reel + 2 stories'"""
    ds = (terms or {}).get("deliverables") or [{"kind": "reel", "count": 1}]
    parts = []
    for d in ds:
        n = d.get("count", 1)
        one, many = DELIVERABLE_NAMES.get(d["kind"], (d["kind"], d["kind"] + "s"))
        parts.append(f"{n} {one if n == 1 else many}")
    return " + ".join(parts)


def fit_reason(fit: dict, scopes: dict | None = None) -> str:
    """Reason for the audience-fit step. With a brand's consent scopes, audience
    numbers the creator hasn't shared with that brand are left out."""
    if fit["reasons"]:
        notes = fit["reasons"] if scopes is None else redact(fit["reasons"], scopes)
    else:
        notes = fit["cautions"] if scopes is None else redact_cautions(fit["cautions"], scopes)
    return " ".join([f"Fit {fit['score']}/100."] + (["; ".join(notes[:2]) + "."] if notes else []))


def _ai_view(c: dict, review: dict | None) -> dict:
    from ..ai import price_review

    if not review:
        return {"status": price_review.status(c)}
    other = review.get("niche") if review.get("niche") in NICHES and review.get("niche") != c.get("niche") else None
    return {
        "status": "applied",
        "adjust_pct": review["adjust_pct"],
        "reasons": review["reasons"],
        "confidence": review["confidence"],
        "suggested_niche": other,
        "suggested_niche_label": NICHES[other]["label"] if other else None,
        "language": review.get("language"),
        "reviewed_at": review.get("reviewed_at"),
    }


def fair_price(
    c: dict,
    lister: dict | None = None,
    terms: dict | None = None,
    with_model: bool = True,
    scopes: dict | None = None,
    with_ai: bool = True,
) -> dict:
    """Fair price for one creator and lister. Pass `scopes` when the result goes
    to that brand, so its step reasons respect what the creator shared. With `with_ai`,
    a stored AI market review for the creator's current numbers is applied as a capped step."""
    niche = NICHES[c["niche"]]
    if not (terms or {}).get("deliverables"):
        # One post in the creator's own format: a video on YouTube, a reel on Instagram (same units).
        terms = {**(terms or {}), "deliverables": [{"kind": metrics.post_noun(c), "count": 1}]}
    f = factors(c, lister)
    adj = adjustments(f)
    mv = f["median_views"]
    base = reach_base(mv, c["niche"])
    real_views = metrics.has_reels(c)
    sim_ss = metrics.fields_simulated(c, "reels.saves", "reels.shares")
    sim_aud = metrics.fields_simulated(c, "audience")
    sim_trust = metrics.fields_simulated(c, "follower_history", "comment_insights")
    sim_views = metrics.recent_simulated(c, "views") if real_views else []
    sim_dates = ["reel dates"] if real_views and metrics.window_simulated(c, "date") else []

    steps = [
        {
            "key": "base",
            "label": "Reach base",
            "pct": None,
            "amount": round(base),
            "reason": (
                f"Median of your last 6 {metrics.post_noun(c)}s is {short(mv)} views. At {inr(f['cpm'])} per 1,000 views for "
                f"{niche['label'].lower()}, that's {inr_full(base)}."
                if real_views
                else (
                    f"No connected {metrics.post_noun(c)}s yet, so we use the {short(mv)} average views you reported. At {inr(f['cpm'])} per 1,000 views, that's {inr_full(base)}."
                    if (c.get("manual") or {}).get("avg_views")
                    else f"No connected {metrics.post_noun(c)}s yet, so we estimate {short(mv)} views per {metrics.post_noun(c)} from your {metrics.audience_noun(c)[:-1]} count."
                )
            ),
            "simulated": bool(sim_views),
            "simulated_fields": sim_views,
            "estimated": not real_views,
        }
    ]
    running = base

    def add(key: str, label: str, reason: str, simulated: list[str] | None = None):
        nonlocal running
        pct = adj[key]
        amount = running * pct
        lo, hi = CAPS[key]
        steps.append(
            {
                "key": key,
                "label": label,
                "pct": round(pct, 4),
                "amount": round(amount),
                "reason": reason,
                "capped": abs(pct - lo) < 1e-9 or abs(pct - hi) < 1e-9,
                "cap": [lo, hi],
                "simulated": bool(simulated),
                "simulated_fields": simulated or [],
            }
        )
        running += amount

    ss_pct = f["ss"] * 100
    if f.get("ss_known", True) or not metrics.has_reels(c):
        engagement_reason = (
            f"{ss_pct:.1f}% of viewers save or share, against {niche['ss_bench'] * 100:.1f}% typical for the niche."
            if adj["engagement"] >= 0
            else f"{ss_pct:.1f}% of viewers save or share, below the {niche['ss_bench'] * 100:.1f}% niche typical."
        )
    else:
        engagement_reason = f"YouTube doesn't report saves or shares, so this uses the niche typical ({niche['ss_bench'] * 100:.1f}%): no change."
    add("engagement", "Engagement quality", engagement_reason, sim_ss if f.get("ss_known", True) else [])
    if lister:
        add("fit", f"Audience fit to {lister['name']}", fit_reason(audience_fit(c, lister), scopes), sim_aud)
    else:
        add("fit", "Audience fit", "Assumes a brand whose audience matches yours well (fit 85/100).", sim_aud)
    add(
        "consistency",
        "Consistency",
        f"{metrics.posts_per_week(c):.1f} {metrics.post_noun(c)}s a week over the last 4 weeks; views vary by {metrics.views_cv(c) * 100:.0f}% {metrics.post_noun(c)} to {metrics.post_noun(c)}.",
        sim_views + sim_dates,
    )
    safety = f["safety"]
    add(
        "safety",
        "Brand safety",
        safety["flags"][0]["label"] + ". " + safety["flags"][0]["fix"] if safety["flags"] else "No brand-safety concerns found.",
    )
    t = f["trust_detail"]
    add(
        "trust",
        "Trust Score",
        f"Trust {t['score']}/100: {t['reasons'][0].lower()}." if t else "Trust not yet measured; counted as 70/100.",
        sim_trust,
    )
    reach_per_reel = running  # what the market model is checked against
    review = None
    if with_ai:
        from ..ai import price_review

        review = price_review.current(c)
    if review:
        adj["ai"] = clamp(review["adjust_pct"] / 100, *CAPS["ai"])
        add("ai", "AI market review", " ".join(review["reasons"][:2]))
    if running < PRODUCTION_FLOOR:
        steps.append(
            {
                "key": "floor",
                "label": "Production floor",
                "pct": None,
                "amount": round(PRODUCTION_FLOOR - running),
                "reason": f"Below this reach we price at least {inr_full(PRODUCTION_FLOOR)} per {metrics.post_noun(c)} to cover the time it takes to make one.",
                "simulated": False,
            }
        )
        running = PRODUCTION_FLOOR
    per_reel = running

    units, uplift, notes = terms_adjustment(terms)
    if units != 1:
        amount = per_reel * (units - 1)
        steps.append(
            {
                "key": "deliverables",
                "label": "Deliverables",
                "pct": round(units - 1, 4),
                "amount": round(amount),
                "reason": f"{deliverables_label(terms)}: {units:g}x a single {metrics.post_noun(c)}.",
                "simulated": False,
            }
        )
        running += amount
    if uplift:
        amount = running * uplift
        steps.append(
            {
                "key": "terms",
                "label": "Usage rights and exclusivity",
                "pct": round(uplift, 4),
                "amount": round(amount),
                "reason": ", ".join(notes).capitalize() + f" ({_pct(uplift)}, capped at +40%).",
                "capped": uplift >= CAPS["terms"][1],
                "simulated": False,
            }
        )
        running += amount

    total = running
    lo, hi = round_to(total * 0.97, 500 if total >= 5_000 else 50), round_to(total * 1.03, 500 if total >= 5_000 else 50)
    simulated_fields = sorted({x for s in steps for x in s.get("simulated_fields", [])})
    confidence = "medium" if real_views else "low"
    if real_views and not simulated_fields and len(metrics.recent(c)) >= 6 and metrics.prov(c, "reels.0.views") == "real":
        confidence = "high"
    fp = follower_price(c)

    label, source = data_label(c)
    result = {
        "data_label": label,
        "data_source": source,
        "creator_id": c["_id"],
        "lister_id": lister["_id"] if lister else None,
        "lister_name": lister["name"] if lister else None,
        "deliverables": deliverables_label(terms),
        "base": round(base),
        "per_reel": round(per_reel),
        "total": round(total),
        "range": {"low": int(lo), "high": int(hi)},
        "steps": steps,
        "follower_price": fp,
        "follower_rate": FOLLOWER_RATE,
        "uplift_vs_followers": round(per_reel / fp, 2) if fp else None,
        "ai_review": _ai_view(c, review) if with_ai else None,
        "estimate": estimate(
            lo,
            hi,
            "inr",
            "deal",
            [
                f"Priced on the median of your last 6 {metrics.post_noun(c)}s ({short(mv)} views), not on {metrics.audience_noun(c)}",
                f"{inr(f['cpm'])} per 1,000 views is the seeded rate for {niche['label'].lower()}",
                "Each adjustment is capped so no single factor dominates",
            ]
            + ([f"An AI market review adjusted it by {_pct(adj['ai'])}, within -30% to +40%"] if review else []),
            confidence,
        ),
        "why": why(
            [
                f"Your price follows how many people actually watch: {short(mv)} median views.",
                f"Priced on {metrics.audience_noun(c)} alone it would be about {inr(fp)}.",
            ]
            + [s["reason"] for s in steps[1:3]],
            [
                inp(f"Median views (last 6 {metrics.post_noun(c)}s)", short(mv), metrics.prov(c, "reels.0.views") if real_views else None),
                inp("Rate per 1,000 views", inr(f["cpm"])),
                inp("Followers", short(c.get("followers", 0)), metrics.prov(c, "followers")),
            ],
            simulated_fields,
            title="How we priced this",
        ),
    }
    if with_model:
        from .price_model import cross_check

        reach_total = reach_per_reel * units * (1 + uplift)
        result["model_check"] = cross_check(f, adj, units, uplift, reach_total)
        result["model_check"]["checked_before_floor"] = reach_per_reel < PRODUCTION_FLOOR
    return result
