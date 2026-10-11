"""Payments into escrow, honest by construction.

- Razorpay TEST mode when test keys are set (rzp_test_...). A failed provider
  call is an error (502): it never turns into a simulated success.
- No provider: demo mode records a payment labelled simulated (no money moves);
  outside demo mode funding is refused (503) and says no money has moved.
- Every order is stored with what it pays for (a deal or a collective) and the
  amount. Checkout verification must match both, and a payment is used once.
- The webhook verifies Razorpay's signature and applies each event once.
- Payouts to creators aren't connected. No payout status or bank reference is
  ever invented: outside demo mode an approved deal waits at "payout not connected".
"""
from __future__ import annotations

import hashlib
import hmac
import json
import logging
import uuid

import httpx
from fastapi import HTTPException

from ..config import get_settings, now_iso
from ..db import get_db

log = logging.getLogger("jodidar.payments")

NO_MONEY = "no money has moved"


def mode() -> str:
    """How brands fund deals: 'razorpay-test', 'simulated' (demo mode only) or 'not_connected'."""
    s = get_settings()
    if s.has_razorpay:
        return "razorpay-test"
    return "simulated" if s.demo_mode else "not_connected"


def payout_mode() -> str:
    """Payouts to creators: there is no payout integration. Demo mode simulates them for simulated payments only."""
    return "simulated" if get_settings().demo_mode else "not_connected"


def create_order(amount_inr: int, kind: str, ref_id: str) -> dict:
    """Start a payment for a deal or collective. Reuses an unpaid order for the same thing
    and amount, so a double click doesn't create two."""
    s = get_settings()
    db = get_db()
    if not s.has_razorpay:
        if not s.demo_mode:
            raise HTTPException(503, f"Payments aren't connected yet, so {NO_MONEY}. Ask the JodiDar team to connect Razorpay.")
        ref = f"sim_{uuid.uuid4().hex[:10]}"
        db.payments.insert_one(
            {"_id": ref, "mode": "simulated", "kind": kind, "ref_id": ref_id, "amount": amount_inr, "status": "simulated", "created_at": now_iso()}
        )
        return {"mode": "simulated", "ref": ref, "amount": amount_inr}
    open_order = db.payments.find_one({"mode": "razorpay-test", "kind": kind, "ref_id": ref_id, "amount": amount_inr, "status": "created"})
    if open_order:
        return {"mode": "razorpay-test", "order_id": open_order["_id"], "key_id": s.razorpay_key_id, "amount": amount_inr}
    try:
        r = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=(s.razorpay_key_id, s.razorpay_key_secret),
            json={"amount": amount_inr * 100, "currency": "INR", "receipt": ref_id[:40], "notes": {"purpose": "JodiDar escrow (test mode)", "kind": kind, "ref": ref_id}},
            timeout=10,
        )
        r.raise_for_status()
        order = r.json()
        order_id = order["id"]
        if int(order.get("amount", -1)) != amount_inr * 100:
            raise ValueError("order amount differs")
    except (httpx.HTTPError, ValueError, KeyError) as e:
        log.warning("Razorpay order failed: %s", type(e).__name__)
        raise HTTPException(502, f"Razorpay couldn't start the payment, so {NO_MONEY}. Try again in a minute.") from None
    db.payments.insert_one(
        {
            "_id": order_id,
            "mode": "razorpay-test",
            "kind": kind,
            "ref_id": ref_id,
            "amount": amount_inr,
            "currency": "INR",
            "status": "created",
            "payment_id": None,
            "created_at": now_iso(),
        }
    )
    return {"mode": "razorpay-test", "order_id": order_id, "key_id": s.razorpay_key_id, "amount": amount_inr}


def signature_ok(order_id: str, payment_id: str, signature: str) -> bool:
    secret = get_settings().razorpay_key_secret or ""
    if not secret:
        return False
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def verify_checkout(kind: str, ref_id: str, amount_inr: int, order_id: str, payment_id: str, signature: str) -> dict:
    """Checks a Razorpay checkout result against the stored order. Returns the payment
    record once it's marked paid; raises 4xx for anything that doesn't match."""
    db = get_db()
    p = db.payments.find_one({"_id": order_id})
    if not p or p.get("mode") != "razorpay-test" or p["kind"] != kind or p["ref_id"] != ref_id:
        raise HTTPException(400, "That payment isn't for this deal.")
    if not signature_ok(order_id, payment_id, signature):
        raise HTTPException(400, "Payment signature didn't match")
    if p["amount"] != amount_inr:
        raise HTTPException(409, "The amount changed after this payment started. Start the payment again.")
    if p["status"] == "paid":
        if p.get("payment_id") == payment_id:
            return p  # the same checkout reported twice
        raise HTTPException(409, "This order was already paid.")
    if db.payments.find_one({"payment_id": payment_id}):
        raise HTTPException(409, "This payment was already used.")
    res = db.payments.update_one(
        {"_id": order_id, "status": {"$ne": "paid"}},
        {"$set": {"status": "paid", "payment_id": payment_id, "paid_at": now_iso(), "confirmed_by": "checkout"}},
    )
    if res.modified_count != 1:
        raise HTTPException(409, "This order was already paid.")
    return db.payments.find_one({"_id": order_id})


# ------------------------------------------------------------------ webhook
def webhook_signature_ok(body: bytes, signature: str | None) -> bool:
    secret = get_settings().razorpay_webhook_secret
    if not secret or not signature:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)


def apply_webhook(body: bytes, signature: str | None, event_id: str | None) -> tuple[dict | None, dict]:
    """Verifies and records one Razorpay webhook. Returns (payment to fund or None, reply)."""
    if not get_settings().razorpay_webhook_secret:
        raise HTTPException(503, "The Razorpay webhook isn't configured (RAZORPAY_WEBHOOK_SECRET).")
    if not webhook_signature_ok(body, signature):
        raise HTTPException(400, "Webhook signature didn't match")
    try:
        event = json.loads(body)
    except ValueError:
        raise HTTPException(400, "Webhook body isn't JSON") from None
    db = get_db()
    key = event_id or hashlib.sha256(body).hexdigest()
    if db.webhook_events.find_one({"_id": key}):
        return None, {"ok": True, "duplicate": True}
    db.webhook_events.insert_one({"_id": key, "event": event.get("event"), "at": now_iso()})
    entity = ((event.get("payload") or {}).get("payment") or {}).get("entity") or {}
    order_id, payment_id, paise = entity.get("order_id"), entity.get("id"), entity.get("amount")
    p = db.payments.find_one({"_id": order_id}) if order_id else None
    if not p:
        return None, {"ok": True, "ignored": "unknown order"}
    if event.get("event") in ("payment.captured", "order.paid"):
        if paise != p["amount"] * 100:
            log.warning("Webhook amount mismatch for order %s", order_id)
            return None, {"ok": True, "ignored": "amount mismatch"}
        if p["status"] != "paid":
            other = db.payments.find_one({"payment_id": payment_id, "_id": {"$ne": order_id}})
            if other:
                return None, {"ok": True, "ignored": "payment already used"}
            db.payments.update_one({"_id": order_id}, {"$set": {"status": "paid", "payment_id": payment_id, "paid_at": now_iso(), "confirmed_by": "webhook"}})
        return db.payments.find_one({"_id": order_id}), {"ok": True}
    if event.get("event") == "payment.failed" and p["status"] != "paid":
        db.payments.update_one({"_id": order_id}, {"$set": {"status": "failed", "failed_at": now_iso()}})
    return None, {"ok": True}
