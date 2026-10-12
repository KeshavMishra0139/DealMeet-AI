"""The pricing form and saved rate cards.

An estimate per content format, built only from metrics the creator has. Each metric
it uses is listed with its source; each one it lacks is named with what the estimate
does instead. Nothing is invented. A saved rate card is the creator's own price for a
format ("Your rate"), kept next to the current "Estimated range".
"""
from __future__ import annotations

from ..config import now_iso
from ..db import get_db
from ..engines import metrics
from ..engines.common import inr_full, round_to, short
from ..engines.fair_price import DELIVERABLE_UNITS, data_label, deliverables_label, fair_price, terms_adjustment
from ..engines.trust import trust_score
from .views import source_of

# The formats a creator can price. "family" says which data prices it.
FORMATS: dict[str, dict] = {
    "reel": {"label": "Instagram reel", "unit": ("reel", "reels"), "family": "instagram"},
    "story": {"label": "Instagram story", "unit": ("story", "stories"), "family": "instagram"},
    "carousel": {"label": "Carousel post", "unit": ("carousel", "carousels"), "family": "instagram"},
    "live": {"label": "Live session", "unit": ("live session", "live sessions"), "family": "instagram"},
    "short": {"label": "YouTube Short", "unit": ("Short", "Shorts"), "family": "youtube_shorts"},
    "youtube_video": {"label": "YouTube video", "unit": ("video", "videos"), "family": "youtube_long"},
}
assert all(k in DELIVERABLE_UNITS for k, f in FORMATS.items() if f["family"] == "instagram")

MAX_CARDS = len(FORMATS)


def _metric(key: str, label: str, value: str, source: str, note: str | None = None) -> dict:
    return {"key": key, "label": label, "value": value, "source": source, "note": note}


def _missing(key: str, label: str, effect: str, fix: str, path: str) -> dict:
    return {"key": key, "label": label, "effect": effect, "fix": fix, "path": path}


def _youtube_posts(creator_id: str, fmt: str) -> list[dict]:
    return list(get_db().posts.find({"creator_id": creator_id, "platform": "youtube", "format": fmt}, {"_id": 0}))


def _youtube_estimate(c: dict, fmt: str) -> dict | None:
    """The public-data estimate for a linked channel's Shorts or long videos, or None."""
    yt = (c.get("channels") or {}).get("youtube")
    if not yt:
        return None
    from .youtube_public import prices_for

    return prices_for(_youtube_posts(c["_id"], fmt), c["niche"])[fmt]


def _instagram_metrics(c: dict) -> tuple[list[dict], list[dict]]:
    """(used, missing) for a price built by the fair-price engine."""
    used, missing = [], []
    manual = c.get("manual") or {}
    if c.get("followers"):
        used.append(_metric("followers", "Followers", short(c["followers"]), source_of(c, "followers")))
    else:
        missing.append(_missing("followers", "Followers", "Not used.", "Add your follower count", "/creator/profile"))
    if metrics.has_reels(c):
        n = len(metrics.recent(c))
        used.append(_metric("median_views", f"Median views, last {n} {metrics.post_word((metrics.recent(c) or [{}])[0].get('topic'))}", short(metrics.median_views(c)), source_of(c, "reels.0.views")))
        word = metrics.post_word((metrics.recent(c) or [{}])[0].get("topic"))
        if metrics.ss_known(c):
            ss = metrics.ss_rate(c)
            used.append(_metric("engagement", "Saves + shares per view", f"{ss * 100:.1f}%", source_of(c, "reels.0.saves")))
        else:
            missing.append(_missing("engagement", "Saves + shares per view", "YouTube doesn't report saves or shares, so the niche typical is used.", "Connect Instagram", "/creator/connections"))
        used.append(_metric("consistency", f"{word.capitalize()} a week, last 4 weeks", f"{metrics.posts_per_week(c):.1f}", source_of(c, "reels.0.date")))
    else:
        if manual.get("avg_views"):
            used.append(_metric("median_views", "Average views per post", short(manual["avg_views"]), "manual"))
        else:
            missing.append(
                _missing(
                    "median_views",
                    "Views per post",
                    f"Estimated from your follower count: about {short(metrics.median_views(c))} views a reel." if c.get("followers") else "Not used.",
                    "Connect Instagram, or add your average views",
                    "/creator/connections",
                )
            )
        missing.append(
            _missing(
                "engagement",
                "Saves and shares per view",
                "No engagement adjustment: counted as typical for your niche.",
                "Connect Instagram to measure it",
                "/creator/connections",
            )
        )
        missing.append(_missing("consistency", "Posting history", "Consistency counted as no recent reels.", "Connect Instagram", "/creator/connections"))
    if manual.get("engagement_pct") is not None:
        used.append(
            _metric(
                "engagement_rate",
                "Engagement rate",
                f"{manual['engagement_pct']:.1f}%",
                "manual",
                "Shown for reference. The price uses saves and shares per view, which this number doesn't measure.",
            )
        )
    if c.get("audience"):
        used.append(_metric("audience", "Audience demographics", "Available", source_of(c, "audience"), "Used when pricing for a specific brand."))
    else:
        missing.append(_missing("audience", "Audience demographics", "Audience fit assumed (85/100).", "Connect Instagram", "/creator/connections"))
    t = trust_score(c)
    if t:
        used.append(_metric("trust", "Trust Score", f"{t['score']}/100", source_of(c, "follower_history")))
    else:
        missing.append(_missing("trust", "Trust Score", "Counted as 70/100.", "Connect Instagram so follower history can be checked", "/creator/connections"))
    return used, missing


def estimate(c: dict, fmt: str, count: int = 1, usage_rights_days: int = 0, exclusivity_days: int = 0) -> dict:
    """The pricing form's answer for one format and set of terms."""
    spec = FORMATS[fmt]
    one, many = spec["unit"]
    terms = {"deliverables": [{"kind": fmt if fmt in DELIVERABLE_UNITS else "reel", "count": count}], "usage_rights_days": usage_rights_days, "exclusivity_days": exclusivity_days}
    label = f"{count} {one if count == 1 else many}"
    _, uplift, notes = terms_adjustment(terms)
    base = {"format": fmt, "format_label": spec["label"], "deliverables": label, "terms": notes, "count": count,
            "usage_rights_days": usage_rights_days, "exclusivity_days": exclusivity_days}

    yt_fmt = {"youtube_shorts": "shorts", "youtube_long": "long"}.get(spec["family"])
    yt = _youtube_estimate(c, yt_fmt) if yt_fmt else None
    if yt_fmt and yt and yt["enough_data"]:
        ch = c["channels"]["youtube"]
        per = yt["per_video"]
        total = per * count * (1 + uplift)
        step = 500 if total >= 5_000 else 50
        lo, hi = int(round_to(total * 0.85, step)), int(round_to(total * 1.15, step))
        used = [
            _metric("subscribers", "YouTube subscribers", "Hidden" if ch.get("subscribers_hidden") else short(ch.get("subscribers") or 0), "youtube_api"),
            _metric("median_views", f"Median views, last {yt['videos']} {'Shorts' if yt_fmt == 'shorts' else 'long videos'}", short(yt["median_views"]), "youtube_api"),
        ]
        missing = [
            _missing("engagement", "Engagement and audience", "Not in public YouTube data, so nothing is adjusted for them. The range is wider.", "Connect YouTube Analytics", "/creator/connections")
        ]
        assumptions = list(yt["why"])
        if notes:
            assumptions.append(f"{', '.join(notes).capitalize()}: +{uplift * 100:.0f}% (capped at +40%).")
        return {**base, "enough_data": True, "range": {"low": lo, "high": hi}, "data_label": "Estimate from YouTube data", "data_source": "youtube_api",
                "metrics": used, "missing": missing, "assumptions": assumptions, "steps": [], "confidence": yt["estimate"]["confidence"]}

    if spec["family"] == "youtube_long":
        why = yt["reason"] if yt else "No YouTube channel linked."
        return {**base, "enough_data": False, "range": None, "data_label": None, "data_source": None, "metrics": [],
                "missing": [_missing("median_views", "Views of your recent long videos", why, "Link your YouTube channel", "/creator/connections")],
                "assumptions": [], "steps": [], "confidence": None}

    used, missing = _instagram_metrics(c)
    has_views = metrics.has_reels(c) or (c.get("manual") or {}).get("avg_views") or c.get("followers")
    if not has_views:
        return {**base, "enough_data": False, "range": None, "data_label": None, "data_source": None, "metrics": used,
                "missing": missing, "assumptions": [], "steps": [], "confidence": None}

    fp = fair_price(c, None, terms, with_model=False)
    assumptions = list(fp["estimate"]["assumptions"])
    assumptions.append("Audience fit assumed at 85/100: a brand whose audience matches yours well. A specific brand's price can differ.")
    if fmt == "short":
        reason = yt["reason"] if yt else "No YouTube channel linked"
        assumptions.insert(0, f"Priced like a reel from your Instagram numbers. {reason.rstrip('.')}.")
    lbl, src = data_label(c)
    steps = [{"label": s["label"], "amount": s["amount"], "reason": s["reason"]} for s in fp["steps"]]
    return {**base, "deliverables": deliverables_label(terms) if fmt in DELIVERABLE_UNITS else label, "enough_data": True,
            "range": fp["range"], "data_label": lbl, "data_source": src, "metrics": used, "missing": missing,
            "assumptions": assumptions, "steps": steps, "confidence": fp["estimate"]["confidence"]}


# ------------------------------------------------------------------ saved rate cards
def _card_view(c: dict, card: dict) -> dict:
    now = estimate(c, card["format"], card["count"], card["usage_rights_days"], card["exclusivity_days"])
    return {
        "format": card["format"],
        "format_label": FORMATS[card["format"]]["label"],
        "deliverables": now["deliverables"],
        "terms": now["terms"],
        "count": card["count"],
        "usage_rights_days": card["usage_rights_days"],
        "exclusivity_days": card["exclusivity_days"],
        "amount": card["amount"],
        "note": card.get("note"),
        "source": card["source"],
        "saved_at": card["updated_at"],
        "estimate_at_save": card.get("estimate_at_save"),
        "estimate_now": {"range": now["range"], "data_label": now["data_label"], "data_source": now["data_source"], "enough_data": now["enough_data"]},
    }


def cards(c: dict) -> list[dict]:
    order = list(FORMATS)
    rows = sorted(get_db().rate_cards.find({"creator_id": c["_id"]}), key=lambda r: order.index(r["format"]))
    return [_card_view(c, r) for r in rows]


def save_card(c: dict, fmt: str, amount: int, count: int, usage_rights_days: int, exclusivity_days: int, note: str | None) -> dict:
    """Saving the same format again replaces it, so a repeated request changes nothing."""
    db = get_db()
    est = estimate(c, fmt, count, usage_rights_days, exclusivity_days)
    at = now_iso()
    snapshot = {"range": est["range"], "data_label": est["data_label"], "data_source": est["data_source"], "at": at} if est["enough_data"] else None
    db.rate_cards.update_one(
        {"_id": f"{c['_id']}:{fmt}"},
        {
            "$set": {
                "creator_id": c["_id"],
                "format": fmt,
                "amount": amount,
                "count": count,
                "usage_rights_days": usage_rights_days,
                "exclusivity_days": exclusivity_days,
                "note": note,
                "source": "manual",  # the creator's own number
                "estimate_at_save": snapshot,
                "updated_at": at,
            },
            "$setOnInsert": {"created_at": at},
        },
        upsert=True,
    )
    if fmt == "reel" and not usage_rights_days and not exclusivity_days:
        # The typical per-reel rate that the rate-gap line compares with the fair rate.
        prov = dict(c.get("provenance") or {})
        prov["current_rate"] = "manual"
        db.creators.update_one({"_id": c["_id"]}, {"$set": {"current_rate": round(amount / count), "provenance": prov}})
    return _card_view(c, db.rate_cards.find_one({"_id": f"{c['_id']}:{fmt}"}))


def delete_card(c: dict, fmt: str) -> bool:
    return get_db().rate_cards.delete_one({"_id": f"{c['_id']}:{fmt}"}).deleted_count > 0


UNITS_HI = {"reel": "रील", "story": "स्टोरी", "carousel": "कैरोसेल", "live": "लाइव सेशन", "short": "Short", "youtube_video": "YouTube वीडियो"}


def _terms_hi(card: dict) -> list[str]:
    out = []
    if card["usage_rights_days"]:
        out.append(f"{card['usage_rights_days']} दिन के पेड यूसेज राइट्स")
    if card["exclusivity_days"]:
        out.append(f"{card['exclusivity_days']} दिन की कैटेगरी एक्सक्लूसिविटी")
    return out


def kit_rates(c: dict, lang: str = "en") -> list[dict]:
    """Saved rates as media-kit rows, in format order."""
    out = []
    for card in cards(c):
        if lang == "hi":
            label, terms = f"{card['count']} {UNITS_HI[card['format']]}", _terms_hi(card)
        else:
            label, terms = card["deliverables"], card["terms"]
        out.append({"label": label + (f" · {', '.join(terms)}" if terms else ""), "value": inr_full(card["amount"]), "amount": card["amount"], "kind": "your_rate"})
    return out


def formats_view(c: dict) -> list[dict]:
    """Every format, and whether it can be estimated now."""
    out = []
    for key, spec in FORMATS.items():
        available, reason = True, None
        if spec["family"] == "youtube_long" and not (c.get("channels") or {}).get("youtube"):
            available, reason = False, "Link your YouTube channel to estimate this."
        out.append({"key": key, "label": spec["label"], "estimate_available": available, "reason": reason})
    return out
