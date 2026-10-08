"""Deal rail, collective escrow, payments and invoices."""
from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Literal

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from ..config import now_iso, today
from ..db import get_db
from ..services import deals as rail
from ..services import payments
from ..services.creator_ctx import load_creator
from ..services.pdf import invoice_pdf

router = APIRouter(prefix="/api", tags=["deals"])


@router.get("/creators/{creator_id}/deals")
def creator_deals(creator_id: str):
    load_creator(creator_id)
    db = get_db()
    invoices = []
    for inv in db.invoices.find({"creator_id": creator_id, "off_platform": True}):
        days = (today() - date.fromisoformat(inv["due"])).days
        invoices.append({**{k: inv[k] for k in ("number", "to", "amount", "issued", "due", "status")}, "id": inv["_id"], "days_late": max(0, days) if inv["status"] == "unpaid" else 0, "reminders": inv.get("reminders", [])})
    return {"deals": rail.list_for("creator", creator_id), "invoices": invoices}


@router.get("/brands/{brand_id}/deals")
def brand_deals(brand_id: str):
    db = get_db()
    cols = []
    for col in db.collectives.find({"brand_id": brand_id}):
        cols.append(rail.collective_view(col["_id"]))
    return {"deals": [d for d in rail.list_for("brand", brand_id) if d["kind"] != "collective"], "collectives": cols}


@router.get("/deals/{deal_id}")
def deal(deal_id: str, role: Literal["creator", "brand"] = "creator"):
    return rail.view(rail._get(deal_id), role)


class ActionIn(BaseModel):
    role: Literal["creator", "brand"]
    action: str = Field(max_length=32)
    amount: int | None = Field(default=None, ge=0, le=50_000_000)
    note: str | None = Field(default=None, max_length=300)
    url: str | None = Field(default=None, max_length=300)
    name: str | None = Field(default=None, max_length=80)


@router.post("/deals/{deal_id}/action")
def deal_action(deal_id: str, body: ActionIn):
    return rail.act(deal_id, body.role, body.action, body.model_dump())


@router.post("/deals/{deal_id}/pay")
def start_payment(deal_id: str):
    """Start escrow funding: a Razorpay test order, or a simulated payment."""
    d = rail._get(deal_id)
    order = payments.create_order(d["amount"], deal_id)
    if order["mode"] == "simulated":
        view = rail.act(deal_id, "brand", "fund", {"mode": "simulated", "payment_ref": order["ref"]})
        return {"mode": "simulated", "deal": view}
    return order


class VerifyIn(BaseModel):
    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


@router.post("/deals/{deal_id}/pay/verify")
def verify_payment(deal_id: str, body: VerifyIn):
    if not payments.verify_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "Payment signature didn't match")
    return rail.act(deal_id, "brand", "fund", {"mode": "razorpay-test", "payment_ref": body.razorpay_payment_id})


@router.get("/collectives/{collective_id}")
def collective(collective_id: str):
    return rail.collective_view(collective_id)


@router.post("/collectives/{collective_id}/fund")
def fund_collective(collective_id: str):
    col = get_db().collectives.find_one({"_id": collective_id})
    if not col:
        raise HTTPException(404, "Collective not found")
    order = payments.create_order(col["total"], collective_id)
    if order["mode"] == "simulated":
        return rail.fund_collective(collective_id, "simulated", order["ref"])
    return order


@router.post("/collectives/{collective_id}/fund/verify")
def verify_collective(collective_id: str, body: VerifyIn):
    if not payments.verify_signature(body.razorpay_order_id, body.razorpay_payment_id, body.razorpay_signature):
        raise HTTPException(400, "Payment signature didn't match")
    return rail.fund_collective(collective_id, "razorpay-test", body.razorpay_payment_id)


@router.post("/collectives/{collective_id}/release")
def release_verified(collective_id: str):
    """Confirm every live member post at once; each member is paid their split."""
    db = get_db()
    for d in db.deals.find({"collective_id": collective_id, "stage": "live"}):
        rail.act(d["_id"], "brand", "confirm", {})
    return rail.collective_view(collective_id)


# ------------------------------------------------------------------ invoices
@router.get("/invoices/{invoice_id}.pdf")
def invoice_file(invoice_id: str):
    db = get_db()
    inv = db.invoices.find_one({"_id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    creator = db.creators.find_one({"_id": inv["creator_id"]}) or {}
    deal = db.deals.find_one({"_id": inv.get("deal_id")}) if inv.get("deal_id") else None
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
def log_off_platform(creator_id: str, body: InvoiceIn):
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
def invoice_action(invoice_id: str, body: InvoiceAction):
    db = get_db()
    inv = db.invoices.find_one({"_id": invoice_id})
    if not inv:
        raise HTTPException(404, "Invoice not found")
    if body.action == "remind":
        db.invoices.update_one({"_id": invoice_id}, {"$push": {"reminders": {"at": now_iso(), "channel": "email with invoice PDF"}}})
    else:
        db.invoices.update_one({"_id": invoice_id}, {"$set": {"status": "paid", "paid_at": now_iso()}})
    return {"ok": True}
