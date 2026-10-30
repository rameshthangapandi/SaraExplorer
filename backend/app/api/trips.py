"""Consent, payment and booking endpoints — the only path by which anything gets booked."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.booking import booking_dict, consent_card, create_bookings
from app.config import get_settings
from app.db import aware, get_db, utcnow
from app.models import Booking, ConsentRequest, Payment, User
from app.payments import gateway
from app.security.deps import get_current_user, owned
from app.security.rate_limit import client_ip, enforce

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["trips"])


async def _expire_if_needed(db: AsyncSession, c: ConsentRequest) -> None:
    if c.status in ("pending", "awaiting_payment") and aware(c.hold_expires_at) <= utcnow():
        c.status = "expired"
        audit(db, "consent.expired", c.user_id, c.id)
        await db.commit()


# ---------------------------------------------------------------- consents

@router.get("/consents/{consent_id}")
async def get_consent(consent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    await _expire_if_needed(db, c)
    return consent_card(c)


@router.post("/consents/{consent_id}/approve")
async def approve(consent_id: str, request: Request, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)):
    """User pressed Approve & Pay: create (or reuse) a gateway order for the server-side total."""
    await enforce(f"approve:{user.id}", 10, 60)
    c = await owned(db, ConsentRequest, consent_id, user)
    await _expire_if_needed(db, c)
    if c.status not in ("pending", "awaiting_payment"):
        raise HTTPException(409, f"This request is already {c.status}.")
    if c.total_inr > user.spend_cap_inr:
        raise HTTPException(403, "Total is above your spending limit.")

    amount_paise = c.total_inr * 100
    existing = await db.scalar(select(Payment).where(Payment.consent_id == c.id, Payment.status == "created"))
    if existing is None:
        try:
            order = await gateway.create_order(amount_paise, receipt=c.id)
        except gateway.PaymentError as exc:
            raise HTTPException(502, str(exc))
        existing = Payment(consent_id=c.id, user_id=user.id, provider=order["provider"], order_id=order["order_id"],
                           amount_paise=amount_paise)
        db.add(existing)
    c.status = "awaiting_payment"
    audit(db, "consent.approved", user.id, c.id, total_inr=c.total_inr, ip=client_ip(request))
    await db.commit()
    s = get_settings()
    return {
        "provider": existing.provider, "order_id": existing.order_id, "amount_paise": existing.amount_paise,
        "currency": "INR", "key_id": s.razorpay_key_id if existing.provider == "razorpay" else None,
        "name": "Sara Explorer", "description": c.title, "prefill": {"name": user.name, "email": user.email},
        "hold_expires_at": aware(c.hold_expires_at).isoformat(),
    }


@router.post("/consents/{consent_id}/reject")
async def reject(consent_id: str, request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    if c.status in ("pending", "awaiting_payment"):
        c.status = "rejected"
        c.decided_at = utcnow()
        await db.execute(update(Payment).where(Payment.consent_id == c.id, Payment.status == "created")
                         .values(status="failed"))
        audit(db, "consent.rejected", user.id, c.id, ip=client_ip(request))
        await db.commit()
    return consent_card(c)


# ---------------------------------------------------------------- payments

class VerifyIn(BaseModel):
    order_id: str = Field(max_length=64)
    payment_id: str = Field(max_length=64)
    signature: str = Field(max_length=128)


class MockPayIn(BaseModel):
    order_id: str = Field(max_length=64)


@router.post("/payments/mock/pay")
async def mock_pay(body: MockPayIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Free built-in test gateway. Disabled unless PAYMENT_PROVIDER=mock."""
    if get_settings().payment_provider != "mock":
        raise HTTPException(404, "Not found")
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id))
    if payment is None or payment.status != "created":
        raise HTTPException(404, "Order not found or already used")
    consent = await db.get(ConsentRequest, payment.consent_id)
    if aware(consent.hold_expires_at) <= utcnow():
        raise HTTPException(409, "The price hold expired. Ask Sara to search again.")
    return gateway.mock_capture(payment.order_id)


async def _settle(db: AsyncSession, payment: Payment, payment_id: str, ip: str) -> list[Booking]:
    # Atomic state change: only one request can move created -> paid, so bookings are created exactly once.
    result = await db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == "created")
                              .values(status="paid", payment_id=payment_id))
    if result.rowcount != 1:
        await db.rollback()
        return []
    consent = await db.get(ConsentRequest, payment.consent_id)
    consent.status = "paid"
    consent.decided_at = utcnow()
    bookings = create_bookings(db, consent)
    audit(db, "payment.captured", payment.user_id, payment.order_id, amount_paise=payment.amount_paise,
          provider=payment.provider, ip=ip)
    audit(db, "booking.created", payment.user_id, consent.id, count=len(bookings))
    await db.commit()
    return bookings


@router.post("/payments/verify")
async def verify(body: VerifyIn, request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    await enforce(f"verify:{user.id}", 20, 60)
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id))
    if payment is None:
        raise HTTPException(404, "Order not found")
    if not gateway.verify_signature(body.order_id, body.payment_id, body.signature):
        audit(db, "payment.signature_invalid", user.id, body.order_id, ip=client_ip(request))
        await db.commit()
        raise HTTPException(400, "Payment could not be verified.")
    if payment.status == "paid":
        rows = (await db.scalars(select(Booking).where(Booking.consent_id == payment.consent_id))).all()
        return {"status": "paid", "bookings": [booking_dict(b) for b in rows]}
    bookings = await _settle(db, payment, body.payment_id, client_ip(request))
    if not bookings:
        rows = (await db.scalars(select(Booking).where(Booking.consent_id == payment.consent_id))).all()
        return {"status": "paid", "bookings": [booking_dict(b) for b in rows]}
    return {"status": "paid", "bookings": [booking_dict(b) for b in bookings]}


@router.post("/payments/webhook", include_in_schema=False)
async def webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """Razorpay webhook (server-to-server). Settles payments even if the browser closed mid-checkout."""
    body = await request.body()
    if len(body) > 64_000 or not gateway.verify_webhook(body, request.headers.get("x-razorpay-signature", "")):
        raise HTTPException(400, "Invalid signature")
    event = json.loads(body)
    if event.get("event") == "payment.captured":
        entity = event["payload"]["payment"]["entity"]
        payment = await db.scalar(select(Payment).where(Payment.order_id == entity.get("order_id")))
        if payment and payment.status == "created" and entity.get("amount") == payment.amount_paise:
            await _settle(db, payment, entity["id"], client_ip(request))
    return {"ok": True}


# ---------------------------------------------------------------- bookings

@router.get("/bookings")
async def bookings(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Booking).where(Booking.user_id == user.id)
                             .order_by(Booking.created_at.desc()))).all()
    return [booking_dict(b) for b in rows]


@router.post("/bookings/{booking_id}/cancel")
async def cancel_booking(booking_id: str, request: Request, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    b = await owned(db, Booking, booking_id, user)
    if b.status == "cancelled":
        raise HTTPException(409, "Already cancelled")
    b.status = "cancelled"
    b.cancelled_at = utcnow()
    audit(db, "booking.cancelled", user.id, b.id, ip=client_ip(request))
    await db.commit()
    return booking_dict(b)
