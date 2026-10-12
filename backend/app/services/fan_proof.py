"""Fan Proof: a creator's unpaid mentions of a brand, from posts synced through the
official APIs (Instagram captions, YouTube titles and descriptions).

A mention is the brand's @handle or #brandname. Posts marked as paid (#ad, #sponsored,
#collab, "paid partnership") don't count. Typed-in or sample data never counts, and we
never say "following since": the APIs don't show who a creator follows. Recomputed
after each sync; a platform's Fan Proof is deleted when it's disconnected.
"""
from __future__ import annotations

import re
from datetime import datetime

from ..config import now_iso
from ..db import get_db

API_SOURCES = ("instagram_api", "youtube_api")
PAID = re.compile(r"(?:#(?:ad|ads|sponsored|collab)\b)|paid partnership", re.I)
MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
MAX_LINKS = 10


def tokens(brand: dict) -> list[str]:
    """The brand's @handles and #brandname, lowercased."""
    out = []
    for h in (brand.get("public_handles") or {}).values():
        if h:
            out.append("@" + h.lstrip("@").lower())
    compact = re.sub(r"[^a-z0-9]", "", brand.get("name", "").lower())
    if len(compact) >= 3:
        out.append("#" + compact)
    return list(dict.fromkeys(out))


def _pattern(brand: dict) -> re.Pattern | None:
    toks = tokens(brand)
    if not toks:
        return None
    # A handle or hashtag ends where handle characters end (so #thalam doesn't match #thalamfoods).
    return re.compile("|".join(re.escape(t) + r"(?![a-z0-9._])" for t in toks), re.I)


def _text(post: dict) -> str:
    if post["platform"] == "youtube":
        return f"{post.get('title') or ''}\n{post.get('description') or ''}"
    return post.get("caption") or ""


def mentions(posts: list[dict], brand: dict) -> list[dict]:
    """Synced API posts that mention the brand and aren't marked as paid."""
    rx = _pattern(brand)
    if not rx:
        return []
    out = []
    for p in posts:
        if p.get("source") not in API_SOURCES:
            continue
        text = _text(p)
        if rx.search(text) and not PAID.search(text):
            out.append(p)
    return out


def recompute(creator_id: str, platform: str) -> int:
    """Rebuild this platform's Fan Proof for every listed brand. Returns brands mentioned."""
    db = get_db()
    posts = list(db.posts.find({"creator_id": creator_id, "platform": platform, "source": {"$in": list(API_SOURCES)}}))
    db.fan_proof.delete_many({"creator_id": creator_id, "platform": platform})
    n = 0
    for b in db.brands.find({"removed": {"$ne": True}, "guest": {"$ne": True}, "_id": {"$not": {"$regex": "^xx_"}}}):
        found = mentions(posts, b)
        if not found:
            continue
        found.sort(key=lambda p: p.get("published_at") or "")
        db.fan_proof.insert_one(
            {
                "_id": f"fp_{creator_id}_{b['_id']}_{platform}",
                "creator_id": creator_id,
                "brand_id": b["_id"],
                "platform": platform,
                "count": len(found),
                "first_at": found[0].get("published_at"),
                "links": [p["permalink"] for p in found if p.get("permalink")][:MAX_LINKS],
                "source": f"{platform}_api",
                "computed_at": now_iso(),
            }
        )
        n += 1
    return n


def _month_year(iso: str | None) -> str | None:
    try:
        d = datetime.fromisoformat((iso or "").replace("Z", "+00:00"))
    except ValueError:
        return None
    return f"{MONTHS[d.month - 1]} {d.year}"


def summary(creator_id: str, brand_id: str) -> dict | None:
    """'Fan since <month year> · N unpaid mentions', across connected platforms, or None."""
    docs = list(get_db().fan_proof.find({"creator_id": creator_id, "brand_id": brand_id}))
    if not docs:
        return None
    first = min((d["first_at"] for d in docs if d.get("first_at")), default=None)
    count = sum(d["count"] for d in docs)
    since = _month_year(first)
    return {
        "count": count,
        "first_at": first,
        "since": since,
        "platforms": sorted(d["platform"] for d in docs),
        "links": [link for d in docs for link in d.get("links", [])][:MAX_LINKS],
        "label": f"Fan since {since} · {count} unpaid mention{'s' if count != 1 else ''}" if since else f"{count} unpaid mention{'s' if count != 1 else ''}",
        "source": docs[0]["source"] if len(docs) == 1 else "api",
    }


def counts_for_brand(brand_id: str) -> dict[str, int]:
    """creator_id -> unpaid mentions of this brand."""
    out: dict[str, int] = {}
    for d in get_db().fan_proof.find({"brand_id": brand_id}):
        out[d["creator_id"]] = out.get(d["creator_id"], 0) + d["count"]
    return out
