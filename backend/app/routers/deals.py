"""Deal rail, collective escrow, payments and invoices."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import now_iso, today
from ..db import get_db
from ..services import auth as au
from ..services import deals as rail
from ..services import payments
from ..services.creator_ctx import load_creator
from ..services.pdf import invoice_pdf

router = APIRouter(prefix="/api", tags=["deals"])


@router.get("/creators/{creator_id}/deals")
def creator_deals(creator_id: str, _: dict = Depends(au.own_creator)):
    load_creator(creator_id)
    db = get_db()
    invoices = []
    for inv in db.invoices.find({"creator_id": creator_id, "off_platform": True}):
        days = (today() - date.fromisoformat(inv["due"])).days
        invoices.append({**{k: inv[k] for k in ("number", "to", "amount", "issued", "due", "status")}, "id": inv["_id"], "days_late": max(0, days) if inv["status"] == "unpaid" else 0, "reminders": inv.get("reminders", [])})
    return {"deals": rail.list_for("creator", creator_id), "invoices": invoices}


@router.get("/brands/{brand_id}/deals")
def brand_deals(brand_id: str, _: dict = Depends(au.own_brand)):
    db = get_db()
    cols = []
    for col in db.collectives.find({"brand_id": brand_id}):
        cols.append(rail.collective_view(col["_id"]))
    return {"deals": [d for d in rail.list_for("brand", brand_id) if d["kind"] != "collective"], "collectives": cols}


def _party(deal_id: str, user: dict) -> tuple[dict, str]:
    d = rail._get(deal_id)
    return d, au.deal_side(user, d)


@router.get("/deals/{deal_id}")
def deal(deal_id: str, user: dict = Depends(au.current_user)):
    d, side = _party(deal_id, user)
    return rail.view(d, side)


class ActionIn(BaseModel):
    # The acting side comes from the session. A role sent here must match it.
    role: Literal["creator", "brand"] | None = None
    action: str = Field(max_length=32)
    amount: int | None = Field(default=None, ge=0, le=50_000_000)
    note: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=300)
    name: str | None = Field(default=None, max_length=80)


@router.post("/deals/{deal_id}/action")
def deal_action(deal_id: str, body: ActionIn, user: dict = Depends(au.current_user)):
    _, side = _party(deal_id, user)
    if body.role and body.role != side:
        raise HTTPException(403, f"You're the {side} on this deal.")
    return rail.act(deal_id, side, body.action, body.model_dump())


def _brand_party(deal_id: str, user: dict) -> dict:
    d, side = _party(deal_id, user)
    if side != "brand":
        raise HTTPException(403, "Only the brand on this deal can fund it.")
    return d


def _ready_to_fund(d: dict) -> None:
    c = d.get("contract") or {}
    if d.get("kind") == "collective":
        raise HTTPException(409, "Fund the collective once from its page")
    if d["stage"] != "contract" or not (c.get("signed_by_creator") and c.get("signed_by_brand")):
        raise HTTPException(409, "Both sides sign before escrow is funded")


@router.post("/deals/{deal_id}/pay")
def start_payment(deal_id: str, user: dict = Depends(au.current_user)):
    """Start escrow funding: a Razorpay test order, or (demo mode only) a simulated payment."""
    d = _brand_party(deal_id, user)
    _ready_to_fund(d)
    order = payments.create_order(d["amount"], "deal", deal_id)
    if order["mode"] == "simulated":
        view = rail.act(deal_id, "brand", "fund", {"mode": "simulated", "payment_ref": order["ref"]})
        return {"mode": "simulated", "deal": view}
    return order


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/deals/{deal_id}/pay/verify")
def verify_payment(deal_id: str, body: VerifyIn, user: dict = Depends(au.current_user)):
    d = _brand_party(deal_id, user)
    p = payments.verify_checkout("deal", deal_id, d["amount"], body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature)
    if (d.get("escrow") or {}).get("ref") == p["payment_id"]:
        return rail.view(d, "brand")  # already funded by this payment (a repeat or the webhook got here first)
    return rail.act(deal_id, "brand", "fund", {"mode": "razorpay-test", "payment_ref": p["payment_id"]})


def _collective(collective_id: str) -> dict:
    col = get_db().collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    return col


def _own_collective(collective_id: str, user: dict) -> dict:
    col = _collective(collective_id)
    au.require_brand(user, col["brand_id"])
    return col


@router.get("/collectives/{collective_id}")
def collective(collective_id: str, user: dict = Depends(au.current_user)):
    col = _collective(collective_id)
    if user.get("role") == "creator" and any(m["creator_id"] == user.get("creator_id") for m in col["members"]):
        return rail.collective_view(collective_id, viewer=user["creator_id"])
    au.require_brand(user, col["brand_id"])
    return rail.collective_view(collective_id)


@router.post("/collectives/{collective_id}/fund")
def fund_collective(collective_id: str, user: dict = Depends(au.current_user)):
    col = _own_collective(collective_id, user)
    if col.get("funded"):
        raise HTTPException(409, "Already funded")
    order = payments.create_order(col["total"], "collective", collective_id)
    if order["mode"] == "simulated":
        return rail.fund_collective(collective_id, "simulated", order["ref"])
    return order


@router.post("/collectives/{collective_id}/fund/verify")
def verify_collective(collective_id: str, body: VerifyIn, user: dict = Depends(au.current_user)):
    col = _own_collective(collective_id, user)
    p = payments.verify_checkout("collective", collective_id, col["total"], body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature)
    if col.get("funded") and (col.get("escrow") or {}).get("ref") == p["payment_id"]:
        return rail.collective_view(collective_id)
    return rail.fund_collective(collective_id, "razorpay-test", p["payment_id"])


@router.post("/payments/razorpay/webhook")
async def razorpay_webhook(request: Request):
    """Razorpay calls this; it proves itself with the webhook signature, not a session.
    Each event is applied once. A captured payment funds its deal or collective if the
    brand's browser didn't finish the checkout step."""
    body = await request.body()
    payment, reply = payments.apply_webhook(body, request.headers.get("x-razorpay-signature"), request.headers.get("x-razorpay-event-id"))
    if payment:
        _fund_from(payment)
    return reply


def _fund_from(p: dict) -> None:
    db = get_db()
    if p["kind"] == "deal":
        d = db.deals.find_one({"_id": p["ref_id"]})
        c = (d or {}).get("contract") or {}
        if d and d["stage"] == "contract" and c.get("signed_by_creator") and c.get("signed_by_brand") and d["amount"] == p["amount"]:
            rail.act(d["_id"], "brand", "fund", {"mode": "razorpay-test", "payment_ref": p["payment_id"]})
    elif p["kind"] == "collective":
        col = db.collectives.find_one({"_id": p["ref_id"]})
        if col and not col.get("funded") and col["total"] == p["amount"]:
            rail.fund_collective(col["_id"], "razorpay-test", p["payment_id"])


@router.post("/collectives/{collective_id}/release")
def release_verified(collective_id: str, user: dict = Depends(au.current_user)):
    """Approve every submitted member post at once. Payouts follow the honest-payments rules."""
    _own_collective(collective_id, user)
    db = get_db()
    for d in db.deals.find({"collective_id": collective_id, "stage": "live"}):
        rail.act(d["_id"], "brand", "approve", {})
    return rail.collective_view(collective_id)


# ------------------------------------------------------------------ invoices
@router.get("/invoices/{invoice_id}.pdf")
def invoice_file(invoice_id: str, user: dict = Depends(au.current_user)):
    db = get_db()
    inv = db.invoices.find_one({"_id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    deal = db.deals.find_one({"_id": inv.get("deal_id")}) if inv.get("deal_id") else None
    # The creator who issued it, or the brand on the deal it bills.
    if not (user.get("role") == "creator" and user.get("creator_id") == inv["creator_id"]):
        if not deal:
            raise HTTPException(403, "Only the creator who issued this invoice can open it.")
        au.deal_side(user, deal)
    creator = db.creators.find_one({"_id": inv["creator_id"]}) or {}
    if deal and deal.get("listing_id"):
        listing = db.listings.find_one({"_id": deal["listing_id"]})
        deal = {**deal, "listing_title": listing["title"] if listing else None}
    pdf = invoice_pdf(inv, creator, deal)
    return Response(pdf, media_type="application/pdf", headers={"Content-Disposition": f'inline; filename="{inv["number"]}.pdf"'})


class InvoiceIn(BaseModel):
    to: str = Field(min_length=2, max_length=80)
    amount: int = Field(ge=100, le=50_000_000)
    description: str = Field(default="Creator services", max_length=120)
    due_days: int = Field(default=7, ge=0, le=90)


@router.post("/creators/{creator_id}/invoices")
def log_off_platform(creator_id: str, body: InvoiceIn, _: dict = Depends(au.own_creator)):
    c = load_creator(creator_id)
    db = get_db()
    seq = db.invoices.count_documents({"creator_id": creator_id}) + 1
    inv = {
        "_id": f"inv_{uuid.uuid4().hex[:8]}",
        "number": rail.invoice_number(c, seq),
        "creator_id": creator_id,
        "deal_id": None,
        "to": body.to.strip(),
        "amount": body.amount,
        "description": body.description,
        "issued": today().isoformat(),
        "due": (today() + timedelta(days=body.due_days)).isoformat(),
        "status": "unpaid",
        "off_platform": True,
        "reminders": [],
    }
    db.invoices.insert_one(inv)
    return {"id": inv["_id"]}


class InvoiceAction(BaseModel):
    action: Literal["remind", "mark_paid"]


@router.post("/invoices/{invoice_id}")
def invoice_action(invoice_id: str, body: InvoiceAction, user: dict = Depends(au.current_user)):
    db = get_db()
    inv = db.invoices.find_one({"_id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    au.require_creator(user, inv["creator_id"])
    if body.action == "remind":
        db.invoices.update_one({"_id": invoice_id}, {"$push": {"reminders": {"at": now_iso(), "channel": "logged"}}})
    else:
        db.invoices.update_one({"_id": invoice_id}, {"$set": {"status": "paid", "paid_at": now_iso()}})
    return {"ok": True}
