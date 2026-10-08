"""Shared shapes for engine output. Every number the UI shows travels with a
`why` (reasons, inputs and their provenance) and every forecast is an
`estimate` (a range with assumptions and a confidence level)."""
from __future__ import annotations

import math
from datetime import date
from statistics import median
from typing import Iterable, Literal

Confidence = Literal["low", "medium", "high"]


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def round_to(v: float, step: float) -> float:
    return round(v / step) * step


def nice_round(v: float) -> int:
    """Round a rupee amount to a step that reads naturally at its size."""
    if v >= 100_000:
        return int(round_to(v, 5_000))
    if v >= 10_000:
        return int(round_to(v, 500))
    if v >= 1_000:
        return int(round_to(v, 100))
    return int(round_to(v, 50))


def short(v: float, digits: int = 1) -> str:
    """Indian short form: 950, 7K, 17.4K, 1.2L, 2.4Cr."""
    a = abs(v)
    sign = "-" if v < 0 else ""

    def f(n: float) -> str:
        s = f"{n:.{digits}f}"
        return s.rstrip("0").rstrip(".") if "." in s else s

    if a >= 1e7:
        return f"{sign}{f(a / 1e7)}Cr"
    if a >= 1e5:
        return f"{sign}{f(a / 1e5)}L"
    if a >= 1e3:
        return f"{sign}{f(a / 1e3)}K"
    return f"{sign}{int(round(a))}"


def day_month(d: date | str) -> str:
    """'3 Oct'. Built by hand because strftime's '%-d' (no leading zero) is not supported on Windows."""
    d = date.fromisoformat(d) if isinstance(d, str) else d
    return f"{d.day} {d.strftime('%b')}"


def inr(v: float) -> str:
    return f"₹{short(v)}"


def inr_full(v: float) -> str:
    n = int(round(v))
    s = str(abs(n))
    if len(s) > 3:
        head, tail = s[:-3], s[-3:]
        parts = []
        while len(head) > 2:
            parts.insert(0, head[-2:])
            head = head[:-2]
        if head:
            parts.insert(0, head)
        s = ",".join(parts + [tail])
    return f"{'-' if n < 0 else ''}₹{s}"


def inr_range(lo: float, hi: float) -> str:
    """Below 10K both ends in full (₹600–1,600); above, compact (₹5.2K–12K)."""
    if hi < 10_000:
        a, b = inr_full(lo)[1:], inr_full(hi)[1:]
    else:
        a, b = short(lo, 1), short(hi, 1)
    return f"₹{a}" if a == b else f"₹{a}–{b}"


def count_range(lo: float, hi: float) -> str:
    a, b = short(lo, 1), short(hi, 1)
    return a if a == b else f"{a}–{b}"


def estimate(
    low: float,
    high: float,
    unit: str = "inr",
    period: str | None = None,
    assumptions: Iterable[str] = (),
    confidence: Confidence = "medium",
) -> dict:
    lo, hi = sorted((low, high))
    if unit == "inr":
        lo, hi = nice_round(lo), nice_round(hi)
    else:
        lo, hi = int(round(lo)), int(round(hi))
    return {
        "low": lo,
        "high": hi,
        "unit": unit,
        "period": period,
        "assumptions": list(assumptions),
        "confidence": confidence,
    }


def why(
    reasons: Iterable[str],
    inputs: Iterable[dict] | None = None,
    simulated_fields: Iterable[str] | None = None,
    title: str | None = None,
    source: str | None = None,
) -> dict:
    return {
        "title": title,
        "reasons": [r for r in reasons if r],
        "inputs": list(inputs or []),
        "simulated_fields": sorted(set(simulated_fields or [])),
        "source": source,
    }


def inp(label: str, value: str, provenance: str | None = None) -> dict:
    return {"label": label, "value": value, "provenance": provenance}


def safe_median(values: Iterable[float], default: float = 0.0) -> float:
    v = [x for x in values if x is not None]
    return float(median(v)) if v else default


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * q
    f, c = math.floor(k), math.ceil(k)
    if f == c:
        return float(v[int(k)])
    return float(v[f] + (v[c] - v[f]) * (k - f))
