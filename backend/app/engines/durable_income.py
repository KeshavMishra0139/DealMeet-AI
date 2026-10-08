"""Durable-Income Score (0-100): how resilient a creator's income is.

  diversification = 1 - Herfindahl index of income sources (normalised)
  recurring share = share of income that repeats (affiliate, retainers, products)
  reliability     = share of payments that arrived on time
Warns when one source is above 70% and suggests the next stream.
"""
from __future__ import annotations

from ..seed.catalog import INCOME_TYPES
from . import metrics
from .common import inp, inr, why

WEIGHTS = {"diversification": 0.5, "recurring": 0.25, "reliability": 0.25}
CONCENTRATION_LIMIT = 0.70
SOURCE_HI = {
    "brand": "ब्रैंड डील्स", "services": "सर्विसेज़", "digital": "डिजिटल प्रोडक्ट्स", "affiliate": "एफ़िलिएट",
    "pr": "PR और इवेंट्स", "collective": "कलेक्टिव डील्स", "page": "पेज शाउटआउट्स",
}
MAX_SOURCES = 5


def compute(c: dict, next_stream: dict | None = None) -> dict:
    by_source = metrics.income_by_source(c)
    total = sum(by_source.values())
    hist = [h for h in c.get("income_history") or [] if h["amount"] > 0]
    sim = metrics.fields_simulated(c, "income_history")
    if total <= 0:
        return {
            "score": None,
            "state": "no_income",
            "headline": "No income yet",
            "sources": [],
            "warning": None,
            "warning_hi": None,
            "next_stream": next_stream,
            "why": why(
                [
                    "There's no income on record yet, so there is nothing to score.",
                    "Your first stream sets the base. We suggest one below.",
                ],
                title="Durable-Income Score",
            ),
        }
    shares = {k: v / total for k, v in by_source.items()}
    hhi = sum(s * s for s in shares.values())
    diversification = (1 - hhi) / (1 - 1 / MAX_SOURCES)
    diversification = max(0.0, min(1.0, diversification))
    recurring = sum(h["amount"] for h in hist if h.get("recurring")) / total
    reliability = sum(1 for h in hist if h.get("paid_on_time")) / len(hist)
    score = 100 * (
        WEIGHTS["diversification"] * diversification + WEIGHTS["recurring"] * recurring + WEIGHTS["reliability"] * reliability
    )
    top, top_share = max(shares.items(), key=lambda kv: kv[1])
    warning = warning_hi = None
    if top_share > CONCENTRATION_LIMIT:
        pct = round(top_share * 100)
        source = INCOME_TYPES.get(top, top).lower()
        # "All of" rather than a 100 percent figure: the copy rules keep absolute claims out of the UI.
        warning = f"All of your income comes from {source}." if pct >= 100 else f"{pct}% of your income comes from {source}."
        warning_hi = f"आपकी सारी कमाई {SOURCE_HI.get(top, top)} से आती है।" if pct >= 100 else f"आपकी {pct}% कमाई {SOURCE_HI.get(top, top)} से आती है।"
    late = [h for h in hist if not h.get("paid_on_time")]
    # Whole shares are said in words ("all", "every") so the UI never shows a 100 percent figure.
    reasons = [
        f"Diversification {diversification * 100:.0f}/100: "
        + (
            f"one income source ({INCOME_TYPES.get(top, top).lower()})."
            if len(shares) == 1
            else f"{len(shares)} income sources, the largest is {round(top_share * 100)}% ({INCOME_TYPES.get(top, top).lower()})."
        ),
        "All of your income is recurring." if recurring >= 0.995 else f"Recurring income is {recurring * 100:.0f}% of the total.",
        (
            "Every payment arrived on time."
            if not late
            else f"{reliability * 100:.0f}% of payments arrived on time; {len(late)} came {max(h['days_late'] for h in late)} days late at worst."
        ),
    ]
    return {
        "score": int(round(score)),
        "state": "scored",
        "headline": "Concentrated" if warning else "Balanced" if score >= 60 else "Building",
        "sources": [
            {"source": k, "label": INCOME_TYPES.get(k, k), "amount": round(v), "share": round(shares[k], 3)}
            for k, v in sorted(by_source.items(), key=lambda kv: -kv[1])
        ],
        "parts": {
            "diversification": round(diversification, 3),
            "recurring": round(recurring, 3),
            "reliability": round(reliability, 3),
            "hhi": round(hhi, 3),
        },
        "monthly_avg": round(total / 6),
        "warning": warning,
        "warning_hi": warning_hi,
        "next_stream": next_stream,
        "why": why(
            reasons,
            [
                inp("Income, last 6 months", inr(total), metrics.prov(c, "income_history")),
                inp("Herfindahl index", f"{hhi:.2f}"),
            ],
            sim,
            title="Durable-Income Score",
            source="Score = 50% diversification (1 - Herfindahl) + 25% recurring share + 25% on-time payments.",
        ),
    }
