"""AI price review: the language model looks at what the price formula can't see (what the
videos are about from their titles, the language market, likes and comments per 1,000
views, how steady the views are, whether a channel is one creator or a TV network posting
clips) and suggests a market adjustment to the formula's price, with its reasons.

It never sets a price on its own:
- the adjustment is capped at -30% to +40% of the formula's price;
- every number in its reasons must already be in the facts it was given;
- with no AI configured, or any failure, the formula's price stands unchanged.

A creator's review is stored on their profile (`ai_price`) and applied everywhere the
price is shown while their numbers stay the same (`basis`); it is refreshed in the
background when they change. The public "Know your page" lookup reviews a channel on
the spot.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import Counter
from typing import Literal

from pydantic import BaseModel, Field

from ..config import get_settings, now_iso
from ..db import get_db
from ..seed.catalog import LANGS, NICHES
from .llm import generate, numbers_grounded
from .regional import tag_rules

log = logging.getLogger("jodidar.ai")

LOW, HIGH = -30, 40  # percent, the most the review may move the formula's price
MAX_TITLES = 12
RETRY_SECONDS = 30 * 60  # after a failed review, wait before trying the same numbers again


class PriceReview(BaseModel):
    adjust_pct: int = Field(description=f"Market adjustment to the formula's price in percent, a whole number from {LOW} to {HIGH}. 0 when the facts don't justify a change.")
    niche: str = Field(description="The niche id from the list given that fits the content best")
    language: str = Field(description="Main language of the titles: one of " + ", ".join(LANGS))
    confidence: Literal["low", "medium", "high"]
    reasons: list[str] = Field(description="2 or 3 short reasons, at most 25 words each. Quote only numbers that appear in the facts.")


def _none() -> PriceReview:
    return PriceReview(adjust_pct=0, niche="", language="", confidence="low", reasons=[])


INSTRUCTIONS = (
    "Judge what the formula can't see in the facts: what the content is about (from the titles), how brand-friendly "
    "and attention-holding it is, the language market, likes and comments per 1,000 views, how steady the views are, "
    "and whether this is one creator or a TV network or media company posting clips (brands buy those differently). "
    f"Return adjust_pct from {LOW} to {HIGH} (0 when unsure), the niche id that fits best, the main language of the "
    "titles, your confidence, and 2 or 3 short reasons. Quote a number only by copying it exactly as the facts write it "
    "(no lakh or K rounding), and only numbers that appear in the facts. No promises."
)


def niche_menu() -> str:
    return "; ".join(f"{k} ({v['label']}, Rs {v['cpm']} per 1,000 views)" for k, v in NICHES.items())


def detect_language(texts: list[str]) -> str | None:
    """The main language of titles or captions, by script and word rules (no AI needed)."""
    langs = [tag_rules(t).language for t in texts if t and t.strip()]
    if not langs:
        return None
    counts = Counter(langs)
    # English titles are common on Indian-language channels; any Indian language that is
    # well represented wins over English.
    indian = [(n, lang) for lang, n in counts.items() if lang != "en"]
    if indian:
        n, lang = max(indian)
        if n >= max(2, len(langs) // 4):
            return lang
    return counts.most_common(1)[0][0]


def _per_1k(videos: list[dict], field: str) -> float | None:
    known = [v for v in videos if v.get(field) is not None]
    views = sum(v.get("views") or 0 for v in known)
    return round(sum(v[field] for v in known) / views * 1000, 1) if known and views else None


def _clean(review: PriceReview, facts: str) -> dict | None:
    """The model's answer, kept only if it stays inside the rules."""
    pct = max(LOW, min(HIGH, int(review.adjust_pct)))
    reasons = [r.strip()[:220] for r in review.reasons if r and r.strip()][:3]
    if not reasons:
        return None
    if not numbers_grounded(" ".join(reasons), f"{facts}\nAdjustment {abs(pct)} percent"):
        log.info("AI price review cited numbers that aren't in the facts; not used")
        return None
    return {
        "adjust_pct": pct,
        "niche": review.niche if review.niche in NICHES else None,
        "language": review.language if review.language in LANGS else None,
        "confidence": review.confidence,
        "reasons": reasons,
    }


def _ask(task: str, facts: str) -> dict | None:
    prompt = f"{facts}\n\n{INSTRUCTIONS}"
    result, source = generate(task, prompt, PriceReview, _none, max_tokens=600)
    if source == "template":
        return None
    return _clean(result, facts)


# ------------------------------------------------------------------ a public channel lookup
def review_channel(report: dict, chosen_by: str) -> dict | None:
    """Reviews a channel_report's prices. None when AI isn't configured or the answer was unusable."""
    if not get_settings().has_ai:
        return None
    ch, videos, prices = report["channel"], report["videos"], report["prices"]
    lines = [
        f"Channel: {ch.get('title')} ({ch.get('handle') or 'no handle'}), country {ch.get('country') or 'not given'}. "
        f"YouTube topics: {', '.join(ch.get('topics') or []) or 'none'}.",
        f"Subscribers: {ch['subscribers'] if ch.get('subscribers') is not None else 'hidden'}. Total views: {ch.get('total_views')}. "
        f"Videos on the channel: {ch.get('video_count')}.",
    ]
    for fmt, label in (("shorts", "Shorts"), ("long", "Long videos")):
        p = prices[fmt]
        if p.get("enough_data"):
            lines.append(f"{label}: median {p['median_views']} views over the last {p['videos']} settled {label.lower()}; formula price Rs {p['per_video']} per video.")
        else:
            lines.append(f"{label}: not priced ({p.get('reason')}).")
    likes, comments = _per_1k(videos, "likes"), _per_1k(videos, "comments")
    lines.append(f"Likes per 1,000 views: {likes if likes is not None else 'hidden'}. Comments per 1,000 views: {comments if comments is not None else 'hidden'}.")
    lines.append(f"Niche the formula used: {report['niche']} ({report['niche_label']}), chosen by {chosen_by}.")
    lines.append(f"Niche ids to choose from: {niche_menu()}.")
    lines.append("Recent titles:\n" + "\n".join(f"- {v['title'][:140]}" for v in videos[:MAX_TITLES] if v.get("title")))
    facts = "Price estimate for one sponsored post on this YouTube channel, for an Indian brand. The formula prices on median views times the niche's rate per 1,000 views.\n" + "\n".join(lines)
    return _ask("price_review_channel", facts)


# ------------------------------------------------------------------ a creator's own price
def _sig2(x: float) -> int:
    if x <= 0:
        return 0
    from math import floor, log10

    return int(round(x, -max(0, int(floor(log10(x))) - 1)))


def basis(c: dict) -> str:
    """What a review was made for. A new niche, platform or a real change in views makes it stale."""
    from ..engines import metrics

    return f"{c.get('niche')}|{metrics.platform(c)}|{_sig2(metrics.median_views(c))}|{len(metrics.recent(c))}"


def current(c: dict) -> dict | None:
    """The stored review, if it was made for the creator's current numbers."""
    r = c.get("ai_price") or {}
    return r if r.get("reasons") and r.get("basis") == basis(c) else None


def enabled() -> bool:
    return get_settings().has_ai


def status(c: dict) -> str:
    """applied, pending (AI is on and a review is due) or off."""
    if current(c):
        return "applied"
    return "pending" if get_settings().has_ai else "off"


def _creator_facts(c: dict) -> str:
    from ..engines import metrics
    from ..engines.fair_price import fair_price

    formula = fair_price(c, None, None, with_model=False, with_ai=False)
    recent = metrics.recent(c)
    posts, audience = metrics.post_noun(c), metrics.audience_noun(c)
    likes, comments = _per_1k(recent, "likes"), _per_1k(recent, "comments")
    langs = ", ".join(LANGS[x]["label"] for x in c.get("languages") or [] if x in LANGS) or "not given"
    lines = [
        f"Creator on {metrics.platform(c).capitalize()}: {c.get('name')}, city {c.get('city') or c.get('region') or 'not given'}, languages {langs}.",
        f"{audience.capitalize()}: {c.get('followers', 0)}. Median views over the last {len(recent)} {posts}s: {round(metrics.median_views(c))}.",
        f"{posts.capitalize()}s per week over the last 4 weeks: {metrics.posts_per_week(c):.1f}. Views vary by {metrics.views_cv(c) * 100:.0f}% from {posts} to {posts}.",
        f"Likes per 1,000 views: {likes if likes is not None else 'not known'}. Comments per 1,000 views: {comments if comments is not None else 'not known'}.",
        f"Niche: {c['niche']} ({NICHES[c['niche']]['label']}), chosen by the creator.",
        f"Formula price for one {posts}: Rs {formula['per_reel']}, from {formula['base']} reach base and capped adjustments for engagement, fit, consistency, safety and trust.",
        f"Niche ids to choose from: {niche_menu()}.",
    ]
    captions = [x.get("caption") for x in recent if x.get("caption")]
    if captions:
        lines.append(f"Recent {posts} titles or captions:\n" + "\n".join(f"- {t[:140]}" for t in captions[:MAX_TITLES]))
    return "Price estimate for one sponsored post by this Indian creator. The formula prices on median views times the niche's rate per 1,000 views.\n" + "\n".join(lines)


def refresh(creator_id: str) -> dict | None:
    """Reviews a creator's price now and stores the result. None when AI isn't on or failed."""
    from ..services.creator_ctx import load_creator

    if not get_settings().has_ai:
        return None
    db = get_db()
    c = load_creator(creator_id)
    b = basis(c)
    db.creators.update_one({"_id": creator_id}, {"$set": {"ai_price_attempt": {"basis": b, "at": time.time()}}})
    review = _ask("price_review_creator", _creator_facts(c))
    if not review:
        return None
    review.update({"basis": b, "reviewed_at": now_iso()})
    db.creators.update_one({"_id": creator_id}, {"$set": {"ai_price": review}})
    return review


_running: set[str] = set()
_lock = threading.Lock()


def ensure(c: dict) -> None:
    """Starts a background review when one is due. Returns at once; the next page load shows it."""
    if not get_settings().has_ai or current(c):
        return
    attempt = c.get("ai_price_attempt") or {}
    if attempt.get("basis") == basis(c) and time.time() - attempt.get("at", 0) < RETRY_SECONDS:
        return
    cid = c["_id"]
    with _lock:
        if cid in _running:
            return
        _running.add(cid)

    def run() -> None:
        try:
            refresh(cid)
        except Exception:  # a review never breaks a page
            log.exception("AI price review for %s failed", cid)
        finally:
            with _lock:
                _running.discard(cid)

    threading.Thread(target=run, name=f"price-review-{cid}", daemon=True).start()
