"""Contract versions and the deal status machine.

Every set of terms is an immutable version: number, terms, SHA-256 hash of the terms,
author (side and account) and time. Proposing a change adds a version; it never edits
one. Each acceptance records who, when and which version. A contract is agreed only
when both sides have accepted the same, latest version.

The deal's status follows one table of allowed transitions, checked on every action
and written to the audit log.
"""
from __future__ import annotations

import hashlib
import json
from datetime import date

from fastapi import HTTPException

from ..config import now_iso

TERM_KEYS = ("amount", "deliverables", "post_by", "usage_rights_days", "exclusivity_days")

STATUS_LABELS = {
    "offer": "Offer",
    "negotiating": "Negotiating",
    "contract_agreed": "Contract agreed",
    "in_progress": "In progress",
    "submitted": "Submitted",
    "revision_requested": "Revision requested",
    "approved": "Approved",
    "payment_pending": "Payment pending",
    "paid": "Paid",
    "cancelled": "Cancelled",
}
ALLOWED = {
    # offer -> in progress: a collective member accepts a pack the brand already funded.
    "offer": {"negotiating", "contract_agreed", "in_progress", "cancelled"},
    "negotiating": {"contract_agreed", "cancelled"},
    "contract_agreed": {"in_progress", "cancelled"},
    "in_progress": {"submitted"},
    "submitted": {"revision_requested", "approved", "payment_pending", "paid"},
    "revision_requested": {"submitted"},
    "approved": {"payment_pending", "paid"},
    "payment_pending": {"paid"},
    "paid": set(),
    "cancelled": set(),
}


def terms_of(d: dict) -> dict:
    return {
        "amount": int(d["amount"]),
        "deliverables": [{"kind": x["kind"], "count": int(x["count"])} for x in d.get("deliverables") or [{"kind": "reel", "count": 1}]],
        "post_by": d.get("post_by"),
        "usage_rights_days": int(d.get("usage_rights_days") or 0),
        "exclusivity_days": int(d.get("exclusivity_days") or 0),
    }


def digest(terms: dict) -> str:
    return hashlib.sha256(json.dumps({k: terms.get(k) for k in TERM_KEYS}, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def latest(d: dict) -> dict:
    return d["versions"][-1]


def _version(d: dict, terms: dict, side: str, user_id: str | None, note: str | None, at: str) -> dict:
    v = {"number": len(d.get("versions") or []) + 1, "terms": terms, "hash": digest(terms), "author": {"side": side, "user_id": user_id}, "note": note, "at": at}
    d.setdefault("versions", []).append(v)
    return v


def _accept(d: dict, number: int, side: str, user_id: str | None, at: str) -> None:
    if not any(a["version"] == number and a["side"] == side for a in d.setdefault("acceptances", [])):
        d["acceptances"].append({"version": number, "side": side, "user_id": user_id, "at": at})


def ensure(d: dict) -> None:
    """Older deals (and the seed) predate versions: their terms become version 1, sent by
    the brand, with the acceptances their signatures already show."""
    if d.get("versions"):
        return
    created = d.get("created_at") or now_iso()
    v = _version(d, terms_of(d), "brand", None, None, created)
    _accept(d, v["number"], "brand", None, created)
    c = d.get("contract") or {}
    if c.get("signed_by_creator") and d.get("stage") != "offer":
        _accept(d, v["number"], "creator", None, c["signed_by_creator"])
        d["agreed_version"] = v["number"]


def start(d: dict, brand_user_id: str | None) -> None:
    """A new offer: the brand's terms are version 1, accepted by the brand that sent them."""
    d.pop("versions", None)
    d.pop("acceptances", None)
    at = d.get("created_at") or now_iso()
    v = _version(d, terms_of(d), "brand", brand_user_id, d.get("message"), at)
    _accept(d, v["number"], "brand", brand_user_id, at)


def validate_terms(t: dict) -> dict:
    """A proposal's terms: the deal's current terms with the proposed changes."""
    out = dict(t)
    if not 500 <= out["amount"] <= 10_000_000:
        raise HTTPException(422, "The fee must be between ₹500 and ₹1,00,00,000.")
    kinds = {"reel", "story", "short", "carousel", "live", "link_in_bio"}
    ds = [x for x in out["deliverables"] if x.get("count")]
    if not ds or any(x["kind"] not in kinds or not 1 <= int(x["count"]) <= 20 for x in ds):
        raise HTTPException(422, "List at least one deliverable (reels, stories, Shorts...), 1 to 20 of each.")
    out["deliverables"] = [{"kind": x["kind"], "count": int(x["count"])} for x in ds]
    for k in ("usage_rights_days", "exclusivity_days"):
        if not 0 <= int(out[k]) <= 365:
            raise HTTPException(422, "Usage rights and exclusivity are 0 to 365 days.")
        out[k] = int(out[k])
    if out.get("post_by"):
        try:
            date.fromisoformat(out["post_by"])
        except ValueError as e:
            raise HTTPException(422, "The posting deadline must be a date like 2026-11-30.") from e
    return out


def propose(d: dict, side: str, user_id: str | None, changes: dict, note: str | None) -> dict:
    """A new version with the proposed changes, accepted by its author."""
    base = latest(d)["terms"]
    terms = validate_terms({**base, **{k: v for k, v in changes.items() if k in TERM_KEYS and v is not None}})
    if digest(terms) == latest(d)["hash"]:
        raise HTTPException(409, "Those are the terms already on the table.")
    at = now_iso()
    v = _version(d, terms, side, user_id, note, at)
    _accept(d, v["number"], side, user_id, at)
    return v


def accept_latest(d: dict, side: str, user_id: str | None) -> bool:
    """Accept the latest version. Returns True when both sides now accept it (agreed)."""
    v = latest(d)
    at = now_iso()
    _accept(d, v["number"], side, user_id, at)
    sides = {a["side"] for a in d["acceptances"] if a["version"] == v["number"]}
    if {"brand", "creator"} <= sides:
        d["agreed_version"] = v["number"]
        for k in TERM_KEYS:  # the deal runs on the agreed terms
            if k == "post_by":
                d["post_by"] = v["terms"].get("post_by")
            else:
                d[k] = v["terms"][k]
        return True
    return False


def awaiting(d: dict) -> str | None:
    """Which side has to answer the latest version, while negotiating."""
    v = latest(d)
    sides = {a["side"] for a in d.get("acceptances") or [] if a["version"] == v["number"]}
    missing = {"brand", "creator"} - sides
    return missing.pop() if len(missing) == 1 else None


def status_of(d: dict) -> str:
    stage = d.get("stage")
    if stage == "declined":
        return "cancelled"
    if stage == "offer":
        return "negotiating" if len(d.get("versions") or []) > 1 else "offer"
    if stage == "contract":
        return "contract_agreed"
    if stage == "escrow_funded":
        return "revision_requested" if d.get("revisions") else "in_progress"
    if stage == "live":
        return "submitted"
    if stage == "verified":
        return "payment_pending" if (d.get("payout") or {}).get("status") == "not_connected" else "approved"
    if stage == "paid":
        return "paid"
    return "offer"


def check_transition(before: str, after: str) -> None:
    if before != after and after not in ALLOWED[before]:
        raise HTTPException(409, f"A deal can't go from {STATUS_LABELS[before].lower()} to {STATUS_LABELS[after].lower()}.")


def versions_view(d: dict) -> list[dict]:
    acc = d.get("acceptances") or []
    return [
        {
            "number": v["number"],
            "terms": v["terms"],
            "hash": v["hash"],
            "author": v["author"]["side"],
            "note": v.get("note"),
            "at": v["at"],
            "accepted_by": [{"side": a["side"], "at": a["at"]} for a in acc if a["version"] == v["number"]],
        }
        for v in d.get("versions") or []
    ]
