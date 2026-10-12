"""Trust-first deal rail.

Offer -> Contract (e-sign) -> Escrow funded -> Post submitted -> Approved -> Paid out

Brands fund escrow before the post goes live. The brand reviews the post link and
approves it or asks for a revision; if they don't respond within the grace period
it is approved automatically. Collective deals share one escrow payment.

Honesty rules:
- Funding happens only from a verified payment (Razorpay test mode) or, in demo
  mode, a payment recorded and labelled simulated.
- There is no payout integration. A real payment stops at "Approved, payout not
  connected"; a simulated one gets a simulated payout, labelled so, with no bank
  reference. Nothing is called paid unless that's what happened.
- Automatic post checks need the creator's connected account. Until then each
  check reads "not checked" and the brand's review is what approves the post.
"""
from __future__ import annotations

import re
import uuid
from datetime import date, timedelta

from fastapi import HTTPException

from ..config import now_iso, today
from ..db import get_db
from ..engines.common import day_month, inr, inr_full
from ..engines.fair_price import deliverables_label, fair_price
from . import contracts, payments

RAIL = [
    ("offer", "Offer"),
    ("contract", "Contract signed"),
    ("escrow_funded", "Escrow funded"),
    ("live", "Post submitted"),
    ("verified", "Approved"),
    ("paid", "Paid out"),
]
ORDER = {k: i for i, (k, _) in enumerate(RAIL)}
VERIFY_DAYS = 3  # brand has this long to confirm a live post
GRACE_DAYS = 3  # then the post is approved automatically
POST_URL = re.compile(r"^https://(www\.)?(instagram\.com/(reel|p)/|youtube\.com/shorts/|youtu\.be/)[\w\-]+/?(\?.*)?$")


def _get(deal_id: str) -> dict:
    d = get_db().deals.find_one({"_id": deal_id})
    if not d:
        raise HTTPException(404, "Deal not found")
    return d


def _save(d: dict) -> None:
    get_db().deals.replace_one({"_id": d["_id"]}, d)


def _event(d: dict, stage: str, note: str) -> None:
    d.setdefault("timeline", []).append({"stage": stage, "at": now_iso(), "note": note})


def _names(d: dict) -> tuple[dict, dict]:
    db = get_db()
    return db.creators.find_one({"_id": d["creator_id"]}) or {}, db.brands.find_one({"_id": d["brand_id"]}) or {}


def invoice_number(creator: dict, seq: int) -> str:
    return f"JD-{re.sub(r'[^A-Za-z0-9]', '', creator.get('handle', 'creator'))[:8].upper()}-{seq:04d}"


def _ensure_contract(d: dict) -> None:
    if not d.get("contract"):
        d["contract"] = {"signed_by_creator": None, "signed_by_brand": None, "created_at": now_iso()}


def _maybe_fund_from_collective(d: dict) -> None:
    if d.get("kind") != "collective":
        return
    col = get_db().collectives.find_one({"_id": d.get("collective_id")})
    c = d.get("contract") or {}
    if col and col.get("funded") and c.get("signed_by_creator") and c.get("signed_by_brand") and d["stage"] == "contract":
        d["stage"] = "escrow_funded"
        d["escrow"] = {"mode": col["escrow"]["mode"], "ref": col["escrow"]["ref"], "funded_at": col["escrow"]["funded_at"], "collective": True}
        _event(d, "escrow_funded", "Covered by the collective's escrow payment")


def _invoice_for(d: dict, status: str) -> dict:
    db = get_db()
    inv = db.invoices.find_one({"deal_id": d["_id"]})
    creator, brand = _names(d)
    if inv is None:
        seq = db.invoices.count_documents({"creator_id": d["creator_id"]}) + 1
        inv = {
            "_id": f"inv_{uuid.uuid4().hex[:8]}",
            "number": invoice_number(creator, seq),
            "creator_id": d["creator_id"],
            "deal_id": d["_id"],
            "to": brand.get("name", "Brand"),
            "amount": d["amount"],
            "description": deliverables_label(d),
            "issued": today().isoformat(),
            "due": (today() + timedelta(days=VERIFY_DAYS + GRACE_DAYS)).isoformat(),
            "status": status,
            "off_platform": False,
            "reminders": [],
        }
        db.invoices.insert_one(inv)
    else:
        db.invoices.update_one({"_id": inv["_id"]}, {"$set": {"status": status, "amount": d["amount"]}})
        inv["status"] = status
    return inv


def _payout(d: dict) -> None:
    """After approval. Only simulated escrow (demo mode) gets a payout, a simulated one with
    no bank reference. Anything paid for real waits until a payout partner is connected."""
    creator, _ = _names(d)
    if (d.get("escrow") or {}).get("mode") == "simulated":
        d.setdefault("payouts", []).append({"creator_id": d["creator_id"], "amount": d["amount"], "mode": "simulated", "at": now_iso()})
        d["payout"] = {"status": "simulated", "at": now_iso()}
        d["stage"] = "paid"
        _event(d, "paid", f"Simulated payout of {inr(d['amount'])} to {creator.get('name', 'the creator')}. No money moved.")
        _invoice_for(d, "paid_simulated")
        if d.get("kind") == "collective":
            get_db().collectives.update_one({"_id": d["collective_id"]}, {"$inc": {"paid_out": d["amount"]}})
        return
    d["payout"] = {"status": "not_connected", "at": now_iso()}
    _event(d, "verified", "Payout isn't connected yet, so nothing has been paid out. The payment stays in escrow.")


def _predict(d: dict) -> None:
    """Record the views we expect when the offer is accepted, for the case study later."""
    if d.get("predicted"):
        return
    from ..engines import metrics
    from .views import source_of

    c = get_db().creators.find_one({"_id": d["creator_id"]})
    if not c:
        return
    if metrics.has_reels(c):
        basis, source = "median of recent posts", source_of(c, "reels.0.views")
    elif (c.get("manual") or {}).get("avg_views"):
        basis, source = "self-reported average views", "manual"
    else:
        basis, source = "estimated from followers", source_of(c, "followers")
    d["predicted"] = {"views": round(metrics.median_views(c)), "basis": basis, "source": source, "at": now_iso()}


def _finished(d: dict) -> None:
    """A deal was approved: the creator's plan is recalculated with it."""
    from . import coach

    coach.on_new_data(d["creator_id"], "A deal was approved")


POST_CHECKS = ("The post is public and live", "Posted after the contract was signed", "The caption mentions the brand", "Paid-partnership label added")


def post_check(d: dict) -> dict:
    """Automatic checks of a submitted post. They need the creator's connected account;
    without it every check reads 'not checked' and the brand's review decides."""
    from . import post_checks  # the Instagram / YouTube connections plug in here

    result = post_checks.run(d)
    if result:
        return result
    return {
        "source": "not_connected",
        "checked_at": None,
        "note": "Automatic checks need the creator's connected Instagram or YouTube account. The brand reviews the link.",
        "checks": [{"label": label, "status": "not_checked"} for label in POST_CHECKS],
    }


def auto_release_due(d: dict) -> date | None:
    if d["stage"] != "live" or not d.get("verify_due"):
        return None
    return date.fromisoformat(d["verify_due"]) + timedelta(days=GRACE_DAYS)


def sweep(d: dict) -> dict:
    """Background rule, applied whenever a deal is read: approve a submitted post
    automatically if the brand hasn't reviewed it within the grace period."""
    due = auto_release_due(d)
    if due and today() >= due:
        d["verification"] = {**post_check(d), "auto": True, "approved_by": "auto", "approved_at": now_iso()}
        d["stage"] = "verified"
        _event(d, "verified", "Approved automatically: the brand didn't review the post in time")
        _payout(d)
        _save(d)
    return d


def _signatures(d: dict, creator: dict, brand: dict, payload: dict, role: str) -> None:
    """The agreed version's acceptances are the e-signatures."""
    _ensure_contract(d)
    acc = {a["side"]: a for a in d["acceptances"] if a["version"] == d["agreed_version"]}
    d["contract"].update({
        "signed_by_creator": acc["creator"]["at"],
        "signed_by_brand": acc["brand"]["at"],
        "creator_signature": (payload.get("name") if role == "creator" else None) or d["contract"].get("creator_signature") or creator.get("name"),
        "brand_signature": (payload.get("name") if role == "brand" else None) or d["contract"].get("brand_signature") or brand.get("name"),
        "version": d["agreed_version"],
        "hash": contracts.latest(d)["hash"],
    })


def _links(payload: dict) -> list[str]:
    raw = payload.get("links") or ([payload["url"]] if payload.get("url") else [])
    return [x.strip() for x in raw if x and x.strip()]


def act(deal_id: str, role: str, action: str, payload: dict, user: dict | None = None) -> dict:
    d = sweep(_get(deal_id))
    contracts.ensure(d)
    creator, brand = _names(d)
    stage = d["stage"]
    uid = (user or {}).get("_id")
    # A repeated request (double-click, retry) carries the same key: it changes nothing.
    key = payload.get("request_key")
    if key and key in (d.get("ops") or []):
        return view(d, role)
    before = contracts.status_of(d)

    def need(cond: bool, msg: str = "That isn't possible at this stage") -> None:
        if not cond:
            raise HTTPException(409, msg)

    def unchanged() -> dict:
        return view(d, role)

    if role == "creator" and action == "accept":
        if stage != "offer" and d.get("agreed_version"):
            return unchanged()  # already accepted
        need(stage == "offer" and contracts.awaiting(d) == "creator", "Wait for the brand to answer your proposal")
        contracts.accept_latest(d, "creator", uid)
        d["stage"] = "contract"
        _signatures(d, creator, brand, payload, role)
        _predict(d)
        _event(d, "contract", f"{creator.get('name')} accepted version {d['agreed_version']} and e-signed the contract")
        _invoice_for(d, "pending")
        _maybe_fund_from_collective(d)
    elif role == "creator" and action == "counter":
        need(stage == "offer" and d.get("kind") != "collective", "Collective splits are fixed; accept or decline")
        need(contracts.awaiting(d) == "creator", "Wait for the brand to answer your last proposal")
        amount = int(payload.get("amount") or 0)
        need(amount >= 500, "Enter a counter amount")
        v = contracts.propose(d, "creator", uid, {"amount": amount}, payload.get("note"))
        d["counter"] = {"amount": amount, "by": "creator", "at": v["at"], "note": payload.get("note"), "version": v["number"]}
        _event(d, "offer", f"{creator.get('name')} countered at {inr(amount)} (version {v['number']})")
    elif action == "propose":
        need(stage == "offer" and d.get("kind") != "collective", "Collective terms are fixed; accept or decline")
        need(contracts.awaiting(d) == role, "Wait for the other side to answer the last proposal")
        changes = {k: payload.get(k) for k in contracts.TERM_KEYS if payload.get(k) is not None}
        need(bool(changes), "Change at least one term")
        v = contracts.propose(d, role, uid, changes, payload.get("note"))
        if role == "creator":
            d["counter"] = {"amount": v["terms"]["amount"], "by": "creator", "at": v["at"], "note": payload.get("note"), "version": v["number"]}
        else:
            d.pop("counter", None)
        who = creator if role == "creator" else brand
        _event(d, "offer", f"{who.get('name')} proposed new terms (version {v['number']})")
    elif role == "creator" and action == "decline":
        if stage == "declined":
            return unchanged()
        need(stage == "offer")
        d["stage"] = "declined"
        _event(d, "declined", f"{creator.get('name')} declined")
    elif role == "brand" and action in ("accept_counter", "accept"):
        if stage != "offer" and d.get("agreed_version"):
            return unchanged()
        need(stage == "offer" and contracts.awaiting(d) == "brand", "There's no proposal from the creator to accept")
        contracts.accept_latest(d, "brand", uid)
        if d.get("counter"):
            d["counter"]["accepted_at"] = now_iso()
        d["stage"] = "contract"
        _signatures(d, creator, brand, payload, role)
        _predict(d)
        _event(d, "contract", f"{brand.get('name')} accepted version {d['agreed_version']} at {inr(d['amount'])}; contract signed by both")
        _invoice_for(d, "pending")
    elif role == "brand" and action == "decline_counter":
        if stage == "declined":
            return unchanged()
        need(stage == "offer" and contracts.awaiting(d) == "brand")
        if d.get("counter"):
            d["counter"]["declined_at"] = now_iso()
        d["stage"] = "declined"
        _event(d, "declined", f"{brand.get('name')} declined the proposal")
    elif action == "withdraw":
        if stage == "declined":
            return unchanged()
        # Before escrow is funded either side may cancel at no cost (contract term); the brand
        # may also withdraw an offer. A collective's funding is managed for the whole pack.
        cancel = stage == "contract" and not d.get("escrow") and (role == "creator" or d.get("kind") != "collective")
        need((stage == "offer" and role == "brand") or cancel)
        who = creator if role == "creator" else brand
        d["stage"] = "declined"
        _event(d, "declined", f"{who.get('name')} cancelled before escrow was funded" if stage == "contract" else f"{who.get('name')} withdrew the offer")
    elif action == "sign":
        need(stage == "contract")
        _ensure_contract(d)
        sig = "signed_by_creator" if role == "creator" else "signed_by_brand"
        if d["contract"].get(sig):
            return unchanged()  # signing twice changes nothing
        d["contract"][sig] = now_iso()
        d["contract"][f"{role}_signature"] = payload.get("name") or (creator if role == "creator" else brand).get("name")
        _event(d, "contract", f"{(creator if role == 'creator' else brand).get('name')} e-signed the contract")
        _maybe_fund_from_collective(d)
    elif role == "brand" and action == "fund":
        c = d.get("contract") or {}
        need(stage == "contract" and c.get("signed_by_creator") and c.get("signed_by_brand"), "Both sides sign before escrow is funded")
        need(d.get("kind") != "collective", "Fund the collective once from its page")
        # Only the payment routes call this, after a verified or (demo mode) simulated payment.
        need(payload.get("mode") in ("simulated", "razorpay-test") and bool(payload.get("payment_ref")), "Fund escrow through the payment step")
        ref = payload["payment_ref"]
        d["escrow"] = {"mode": payload["mode"], "ref": ref, "funded_at": now_iso(), "amount": d["amount"]}
        d["stage"] = "escrow_funded"
        _event(
            d,
            "escrow_funded",
            f"{inr(d['amount'])} paid into escrow (Razorpay test mode, payment {ref})"
            if payload["mode"] == "razorpay-test"
            else f"{inr(d['amount'])} in simulated escrow. No money moved (demo payment {ref}).",
        )
    elif role == "creator" and action == "submit_post":
        links = _links(payload)
        last = (d.get("submissions") or [None])[-1]
        if stage == "live" and last and last["links"] == links:
            return unchanged()  # the same submission again
        need(stage == "escrow_funded", "Wait until escrow is funded before posting")
        need(1 <= len(links) <= 5, "Add the link to your post (up to 5 links)")
        need(all(POST_URL.match(x) for x in links), "Paste the link to your Instagram reel or YouTube Short")
        note = (payload.get("note") or "").strip() or None
        d["proof_url"] = links[0]
        d["stage"] = "live"
        d["submitted_at"] = now_iso()
        d["verify_due"] = (today() + timedelta(days=VERIFY_DAYS)).isoformat()
        d["post_check"] = post_check(d)
        rnd = len(d.get("submissions") or []) + 1
        d.setdefault("submissions", []).append({"round": rnd, "links": links, "note": note, "at": d["submitted_at"], "check": d["post_check"]})
        _event(d, "live", "Post link submitted" + (f" (revision round {rnd - 1})" if rnd > 1 else ""))
    elif role == "brand" and action in ("approve", "confirm"):
        if stage in ("verified", "paid"):
            return unchanged()
        need(stage == "live")
        d["verification"] = {**(d.get("post_check") or post_check(d)), "approved_by": "brand", "approved_at": now_iso()}
        d["stage"] = "verified"
        _event(d, "verified", f"{brand.get('name')} approved the post")
        _payout(d)
        _save(d)
        _finished(d)
    elif role == "brand" and action == "request_revision":
        reason = (payload.get("note") or "").strip()
        revs = d.get("revisions") or []
        if stage == "escrow_funded" and revs and revs[-1]["reason"] == reason:
            return unchanged()  # the same request again
        need(stage == "live")
        need(len(reason) >= 3, "Say what needs to change")
        d.setdefault("revisions", []).append({"reason": reason, "at": now_iso(), "post": d.get("proof_url"), "round": len(revs) + 1})
        d["stage"] = "escrow_funded"
        d.pop("verify_due", None)
        _event(d, "escrow_funded", f"{brand.get('name')} asked for a revision (round {len(revs) + 1}): {reason}")
    elif role == "creator" and action == "nudge":
        need(stage == "live")
        _event(d, "live", f"{creator.get('name')} sent a reminder to confirm")
    else:
        raise HTTPException(400, "Unknown action")
    after = contracts.status_of(d)
    contracts.check_transition(before, after)
    if key:
        d["ops"] = [*(d.get("ops") or []), key][-50:]
    _save(d)
    if after != before:
        from . import auth as au

        au.audit("deal_status", uid, role, deal_id=d["_id"], deal_action=action, **{"from": before, "to": after}, version=d.get("agreed_version"))
    return view(d, role)


def actions_for(d: dict, role: str) -> list[dict]:
    s = d["stage"]
    c = d.get("contract") or {}
    out: list[dict] = []
    contracts.ensure(d)
    on_table = contracts.latest(d)["terms"]
    turn = s == "offer" and contracts.awaiting(d) == role
    if role == "creator":
        if turn:
            out = [{"id": "accept", "label": f"Accept {inr(on_table['amount'])} and sign", "kind": "primary"}]
            if d.get("kind") != "collective":  # a collective's split is fixed and already priced on reach
                out.append({"id": "counter", "label": "Counter", "kind": "secondary", "needs": "amount"})
                out.append({"id": "propose", "label": "Propose changes", "kind": "secondary", "needs": "terms"})
            out.append({"id": "decline", "label": "Decline", "kind": "ghost"})
        elif s == "contract" and not c.get("signed_by_creator"):
            out = [{"id": "sign", "label": "E-sign contract", "kind": "primary"}]
        if s == "contract" and not d.get("escrow"):
            out.append({"id": "withdraw", "label": "Cancel deal", "kind": "ghost"})
        elif s == "escrow_funded":
            out = [{"id": "submit_post", "label": "Submit post link", "kind": "primary", "needs": "url"}]
        elif s == "live":
            out = [{"id": "nudge", "label": "Remind the brand", "kind": "secondary"}]
    else:
        if turn:
            out = [
                {"id": "accept_counter", "label": f"Accept {inr(on_table['amount'])} and sign", "kind": "primary"},
                {"id": "propose", "label": "Propose changes", "kind": "secondary", "needs": "terms"},
                {"id": "decline_counter", "label": "Decline", "kind": "ghost"},
            ]
        elif s == "offer":
            out = [{"id": "withdraw", "label": "Withdraw offer", "kind": "ghost"}]
        elif s == "contract" and not c.get("signed_by_brand"):
            out = [{"id": "sign", "label": "E-sign contract", "kind": "primary"}]
        elif s == "contract" and c.get("signed_by_creator") and d.get("kind") != "collective":
            out = [{"id": "fund", "label": f"Fund escrow {inr(d['amount'])}", "kind": "primary", "needs": "payment"}]
        if s == "contract" and not d.get("escrow") and d.get("kind") != "collective":
            out.append({"id": "withdraw", "label": "Cancel deal", "kind": "ghost"})
        elif s == "live":
            out = [
                {"id": "approve", "label": "Approve post", "kind": "primary"},
                {"id": "request_revision", "label": "Ask for a revision", "kind": "secondary", "needs": "note"},
            ]
    return out


def view(d: dict, role: str) -> dict:
    d = sweep(d)
    contracts.ensure(d)
    db = get_db()
    creator, brand = _names(d)
    listing = db.listings.find_one({"_id": d.get("listing_id")}) if d.get("listing_id") else None
    reached = ORDER.get(d["stage"], -1)
    times = {}
    for e in d.get("timeline") or []:
        times.setdefault(e["stage"], e["at"])
    steps = []
    for i, (key, label) in enumerate(RAIL):
        status = "done" if i < reached or d["stage"] == "paid" else "current" if i == reached else "upcoming"
        if d["stage"] == "declined":
            status = "done" if key == "offer" else "upcoming"
        steps.append({"key": key, "label": label, "status": status, "at": times.get(key)})
    terms = {"deliverables": d.get("deliverables"), "usage_rights_days": d.get("usage_rights_days"), "exclusivity_days": d.get("exclusivity_days")}
    fair_total = d.get("fair_at_offer")
    if not fair_total and creator:
        fair_total = fair_price(creator, brand or None, terms, with_model=False)["total"]
    if role == "brand" and d.get("channel") == "link_in_bio" and (creator.get("public_scopes") or {}).get("rates") is False:
        fair_total = None  # the creator hides rates on their public page, so the guest brand doesn't see them here
    alerts = []
    if d["stage"] == "offer" and fair_total and d["amount"] < 0.7 * fair_total:
        alerts.append({"kind": "low_offer", "text": f"This offer is {round((1 - d['amount'] / fair_total) * 100)}% below the fair price", "fair": fair_total})
    due = auto_release_due(d)
    if due:
        days_left = (due - today()).days
        late = d.get("verify_due") and today() > date.fromisoformat(d["verify_due"])
        alerts.append(
            {
                "kind": "verify_late" if late else "verify_window",
                "text": (f"{brand.get('name', 'The brand')} is {(today() - date.fromisoformat(d['verify_due'])).days} days late reviewing the post" if late else f"{brand.get('name', 'The brand')} has until {day_month(d['verify_due'])} to review the post"),
                "detail": f"If there's no response, the post is approved automatically in {days_left} day{'s' if days_left != 1 else ''}.",
            }
        )
    if d["stage"] == "escrow_funded" and d.get("revisions"):
        alerts.append({"kind": "revision", "text": f"{brand.get('name', 'The brand')} asked for a revision", "detail": d["revisions"][-1]["reason"]})
    if d["stage"] == "verified" and (d.get("payout") or {}).get("status") == "not_connected":
        alerts.append(
            {
                "kind": "payout_not_connected",
                "text": "Approved, payout not connected",
                "detail": "Nothing has been paid out yet: JodiDar has no payout partner connected. The payment stays in escrow until one is.",
            }
        )
    invoice = db.invoices.find_one({"deal_id": d["_id"]})
    collective = None
    if d.get("kind") == "collective":
        col = db.collectives.find_one({"_id": d.get("collective_id")})
        if col:
            member = next((m for m in col["members"] if m["creator_id"] == d["creator_id"]), None)
            collective = {"id": col["_id"], "size": len(col["members"]), "total": col["total"], "funded": bool(col.get("funded")), "split": member["split"] if member else None}
    return {
        "id": d["_id"],
        "kind": d.get("kind", "single"),
        "stage": d["stage"],
        "amount": d["amount"],
        "fair_total": fair_total,
        "deliverables": deliverables_label(terms),
        "usage_rights_days": d.get("usage_rights_days") or 0,
        "exclusivity_days": d.get("exclusivity_days") or 0,
        "message": d.get("message"),
        "creator": {"id": creator.get("_id"), "name": creator.get("name"), "handle": creator.get("handle"), "avatar_hue": creator.get("avatar_hue", 260), "is_reference": creator.get("is_reference", False)},
        "brand": {"id": brand.get("_id"), "name": brand.get("name", "Brand"), "hue": brand.get("hue", 260), "verified": brand.get("verified", True)},
        "listing": {"id": listing["_id"], "title": listing["title"]} if listing else None,
        "steps": steps,
        "timeline": list(reversed(d.get("timeline") or [])),
        "counter": d.get("counter"),
        "status": contracts.status_of(d),
        "status_label": contracts.STATUS_LABELS[contracts.status_of(d)],
        "versions": contracts.versions_view(d),
        "agreed_version": d.get("agreed_version"),
        "awaiting": contracts.awaiting(d) if d["stage"] == "offer" else None,
        "terms": contracts.latest(d)["terms"],
        "post_by": d.get("post_by"),
        "submissions": d.get("submissions") or [],
        "revision_round": len(d.get("revisions") or []),
        "contract": {**(d.get("contract") or {}), "terms": contract_terms(d, creator, brand)} if d.get("contract") or d["stage"] == "offer" else None,
        "escrow": d.get("escrow"),
        "proof_url": d.get("proof_url"),
        "verify_due": d.get("verify_due"),
        "predicted": d.get("predicted"),
        "result": d.get("result"),
        "rating": {k: v for k, v in d["rating"].items() if k != "by"} if d.get("rating") else None,
        "auto_release_on": due.isoformat() if due else None,
        "verification": d.get("verification"),
        "post_check": d.get("post_check") or (post_check(d) if d["stage"] == "live" else None),
        "revisions": d.get("revisions") or [],
        "payout": d.get("payout"),
        "payouts": d.get("payouts") or [],
        "invoice": {"id": invoice["_id"], "number": invoice["number"], "status": invoice["status"]} if invoice else None,
        "alerts": alerts,
        "collective": collective,
        "actions": actions_for(d, role),
        "payments_mode": payments.mode(),
        "payout_mode": payments.payout_mode(),
    }


def contract_terms(d: dict, creator: dict, brand: dict) -> list[str]:
    terms = {"deliverables": d.get("deliverables")}
    brand_name = (brand.get("name") or "the brand").rstrip(".")
    t = [
        f"{creator.get('name', 'The creator')} will publish {deliverables_label(terms)} for {brand_name}.",
        f"Fee: {inr_full(d['amount'])}, paid into JodiDar escrow before the post goes live.",
        f"The brand reviews the post and approves it or asks for a revision. If the brand doesn't respond, the post is approved automatically {VERIFY_DAYS + GRACE_DAYS} days after it's submitted.",
        "The fee is released to the creator after approval, through JodiDar's payout partner.",
        "The post carries a paid-partnership label and stays up for at least 30 days.",
    ]
    if d.get("post_by"):
        t.insert(1, f"Post by {day_month(d['post_by'])}.")
    if d.get("usage_rights_days"):
        t.append(f"The brand may use the post in paid ads for {d['usage_rights_days']} days.")
    if d.get("exclusivity_days"):
        t.append(f"No competing brand in the same category for {d['exclusivity_days']} days.")
    t.append("Either side may cancel before escrow is funded at no cost. Once funded, the fee stays in escrow until the post is approved, by the brand or automatically.")
    return t


def list_for(role: str, owner_id: str) -> list[dict]:
    q = {"creator_id": owner_id} if role == "creator" else {"brand_id": owner_id}
    rows = []
    for d in get_db().deals.find(q):
        v = view(d, role)
        rows.append(
            {
                "id": v["id"],
                "kind": v["kind"],
                "stage": v["stage"],
                "amount": v["amount"],
                "fair_total": v["fair_total"],
                "deliverables": v["deliverables"],
                "creator": v["creator"],
                "brand": v["brand"],
                "listing": v["listing"],
                "alerts": v["alerts"],
                "actions": [a["id"] for a in v["actions"]],
                "updated": (v["timeline"][0]["at"] if v["timeline"] else None),
                "collective": v["collective"],
                "counter": v["counter"],
            }
        )
    rows.sort(key=lambda r: r["updated"] or "", reverse=True)
    return rows


def fund_collective(collective_id: str, mode: str, ref: str) -> dict:
    """Called only after a verified (or, in demo mode, simulated) payment for the whole pack."""
    db = get_db()
    col = db.collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    if col.get("funded"):
        raise HTTPException(409, "Already funded")
    escrow = {"mode": mode, "ref": ref, "funded_at": now_iso(), "amount": col["total"]}
    db.collectives.update_one({"_id": collective_id}, {"$set": {"funded": True, "escrow": escrow, "status": "funded"}})
    for d in db.deals.find({"collective_id": collective_id}):
        _maybe_fund_from_collective(d)
        _save(d)
    return collective_view(collective_id)


def collective_view(collective_id: str, viewer: str | None = None) -> dict:
    """The brand sees every member's price and split. A member (`viewer`) sees the pack
    and everyone's progress, but only their own price and split."""
    db = get_db()
    col = db.collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    brand = db.brands.find_one({"_id": col["brand_id"]}) or {}
    listing = db.listings.find_one({"_id": col["listing_id"]}) or {}
    deals = {d["creator_id"]: sweep(d) for d in db.deals.find({"collective_id": collective_id})}
    creators = {c["_id"]: c for c in db.creators.find({"_id": {"$in": [m["creator_id"] for m in col["members"]]}}, {"name": 1, "handle": 1, "avatar_hue": 1, "is_reference": 1})}
    members = []
    for m in col["members"]:
        d = deals.get(m["creator_id"]) or {}
        c = creators.get(m["creator_id"], {})
        members.append(
            {
                "creator_id": m["creator_id"],
                "name": c.get("name"),
                "handle": c.get("handle"),
                "avatar_hue": c.get("avatar_hue", 260),
                "is_reference": c.get("is_reference", False),
                "price": m["price"],
                "split": m["split"],
                "deal_id": d.get("_id"),
                "stage": d.get("stage"),
                "proof_url": d.get("proof_url"),
                "paid": d.get("stage") == "paid",
            }
        )
    stages: dict[str, int] = {}
    for m in members:
        stages[m["stage"] or "offer"] = stages.get(m["stage"] or "offer", 0) + 1
    if viewer:
        for m in members:
            if m["creator_id"] != viewer:
                m.update({"price": None, "split": None, "deal_id": None, "proof_url": None})
    return {
        "id": col["_id"],
        "brand": {"id": brand.get("_id"), "name": brand.get("name")},
        "listing": {"id": listing.get("_id"), "title": listing.get("title")},
        "total": col["total"],
        "combined_reach": col.get("combined_reach"),
        "funded": bool(col.get("funded")),
        "escrow": col.get("escrow"),
        "paid_out": sum(m["price"] or 0 for m in members if m["paid"]) if not viewer else None,
        # The whole pack is held in escrow; a member who declines has their share returned to the brand.
        "refunded": (sum(m["price"] or 0 for m in members if m["stage"] == "declined") if col.get("funded") else 0) if not viewer else None,
        "members": members,
        "stages": stages,
        "created_at": col.get("created_at"),
        "payments_mode": payments.mode(),
    }
