"""Consent, payment, booking and admin-verification endpoints — the only path by which anything gets booked.

Booking rule: a booking exists only after money is confirmed —
by an admin checking their UPI account (upi), by a signed gateway callback (razorpay), or in tests (mock)."""

import json
import logging

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.booking import BookingError, booking_dict, consent_card, create_bookings, create_consent
from app.config import get_settings
from app.db import aware, get_db, utcnow
from app.models import Booking, ConsentRequest, Payment, User
from app.payments import gateway
from app.security.deps import get_current_user, owned, require_admin
from app.security.rate_limit import client_ip, enforce

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["trips"])

OPEN = ("pending", "awaiting_payment")


async def _expire_if_needed(db: AsyncSession, c: ConsentRequest) -> None:
    # Once a UPI payment is submitted the hold no longer expires: the traveller may already have paid.
    if c.status in OPEN and aware(c.hold_expires_at) <= utcnow():
        c.status = "expired"
        await db.execute(update(Payment).where(Payment.consent_id == c.id, Payment.status == "created")
                         .values(status="failed"))
        audit(db, "consent.expired", c.user_id, c.id)
        await db.commit()


# ---------------------------------------------------------------- consents

class ConsentIn(BaseModel):
    option_ids: list[str] = Field(min_length=1, max_length=6)
    title: str = Field(default="Your trip", max_length=200)


@router.post("/consents", status_code=201)
async def new_consent(body: ConsentIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Create an approval request from options chosen in the Plan screen (same rules as Ask Sara)."""
    await enforce(f"consent:{user.id}", 20, 60)
    try:
        c = await create_consent(db, user, body.option_ids, body.title)
    except BookingError as exc:
        raise HTTPException(422, str(exc))
    return consent_card(c)


@router.get("/consents")
async def list_consents(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Approvals still in progress: awaiting approval / payment / verification, or rejected payments."""
    rows = (await db.scalars(select(ConsentRequest).where(
        ConsentRequest.user_id == user.id,
        ConsentRequest.status.in_(["pending", "awaiting_payment", "payment_submitted", "payment_rejected"]),
    ).order_by(ConsentRequest.created_at.desc()).limit(20))).all()
    for c in rows:
        await _expire_if_needed(db, c)
    return [consent_card(c) for c in rows if c.status != "expired"]


@router.get("/consents/{consent_id}")
async def get_consent(consent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    await _expire_if_needed(db, c)
    return consent_card(c)


@router.post("/consents/{consent_id}/approve")
async def approve(consent_id: str, request: Request, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)):
    """User pressed Approve & Pay: create (or reuse) a payment order for the server-side total."""
    await enforce(f"approve:{user.id}", 10, 60)
    c = await owned(db, ConsentRequest, consent_id, user)
    await _expire_if_needed(db, c)
    if c.status not in OPEN:
        raise HTTPException(409, f"This request is already {c.status.replace('_', ' ')}.")
    if c.total_inr > user.spend_cap_inr:
        raise HTTPException(403, "Total is above your spending limit.")

    amount_paise = c.total_inr * 100
    payment = await db.scalar(select(Payment).where(Payment.consent_id == c.id, Payment.status == "created"))
    if payment is None:
        try:
            order = await gateway.create_order(amount_paise, receipt=c.id)
        except gateway.PaymentError as exc:
            raise HTTPException(503, str(exc))
        payment = Payment(consent_id=c.id, user_id=user.id, provider=order["provider"], order_id=order["order_id"],
                          amount_paise=amount_paise)
        db.add(payment)
    c.status = "awaiting_payment"
    audit(db, "consent.approved", user.id, c.id, total_inr=c.total_inr, ip=client_ip(request))
    await db.commit()

    s = get_settings()
    out = {
        "provider": payment.provider, "order_id": payment.order_id, "amount_paise": payment.amount_paise,
        "currency": "INR", "key_id": s.razorpay_key_id if payment.provider == "razorpay" else None,
        "name": s.merchant_name, "description": c.title, "prefill": {"name": user.name, "email": user.email},
        "hold_expires_at": aware(c.hold_expires_at).isoformat(), "consent_id": c.id,
    }
    if payment.provider == "upi":
        out.update(upi_uri=gateway.upi_uri(payment.order_id, payment.amount_paise),
                   payee_upi_id=s.merchant_upi_id, payee_name=s.merchant_name)
    return out


@router.post("/consents/{consent_id}/reject")
async def reject(consent_id: str, request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    if c.status == "payment_submitted":
        raise HTTPException(409, "Your payment is being verified, so this request can't be cancelled now.")
    if c.status in OPEN:
        c.status = "rejected"
        c.decided_at = utcnow()
        await db.execute(update(Payment).where(Payment.consent_id == c.id, Payment.status == "created")
                         .values(status="failed"))
        audit(db, "consent.rejected", user.id, c.id, ip=client_ip(request))
        await db.commit()
    return consent_card(c)


# ---------------------------------------------------------------- settlement (shared)

async def _settle(db: AsyncSession, payment: Payment, from_status: str, payment_id: str | None, ip: str,
                  actor: str | None = None) -> list[Booking]:
    # Atomic state change: only one request can move a payment to "paid", so bookings are created exactly once.
    values = {"status": "paid"}
    if payment_id:
        values["payment_id"] = payment_id
    result = await db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == from_status)
                              .values(**values))
    if result.rowcount != 1:
        await db.rollback()
        return []
    consent = await db.get(ConsentRequest, payment.consent_id)
    consent.status = "paid"
    consent.decided_at = utcnow()
    bookings = create_bookings(db, consent)
    audit(db, "payment.captured", payment.user_id, payment.order_id, amount_paise=payment.amount_paise,
          provider=payment.provider, verified_by=actor, ip=ip)
    audit(db, "booking.created", payment.user_id, consent.id, count=len(bookings))
    await db.commit()
    return bookings


async def _bookings_for(db: AsyncSession, consent_id: str) -> list[dict]:
    rows = (await db.scalars(select(Booking).where(Booking.consent_id == consent_id))).all()
    return [booking_dict(b) for b in rows]


# ---------------------------------------------------------------- UPI (default, free)

class UtrIn(BaseModel):
    order_id: str = Field(max_length=64)
    utr: str = Field(max_length=20)


@router.post("/payments/upi/submit")
async def upi_submit(body: UtrIn, request: Request, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """Traveller says "I've paid" and gives the UPI reference (UTR). Nothing is booked yet."""
    await enforce(f"utr:{user.id}", 10, 300)
    utr = body.utr.strip().replace(" ", "")
    if not gateway.UTR_RE.match(utr):
        raise HTTPException(422, "The UPI reference (UTR) is the 12-digit number shown in your UPI app after paying.")
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id,
                                                    Payment.provider == "upi"))
    if payment is None:
        raise HTTPException(404, "Order not found")
    consent = await db.get(ConsentRequest, payment.consent_id)
    if payment.status != "created" or consent.status != "awaiting_payment":
        raise HTTPException(409, "This payment was already submitted or closed.")
    if aware(consent.hold_expires_at) <= utcnow():
        raise HTTPException(409, "The price hold expired before the payment was submitted. "
                                 "If you already paid, contact support with your UTR.")
    payment.status = "submitted"
    payment.payment_id = utr
    consent.status = "payment_submitted"
    audit(db, "payment.utr_submitted", user.id, payment.order_id, amount_paise=payment.amount_paise, ip=client_ip(request))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "This UTR has already been used for another payment.")
    return consent_card(consent)


# ---------------------------------------------------------------- Razorpay / mock (signature based)

class VerifyIn(BaseModel):
    order_id: str = Field(max_length=64)
    payment_id: str = Field(max_length=64)
    signature: str = Field(max_length=128)


class MockPayIn(BaseModel):
    order_id: str = Field(max_length=64)


@router.post("/payments/mock/pay", include_in_schema=False)
async def mock_pay(body: MockPayIn, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    """Instant test payments — only when PAYMENT_PROVIDER=mock (automated tests)."""
    if get_settings().payment_provider != "mock":
        raise HTTPException(404, "Not found")
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id))
    if payment is None or payment.status != "created":
        raise HTTPException(404, "Order not found or already used")
    consent = await db.get(ConsentRequest, payment.consent_id)
    if aware(consent.hold_expires_at) <= utcnow():
        raise HTTPException(409, "The price hold expired. Search again.")
    return gateway.mock_capture(payment.order_id)


@router.post("/payments/verify")
async def verify(body: VerifyIn, request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    await enforce(f"verify:{user.id}", 20, 60)
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id))
    if payment is None or payment.provider not in ("razorpay", "mock"):
        raise HTTPException(404, "Order not found")
    try:
        valid = gateway.verify_signature(body.order_id, body.payment_id, body.signature)
    except gateway.PaymentError:
        valid = False
    if not valid:
        audit(db, "payment.signature_invalid", user.id, body.order_id, ip=client_ip(request))
        await db.commit()
        raise HTTPException(400, "Payment could not be verified.")
    if payment.status == "created":
        await _settle(db, payment, "created", body.payment_id, client_ip(request))
    return {"status": "paid", "bookings": await _bookings_for(db, payment.consent_id)}


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
            await _settle(db, payment, "created", entity["id"], client_ip(request), actor="razorpay-webhook")
    return {"ok": True}


# ---------------------------------------------------------------- admin: verify UPI payments

def _payment_row(p: Payment, c: ConsentRequest, u: User) -> dict:
    return {"id": p.id, "order_id": p.order_id, "utr": p.payment_id, "amount_inr": p.amount_paise // 100,
            "status": p.status, "created_at": aware(p.created_at).isoformat(), "trip": c.title,
            "items": [i["title"] for i in c.items], "traveller": {"name": u.name, "email": u.email}}


@router.get("/admin/payments")
async def admin_payments(status: str = "submitted", admin: User = Depends(require_admin),
                         db: AsyncSession = Depends(get_db)):
    if status not in ("submitted", "paid", "rejected"):
        raise HTTPException(422, "Unknown status")
    rows = (await db.execute(
        select(Payment, ConsentRequest, User).join(ConsentRequest, Payment.consent_id == ConsentRequest.id)
        .join(User, Payment.user_id == User.id).where(Payment.status == status, Payment.provider == "upi")
        .order_by(Payment.created_at.desc()).limit(100))).all()
    return [_payment_row(p, c, u) for p, c, u in rows]


class RejectIn(BaseModel):
    reason: str = Field(default="Payment not received", max_length=200)


@router.post("/admin/payments/{payment_id}/confirm")
async def admin_confirm(payment_id: str, request: Request, admin: User = Depends(require_admin),
                        db: AsyncSession = Depends(get_db)):
    """Admin checked their UPI/bank app and the money (matching UTR and amount) arrived."""
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.provider != "upi":
        raise HTTPException(404, "Not found")
    bookings = await _settle(db, payment, "submitted", None, client_ip(request), actor=admin.email)
    if not bookings:
        raise HTTPException(409, "This payment is not awaiting verification.")
    return {"status": "paid", "bookings": [booking_dict(b) for b in bookings]}


@router.post("/admin/payments/{payment_id}/reject")
async def admin_reject(payment_id: str, body: RejectIn, request: Request, admin: User = Depends(require_admin),
                       db: AsyncSession = Depends(get_db)):
    payment = await db.get(Payment, payment_id)
    if payment is None or payment.provider != "upi":
        raise HTTPException(404, "Not found")
    result = await db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == "submitted")
                              .values(status="rejected"))
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "This payment is not awaiting verification.")
    consent = await db.get(ConsentRequest, payment.consent_id)
    consent.status = "payment_rejected"
    consent.decided_at = utcnow()
    audit(db, "payment.rejected", payment.user_id, payment.order_id, reason=body.reason, verified_by=admin.email,
          ip=client_ip(request))
    await db.commit()
    return {"status": "rejected"}


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
