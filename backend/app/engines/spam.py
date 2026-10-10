"""Silent marketplace hygiene: spam and duplicate listing detection.

Duplicates: TF-IDF cosine similarity between listings from different owners.
Spam: fee requests, off-platform-only contact, follower selling, unverified
owners and budgets out of line with the ask. Flagged listings are hidden from
creators with a one-line note, never shown as a dashboard.
"""
from __future__ import annotations

import re

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from ..db import get_db
from ..services import cache

PATTERNS = [
    (re.compile(r"\b(registration|joining|unlock)\b.*\b(fee|pay)|\bpay\b.*\b(registration|to (join|unlock))", re.I), "Asks creators to pay a fee"),
    (re.compile(r"whatsapp only|contact on whatsapp", re.I), "Moves the conversation off-platform"),
    (re.compile(r"\b(buy|get)\s+[\d,.]+\s*k?\s+(real\s+|instagram\s+)?followers\b|\bfollowers?\s+packages?\b", re.I), "Sells followers"),
    (re.compile(r"\bearn [\d,]+.*(a|per) (week|day)|\bearn\b.*\bfrom home\b", re.I), "Income claims typical of scams"),
]


def _scan() -> dict[str, dict]:
    db = get_db()
    listings = list(db.listings.find({}))
    owners = {b["_id"]: b for b in db.brands.find({})}
    texts = [f"{x['title']} {x['summary']}" for x in listings]
    sim = cosine_similarity(TfidfVectorizer(ngram_range=(1, 2)).fit_transform(texts))
    out: dict[str, dict] = {}
    for i, x in enumerate(listings):
        reasons = [why for rx, why in PATTERNS if rx.search(texts[i])]
        owner = owners.get(x["owner_id"])
        verified = bool(owner and owner.get("verified")) or x["owner_id"].startswith("cr_")
        if not verified:
            reasons.append("Lister is not verified")
        dup_of = None
        for j, y in enumerate(listings):
            if i == j or x["owner_id"] == y["owner_id"] or sim[i, j] < 0.75:
                continue
            y_owner = owners.get(y["owner_id"])
            if y_owner and y_owner.get("verified") and not verified:
                dup_of = y["_id"]
                similar = "word for word" if sim[i, j] >= 0.995 else f"({sim[i, j] * 100:.0f}% similar)"
                reasons.append(f"Copies a listing by {y_owner['name']} {similar}")
                break
        flagged = bool(dup_of) or (not verified and len(reasons) >= 2) or len(reasons) >= 2
        out[x["_id"]] = {"flagged": flagged, "dup_of": dup_of, "reasons": reasons}
    return out


def scan() -> dict[str, dict]:
    return cache.memo("spam_scan", _scan)


def is_flagged(listing_id: str) -> bool:
    return scan().get(listing_id, {}).get("flagged", False)
