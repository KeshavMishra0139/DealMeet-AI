"""Escrow payments. Razorpay TEST mode when test keys are set (rzp_test_...),
otherwise a simulated escrow so the demo never needs the network.

Only the two REST calls the flow needs are used: create an order, and verify
the checkout signature (HMAC-SHA256 of "order_id|payment_id").
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import uuid

import httpx

from ..config import get_settings

log = logging.getLogger("jodidar.payments")


def mode() -> str:
    return "razorpay-test" if get_settings().has_razorpay else "simulated"


def create_order(amount_inr: int, receipt: str) -> dict:
    s = get_settings()
    if not s.has_razorpay:
        return {"mode": "simulated", "ref": f"esc_sim_{uuid.uuid4().hex[:4].upper()}", "amount": amount_inr}
    try:
        r = httpx.post(
            "https://api.razorpay.com/v1/orders",
            auth=(s.razorpay_key_id, s.razorpay_key_secret),
            json={"amount": amount_inr * 100, "currency": "INR", "receipt": receipt[:40], "notes": {"purpose": "JodiDar escrow (test mode)"}},
            timeout=10,
        )
        r.raise_for_status()
        order = r.json()
        return {"mode": "razorpay-test", "order_id": order["id"], "key_id": s.razorpay_key_id, "amount": amount_inr}
    except Exception as e:  # network down or bad keys: keep the demo moving
        log.warning("Razorpay order failed (%s); using simulated escrow", e)
        return {"mode": "simulated", "ref": f"esc_sim_{uuid.uuid4().hex[:4].upper()}", "amount": amount_inr}


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    secret = get_settings().razorpay_key_secret or ""
    expected = hmac.new(secret.encode(), f"{order_id}|{payment_id}".encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature)
