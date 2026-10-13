"""Silent Trust Score: fake-follower and engagement-pod detection.

Runs an IsolationForest over insights each creator connected through the
official API (never over accounts that have not consented). Surfaces only as a
small shield badge with the top two reasons, and as a filter in collectives.
"""
from __future__ import annotations

import math

import numpy as np
from sklearn.ensemble import IsolationForest

from ..db import get_db
from ..services import cache
from . import metrics
from .common import clamp

FEATURES = [
    "growth_spike",      # biggest weekly follower jump vs a typical week
    "view_follower",     # median views / followers (bought followers do not watch)
    "like_follower",     # average likes / followers
    "comment_like",      # comments per like (pods comment a lot)
    "generic_comments",  # share of generic comments ("nice", emoji-only)
    "follow_ratio",      # followers / following
]


def features(c: dict) -> list[float] | None:
    if not c.get("insights_connected", {}).get("instagram") or not c.get("reels"):
        return None
    if metrics.recent(c)[0].get("source") == "youtube_api":
        return None  # measured on Instagram's insights only
    hist = c.get("follower_history") or [c["followers"]]
    growth = [(b - a) / a for a, b in zip(hist, hist[1:]) if a > 0]
    typical = float(np.median(growth)) if growth else 0.0
    spike = max(growth) / max(typical, 0.002) if growth else 1.0
    f = max(c.get("followers", 1), 1)
    r = metrics.recent(c)
    likes = sum(x.get("likes") or 0 for x in r) / len(r)
    comments = sum(x.get("comments") or 0 for x in r) / len(r)
    following = c.get("following")  # None on a live site until a platform reports it
    # Each feature is one-sided: the healthy extreme is clipped, so a creator
    # whose reels out-reach their follower count is never "anomalous" for it.
    return [
        math.log1p(max(spike, 1.0)),
        math.log1p(min(metrics.median_views(c) / f, 1.2)),
        math.log1p(min(likes / f * 100, 6.0)),
        max(comments / max(likes, 1), 0.01),
        max((c.get("comment_insights") or {}).get("generic_share", 0.15), 0.10),
        # Small accounts naturally follow relatively more people; only judge
        # the follow ratio once an account has a real audience.
        math.log1p(min(f / max(following, 1), 3.0) if f >= 1_000 and following else 3.0),
    ]


def _model():
    # Trained on the seeded population, not the live collection: deterministic, unaffected by a
    # reset in progress, and new sign-ups can't shift what "normal" looks like.
    from ..seed.load import all_creators

    rows, ids = [], []
    for c in all_creators():
        fv = features(c)
        if fv:
            rows.append(fv)
            ids.append(c["_id"])
    X = np.array(rows)
    model = IsolationForest(n_estimators=300, contamination=0.1, random_state=7).fit(X)
    med = np.median(X, axis=0)
    iqr = np.subtract(*np.percentile(X, [75, 25], axis=0))
    iqr[iqr == 0] = 1.0
    return {"model": model, "median": med, "iqr": iqr}


def model():
    return cache.memo("trust_model", _model)


# direction: +1 means higher is worse, -1 means lower is worse
_RISK = {
    "growth_spike": (1, "Sudden follower jump that organic growth doesn't explain", "Steady, organic follower growth"),
    "view_follower": (-1, "Views are low for the follower count", "Views keep pace with followers"),
    "like_follower": (-1, "Likes are low for the follower count", "Healthy likes for the audience size"),
    "comment_like": (1, "Unusually many comments per like (possible engagement pod)", "Comment volume looks natural"),
    "generic_comments": (1, "Many generic comments", "Comments look specific and organic"),
    "follow_ratio": (-1, "Follows many accounts relative to followers (possible follow-for-follow)", "Balanced follower/following ratio"),
}


def trust_score(c: dict) -> dict | None:
    fv = features(c)
    if fv is None:
        return None
    m = model()
    x = np.array([fv])
    d = float(m["model"].decision_function(x)[0])
    z = (x[0] - m["median"]) / m["iqr"]
    risks = []
    for i, name in enumerate(FEATURES):
        direction, bad, good = _RISK[name]
        risks.append((direction * z[i], name, bad, good))
    risks.sort(reverse=True)
    hard_flags = sum(1 for r in risks if r[0] > 2.5)
    score = clamp(72 + 160 * d - 9 * hard_flags, 5, 98)
    if score < 60:
        reasons = [r[2] for r in risks[:2]]
    else:
        reasons = [r[3] for r in sorted(risks)[:2]]
    level = "high" if score >= 75 else "medium" if score >= 60 else "low"
    return {
        "score": int(round(score)),
        "level": level,
        "reasons": reasons,
        "method": "Isolation Forest over insights this creator connected via the official API",
        # Inputs that are sample data (Creator A's follower history, sandbox logins).
        "simulated": metrics.fields_simulated(c, "follower_history", "comment_insights", "reels.likes", "reels.comments"),
    }


def trust_for_id(creator_id: str) -> dict | None:
    def compute():
        c = get_db().creators.find_one({"_id": creator_id})
        return trust_score(c) if c else None

    return cache.memo(f"trust:{creator_id}", compute)
