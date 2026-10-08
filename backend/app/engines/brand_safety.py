"""Silent brand-safety notes: small flags with a fix suggestion."""
from __future__ import annotations

from . import metrics

FLAGS = {
    "copyrighted_clips": {
        "label": "Uses copyrighted clips",
        "fix": "Add an original voiceover or commentary to each edit.",
        "penalty": 0.06,
    },
    "strong_language": {
        "label": "Strong language in some posts",
        "fix": "Keep brand-paired posts free of strong language.",
        "penalty": 0.08,
    },
    "health_claims": {
        "label": "Unverified health claims",
        "fix": "Share personal experience, not medical results.",
        "penalty": 0.08,
    },
}


def assess(c: dict) -> dict:
    flags = []
    recent = metrics.recent(c)
    if recent and sum(1 for r in recent if r.get("copyrighted_clips") and not r.get("original_voiceover")) >= len(recent) / 2:
        flags.append("copyrighted_clips")
    for f in c.get("content_flags") or []:
        if f in FLAGS and f not in flags:
            flags.append(f)
    penalty = min(0.15, sum(FLAGS[f]["penalty"] for f in flags))
    return {
        "safe": not flags,
        "score": int(round(100 - penalty * 400)),
        "penalty": penalty,
        "flags": [{"id": f, **FLAGS[f]} for f in flags],
    }


def public(c: dict) -> dict:
    """What a brand sees: the flags and the fix already suggested to the creator, never the penalty maths."""
    return {"flags": [{"id": f["id"], "label": f["label"], "fix": f["fix"]} for f in assess(c)["flags"]]}
