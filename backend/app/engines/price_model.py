"""Cross-check for Fair-Price AI: a GradientBoostingRegressor trained on
synthetic deals that include market noise. Because the training data is
synthetic, agreement shows the rule-based price is internally consistent, not
that the market will pay it. The UI says so."""
from __future__ import annotations

import math

import numpy as np
from sklearn.ensemble import GradientBoostingRegressor

from ..seed.catalog import NICHES
from ..services import cache

N_DEALS = 4_000


def _formula(mv, cpm, ss_ratio, fit, consistency, trust, safety, units, uplift):
    from .fair_price import adjustments

    adj = adjustments({"ss_ratio": ss_ratio, "fit": fit, "consistency": consistency, "trust": trust, "safety_penalty": safety})
    p = mv / 1000 * cpm
    for a in adj.values():
        p *= 1 + a
    return p * units * (1 + uplift)


def _features(mv, cpm, ss_ratio, fit, consistency, trust, safety, units, uplift):
    return [math.log(max(mv, 1)), cpm, ss_ratio, fit, consistency, trust, safety, units, uplift]


def _train():
    rng = np.random.default_rng(11)
    cpms = [n["cpm"] for n in NICHES.values()]
    X, y = [], []
    for _ in range(N_DEALS):
        mv = float(np.clip(rng.lognormal(math.log(20_000), 1.4), 200, 2_000_000))
        row = (
            mv,
            float(rng.choice(cpms)),
            float(rng.lognormal(0, 0.35)),
            float(rng.beta(5, 2) if rng.random() < 0.5 else rng.uniform(0.05, 1.0)),
            float(rng.uniform(0.15, 0.95)),
            float(rng.uniform(25, 98)),
            float(rng.choice([0, 0, 0, 0.06, 0.08, 0.14])),
            float(rng.choice([1, 1, 1, 1.25, 1.5, 2])),
            float(rng.choice([0, 0, 0.1, 0.2, 0.3])),
        )
        price = _formula(*row) * float(rng.lognormal(0, 0.12))  # market variation
        X.append(_features(*row))
        y.append(math.log(price))
    model = GradientBoostingRegressor(n_estimators=300, max_depth=4, learning_rate=0.06, random_state=3)
    model.fit(np.array(X), np.array(y))
    return model


def model():
    return cache.memo("price_model", _train)


def cross_check(f: dict, adj: dict, units: float, uplift: float, rule_total: float) -> dict:
    fit = f["fit"] if f["fit"] is not None else 0.85
    x = _features(f["median_views"], f["cpm"], f["ss_ratio"], fit, f["consistency"], f["trust"],
                  f["safety_penalty"], units, uplift)
    predicted = math.exp(float(model().predict(np.array([x]))[0]))
    diff = abs(predicted - rule_total) / rule_total if rule_total else 0
    return {
        "predicted": round(predicted),
        "agrees_within_pct": max(1, int(math.ceil(diff * 100))),
        "trained_on": N_DEALS,
        "note": "Gradient-boosted model trained on synthetic deals with market noise. It checks consistency, not market truth.",
    }
