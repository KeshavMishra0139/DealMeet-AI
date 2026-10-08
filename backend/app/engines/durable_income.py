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
    warning = None
    if top_share > CONCENTRATION_LIMIT:
        warning = f"{round(top_share * 100)}% of your income comes from {INCOME_TYPES.get(top, top).lower()}."
    late = [h for h in hist if not h.get("paid_on_time")]
    reasons = [
        f"Diversification {diversification * 100:.0f}/100: {len(shares)} income source{'s' if len(shares) != 1 else ''}, "
        f"the largest is {round(top_share * 100)}% ({INCOME_TYPES.get(top, top).lower()}).",
        f"Recurring income is {recurring * 100:.0f}% of the total.",
        f"{reliability * 100:.0f}% of payments arrived on time"
        + (f"; {len(late)} came {max(h['days_late'] for h in late)} days late at worst." if late else "."),
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
