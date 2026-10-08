"""Builds everything the creator screens need from one creator record."""
from __future__ import annotations

from fastapi import HTTPException

from ..db import get_db
from ..engines import durable_income, hindi, money_paths, next_step, roadmap, stage
from ..engines.common import inp, inr, inr_range, short, why
from ..engines.fair_price import fair_price, follower_price
from ..engines.matching import audience_fit
from ..engines.opportunities import matched
from ..engines.trust import trust_score
from ..engines import metrics
from ..config import today
from datetime import date


def load_creator(creator_id: str) -> dict:
    c = get_db().creators.find_one({"_id": creator_id})
    if not c:
        raise HTTPException(404, "Creator not found")
    return c


def best_fit_brand(c: dict) -> dict | None:
    brands = [b for b in get_db().brands.find({"kind": "brand", "verified": True})]
    if not brands:
        return None
    # A brand whose main category is the creator's niche is the natural "well-fitting brand".
    return max(brands, key=lambda b: ((b.get("niches") or [None])[0] == c["niche"], audience_fit(c, b)["fit"], b["name"]))


def build(c: dict, with_plan: bool = True) -> dict:
    brand = best_fit_brand(c)
    fair = fair_price(c, brand)
    fair_any = fair_price(c, None, with_model=False)
    opps = matched(c)["items"]
    paths = money_paths.build(c, fair, opps)
    durable = durable_income.compute(c, money_paths.next_stream(paths))
    st = stage.detect(c, fair)
    gaps = roadmap.content_gaps(c)
    ctx = {"fair": fair, "fair_any": fair_any, "opps": opps, "paths": paths, "durable": durable, "stage": st, "gaps": gaps, "brand": brand}
    if with_plan:
        ctx["plan"] = next_step.current_plan(c, ctx)
    return ctx


def rate_gap(c: dict, fair: dict) -> dict:
    rate = c.get("current_rate")
    fp = follower_price(c)
    lo, hi = fair["range"]["low"], fair["range"]["high"]
    mid = (lo + hi) / 2
    if rate:
        gap = mid - rate
        line = (
            f"You're leaving about {inr(gap)} on each brand reel." if gap > 0 else "Your rate is in line with your reach."
        )
    else:
        gap = None
        line = "You haven't set a rate yet. Start here."
    return {
        "fair": fair["range"],
        "per_reel": fair["per_reel"],
        "current": rate,
        "follower_price": fp,
        "gap": round(gap) if gap is not None else None,
        "line": line,
        "line_hi": hindi.rate_gap_line(gap, rate),
        "brand": fair["lister_name"],
        "why": why(
            [
                f"Fair price for {fair['lister_name'] or 'a well-fitting brand'}: {inr_range(lo, hi)} a reel, priced on {short(metrics.median_views(c))} median views.",
                f"Priced on followers alone it would be about {inr(fp)}.",
            ]
            + ([f"Your typical deal is {inr(rate)}."] if rate else []),
            [
                inp("Typical deal", inr(rate) if rate else "Not set", metrics.prov(c, "current_rate") if rate else None),
                inp("Follower-based price", inr(fp)),
            ],
            metrics.fields_simulated(c, "current_rate") if rate else [],
            title="How we worked out your rate gap",
        ),
    }


def pipeline(c: dict) -> dict:
    db = get_db()
    deals = list(db.deals.find({"creator_id": c["_id"]}))
    brands = {b["_id"]: b for b in db.brands.find({})}
    offers, active, awaiting, alerts = [], [], [], []
    for d in deals:
        b = brands.get(d["brand_id"], {})
        item = {"id": d["_id"], "brand": b.get("name", "A brand"), "amount": d["amount"], "stage": d["stage"]}
        if d["stage"] == "offer":
            fp = fair_price(c, b or None, {k: d.get(k) for k in ("deliverables", "usage_rights_days", "exclusivity_days")}, with_model=False)
            below = 1 - d["amount"] / fp["total"] if fp["total"] else 0
            item["fair_total"] = fp["total"]
            item["below_pct"] = round(below * 100)
            offers.append(item)
            if below >= 0.3:
                alerts.append(
                    {
                        "kind": "low_offer",
                        "deal_id": d["_id"],
                        "text": f"{b.get('name', 'This')} offer is {round(below * 100)}% below your fair price",
                        "detail": f"{inr(d['amount'])} offered; fair is {inr(fp['total'])} for {fp['deliverables']}.",
                        "hi": hindi.alert("low_offer", brand=b.get("name"), pct=round(below * 100), amount=d["amount"], fair=fp["total"], deliverables=fp["deliverables"]),
                    }
                )
        elif d["stage"] in ("contract", "escrow_funded"):
            active.append(item)
        elif d["stage"] in ("live", "verified"):
            awaiting.append(item)
            due = d.get("verify_due")
            if due and due < today().isoformat():
                from . import deals as rail

                days = (today() - date.fromisoformat(due)).days
                release = rail.auto_release_due(d)
                left = (release - today()).days if release else 0
                alerts.append(
                    {
                        "kind": "verify_late",
                        "deal_id": d["_id"],
                        "text": f"{b.get('name', 'The brand')} is {days} day{'s' if days != 1 else ''} late confirming your post",
                        "detail": f"{inr(d['amount'])} is safe in escrow. We've nudged them; it auto-releases to you in {left} day{'s' if left != 1 else ''}.",
                        "hi": hindi.alert("verify_late", brand=b.get("name"), days=days, left=left, amount=d["amount"]),
                    }
                )
    for inv in db.invoices.find({"creator_id": c["_id"], "status": "unpaid"}):
        days = (today() - date.fromisoformat(inv["due"])).days
        if days > 0:
            awaiting.append({"id": inv["_id"], "brand": inv["to"], "amount": inv["amount"], "stage": "invoice"})
            alerts.append(
                {
                    "kind": "invoice_late",
                    "invoice_id": inv["_id"],
                    "text": f"{inr(inv['amount'])} invoice is {days} days late",
                    "detail": f"{inv['to']} was due to pay on {date.fromisoformat(inv['due']).strftime('%-d %b')}. Send a reminder with the invoice attached.",
                    "hi": hindi.alert("invoice_late", amount=inv["amount"], days=days, to=inv["to"], due=date.fromisoformat(inv["due"]).strftime("%-d %b")),
                }
            )
    return {
        "offers": offers,
        "active": active,
        "awaiting": awaiting,
        "awaiting_total": sum(x["amount"] for x in awaiting),
        "alerts": alerts,
    }


def context_line(c: dict) -> dict:
    return {
        "followers": c.get("followers", 0),
        "median_views": metrics.median_views(c),
        "has_reels": metrics.has_reels(c),
        "reach_ratio": round(metrics.reach_ratio(c), 1) if metrics.has_reels(c) else None,
        "trust": trust_score(c),
    }
