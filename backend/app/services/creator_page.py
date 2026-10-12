"""The public creator page: badges backed by data, past collaborations, top posts,
Fan Proof, case studies and an estimated price. Everything here respects the
creator's sharing settings (`public_scopes`) and never includes private fields.

Badges appear only when data backs them. "Paid" counts never appear: payouts aren't
connected to a verified provider. Case studies use the predicted views stored when
the offer was accepted and actual views from the platform API (self-reported numbers
are labelled); "paid in X days" only from verified payment events.
"""
from __future__ import annotations

import re
from datetime import date, datetime

from ..db import get_db
from ..engines import metrics
from ..engines.common import short
from ..engines.fair_price import deliverables_label, fair_price
from ..seed.catalog import NICHES
from . import fan_proof
from .profile import connected_platforms
from .views import source_of

DONE = ("verified", "paid")
MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]


def _month(iso: str | None) -> str | None:
    try:
        d = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return f"{MONTHS[d.month - 1]} {d.year}"


def _completed(creator_id: str) -> list[dict]:
    return list(get_db().deals.find({"creator_id": creator_id, "stage": {"$in": list(DONE)}}))


def _deadline(d: dict) -> date | None:
    """The deal's posting deadline: its own, else its campaign's."""
    raw = d.get("post_by")
    if not raw and d.get("listing_id"):
        x = get_db().listings.find_one({"_id": d["listing_id"]}, {"deadline": 1})
        raw = (x or {}).get("deadline")
    try:
        return date.fromisoformat(raw) if raw else None
    except ValueError:
        return None


def _submitted(d: dict) -> date | None:
    """When the post was first submitted."""
    first = next((e["at"] for e in d.get("timeline") or [] if e.get("stage") == "live"), None) or d.get("submitted_at")
    try:
        return datetime.fromisoformat(first.replace("Z", "+00:00")).date() if first else None
    except ValueError:
        return None


def badges(c: dict) -> list[dict]:
    db = get_db()
    out = []
    linked = connected_platforms(c)
    if linked:
        out.append({"key": "connected", "label": "Connected audience", "detail": f"{', '.join(p.capitalize() for p in linked)} through the official API", "sample": False})
    deals = [d for d in db.deals.find({"creator_id": c["_id"], "stage": {"$in": ["live", *DONE]}})]
    timed = [(d, _deadline(d), _submitted(d)) for d in deals]
    timed = [(d, dl, sub) for d, dl, sub in timed if dl and sub]
    if timed:
        on_time = sum(1 for _, dl, sub in timed if sub <= dl)
        # Counted, not rounded to a percentage: "100%" reads as a promise (copy rules).
        out.append({"key": "on_time", "label": f"On time: {on_time} of {len(timed)} post{'s' if len(timed) != 1 else ''}", "detail": "Posts submitted by their deadline",
                    "percent": round(on_time / len(timed) * 100), "sample": any(d.get("source") == "synthetic" for d, _, _ in timed)})
    done = _completed(c["_id"])
    if done:
        out.append({"key": "completed", "label": f"Completed on JodiDar ×{len(done)}", "detail": "Posts approved by the brand", "sample": any(d.get("source") == "synthetic" for d in done)})
    rated = [d for d in done if (d.get("rating") or {}).get("stars")]
    if rated:
        avg = sum(d["rating"]["stars"] for d in rated) / len(rated)
        out.append({"key": "rating", "label": f"Brand rating {avg:.1f}/5", "detail": f"From {len(rated)} brand{'s' if len(rated) != 1 else ''} after completed deals", "sample": any(d.get("source") == "synthetic" for d in rated)})
    joined = list(db.deals.find({"creator_id": c["_id"], "kind": "collective", "stage": {"$nin": ["offer", "declined"]}}, {"source": 1}))
    if joined:  # accepted a place in a collective
        out.append({"key": "collective", "label": "Collective member", "detail": "Accepted a place in a creator collective on JodiDar", "sample": any(d.get("source") == "synthetic" for d in joined)})
    return out


def collaborations(c: dict) -> list[dict]:
    db = get_db()
    rows = []
    for d in sorted(_completed(c["_id"]), key=lambda d: d.get("created_at") or "", reverse=True):
        b = db.brands.find_one({"_id": d["brand_id"]}, {"name": 1, "slug": 1})
        if not b:
            continue
        done_at = next((e["at"] for e in reversed(d.get("timeline") or []) if e.get("stage") in DONE), d.get("created_at"))
        rows.append({"brand": b["name"], "slug": b.get("slug"), "month": _month(done_at), "deliverables": deliverables_label({"deliverables": d.get("deliverables")}),
                     "sample": d.get("source") == "synthetic"})
    return rows[:12]


def top_posts(c: dict, n: int = 6) -> list[dict]:
    """The most-viewed posts synced through the official APIs."""
    posts = get_db().posts.find({"creator_id": c["_id"], "source": {"$in": list(fan_proof.API_SOURCES)}, "views": {"$ne": None}}).sort("views", -1).limit(n)
    out = []
    for p in posts:
        text = (p.get("title") or p.get("caption") or "").strip().splitlines()[0] if (p.get("title") or p.get("caption")) else ""
        out.append({"platform": p["platform"], "url": p.get("permalink"), "text": text[:90], "views": p.get("views"), "views_label": short(p.get("views") or 0),
                    "published_at": p.get("published_at"), "source": p["source"]})
    return out


def fan_badges(c: dict) -> list[dict]:
    db = get_db()
    seen: dict[str, dict] = {}
    for doc in db.fan_proof.find({"creator_id": c["_id"]}):
        seen.setdefault(doc["brand_id"], doc)
    out = []
    for bid in list(seen)[:6]:
        b = db.brands.find_one({"_id": bid, "removed": {"$ne": True}}, {"name": 1, "slug": 1})
        s = fan_proof.summary(c["_id"], bid)
        if b and s:
            out.append({"brand": b["name"], "slug": b.get("slug"), "label": s["label"]})
    return out


_IG = re.compile(r"instagram\.com/(?:reel|reels|p)/([A-Za-z0-9_-]+)")
_YT = re.compile(r"(?:youtube\.com/(?:watch\?v=|shorts/)|youtu\.be/)([A-Za-z0-9_-]{6,})")


def _post_key(url: str | None) -> str | None:
    if not url:
        return None
    m = _IG.search(url) or _YT.search(url)
    return m.group(1) if m else None


def actual_views(d: dict) -> dict | None:
    """The submitted post's views from the platform API, else the creator's own number (labelled)."""
    key = _post_key(d.get("proof_url"))
    if key:
        for p in get_db().posts.find({"creator_id": d["creator_id"], "source": {"$in": list(fan_proof.API_SOURCES)}}, {"permalink": 1, "views": 1, "source": 1, "post_id": 1}):
            if p.get("views") is not None and key in ((p.get("permalink") or "") + " " + str(p.get("post_id"))):
                return {"views": p["views"], "source": p["source"]}
    r = d.get("result") or {}
    if r.get("views") is not None:
        return {"views": r["views"], "source": "manual"}
    return None


def paid_in_days(d: dict) -> int | None:
    """Only from a payout a verified provider event confirmed; nothing else counts."""
    p = d.get("payout") or {}
    if p.get("status") != "paid" or not p.get("verified_event"):
        return None
    approved = next((e["at"] for e in d.get("timeline") or [] if e.get("stage") == "verified"), None)
    try:
        return (datetime.fromisoformat(p["at"]) - datetime.fromisoformat(approved)).days if approved else None
    except (KeyError, ValueError):
        return None


def case_studies(c: dict) -> list[dict]:
    db = get_db()
    out = []
    for d in _completed(c["_id"]):
        pred = d.get("predicted") or {}
        if not pred.get("views"):
            continue
        b = db.brands.find_one({"_id": d["brand_id"]}, {"name": 1})
        actual = actual_views(d)
        row = {"brand": (b or {}).get("name"), "predicted_views": pred["views"], "predicted_label": short(pred["views"]), "predicted_source": pred.get("source"),
               "actual_views": actual["views"] if actual else None, "actual_label": short(actual["views"]) if actual else None,
               "actual_source": actual["source"] if actual else None, "sample": d.get("source") == "synthetic"}
        days = paid_in_days(d)
        if days is not None:
            row["paid_in_days"] = days
        out.append(row)
    return out[:6]


def estimate(c: dict) -> dict:
    fp = fair_price(c, None, {"deliverables": [{"kind": "reel", "count": 1}]}, with_model=False)
    return {"range": fp["range"], "deliverables": fp["deliverables"], "label": "Estimated range", "data_label": fp["data_label"], "data_source": fp["data_source"]}


def public_extras(c: dict, pub: dict) -> dict:
    """What the full public page adds to the media kit, under the sharing settings."""
    niche = NICHES[c["niche"]]["label"]
    branding = c.get("branding") or {}
    return {
        "niche_tags": [niche, *[s for s in c.get("sub_niches") or [] if s]][:6],
        "positioning": branding.get("positioning") if branding.get("show_on_page") else None,
        "badges": badges(c),
        "collaborations": collaborations(c) if pub.get("collabs", True) else None,
        "top_posts": top_posts(c) if pub.get("stats") else None,
        "fan_badges": fan_badges(c),
        "case_studies": case_studies(c) if pub.get("stats") and pub.get("collabs", True) else None,
        "estimate": estimate(c) if pub.get("rates") else None,
        "median_source": source_of(c, "reels.0.views") if metrics.has_reels(c) else None,
    }
