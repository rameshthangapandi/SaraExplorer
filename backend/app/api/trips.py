"""Consent, payment, booking and vendor-portal endpoints — the only path by which anything gets booked.

Model B (default "upi" provider): the traveller pays each vendor directly — one UPI payment per vendor — and
each vendor's part of the trip is booked only after THAT vendor confirms the money arrived. Sandbox vendors are
synthetic (demo UPI IDs that can't receive money); an admin confirms on their behalf and can switch a vendor to
its real UPI ID once the details are available."""

import json
import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.booking import BookingError, booking_dict, consent_card, create_bookings, create_consent, ensure_vendors
from app.config import get_settings
from app.db import aware, get_db, utcnow
from app.models import Booking, ConsentRequest, Payment, User, Vendor
from app.payments import gateway
from app.security.deps import get_current_user, is_admin, owned, require_admin
from app.security.rate_limit import client_ip, enforce

log = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["trips"])

OPEN = ("pending", "awaiting_payment")


async def _expire_if_needed(db: AsyncSession, c: ConsentRequest) -> None:
    # Once any payment is submitted the hold no longer expires: the traveller may already have paid a vendor.
    if c.status in OPEN and aware(c.hold_expires_at) <= utcnow():
        c.status = "expired"
        await db.execute(update(Payment).where(Payment.consent_id == c.id, Payment.status == "created")
                         .values(status="failed"))
        audit(db, "consent.expired", c.user_id, c.id)
        await db.commit()


def _vendor_payment(p: Payment, v: Vendor | None) -> dict:
    out = {"order_id": p.order_id, "amount_inr": p.amount_paise // 100, "status": p.status,
           "utr": p.payment_id if p.status != "created" else None,
           "vendor": {"name": v.name, "kind": v.kind, "upi_id": v.upi_id, "demo": v.synthetic} if v else None}
    if v and p.status == "created":
        out["upi_uri"] = gateway.upi_uri(p.order_id, p.amount_paise, v.upi_id, v.name)
    return out


async def _payments_for(db: AsyncSession, consent_id: str) -> list[dict]:
    rows = (await db.execute(select(Payment, Vendor).outerjoin(Vendor, Payment.vendor_id == Vendor.id)
                             .where(Payment.consent_id == consent_id, Payment.status != "failed")
                             .order_by(Payment.amount_paise.desc()))).all()
    return [_vendor_payment(p, v) for p, v in rows]


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
    """Approvals still in progress: awaiting approval / payment / vendor confirmation, or rejected payments."""
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


@router.get("/consents/{consent_id}/payments")
async def consent_payments(consent_id: str, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    return await _payments_for(db, c.id)


@router.post("/consents/{consent_id}/approve")
async def approve(consent_id: str, request: Request, user: User = Depends(get_current_user),
                  db: AsyncSession = Depends(get_db)):
    """User pressed Approve & Pay: create (or reuse) the payments for the server-side amounts."""
    await enforce(f"approve:{user.id}", 10, 60)
    c = await owned(db, ConsentRequest, consent_id, user)
    await _expire_if_needed(db, c)
    if c.status not in OPEN:
        raise HTTPException(409, f"This request is already {c.status.replace('_', ' ')}.")
    if c.total_inr > user.spend_cap_inr:
        raise HTTPException(403, "Total is above your spending limit.")
    s = get_settings()
    base = {"consent_id": c.id, "hold_expires_at": aware(c.hold_expires_at).isoformat(), "description": c.title,
            "name": s.merchant_name, "prefill": {"name": user.name, "email": user.email}, "currency": "INR"}

    if s.payment_provider == "upi":
        existing = (await db.scalars(select(Payment).where(Payment.consent_id == c.id,
                                                           Payment.status == "created"))).all()
        if not existing:
            if any("vendor_key" not in i for i in c.items):
                raise HTTPException(409, "This request is from an older version. Please search again.")
            vendors = await ensure_vendors(db, c.items)
            totals: dict[str, int] = defaultdict(int)
            for item in c.items:
                totals[item["vendor_key"]] += item["price_inr"]
            for key, amount in totals.items():
                order = await gateway.create_order(amount * 100, receipt=c.id)
                db.add(Payment(consent_id=c.id, user_id=user.id, vendor_id=vendors[key].id, provider="upi",
                               order_id=order["order_id"], amount_paise=amount * 100))
        c.status = "awaiting_payment"
        audit(db, "consent.approved", user.id, c.id, total_inr=c.total_inr, ip=client_ip(request))
        await db.commit()
        return {**base, "provider": "upi", "amount_paise": c.total_inr * 100, "payments": await _payments_for(db, c.id)}

    # Single-payment providers (razorpay, or mock in automated tests)
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
    return {**base, "provider": payment.provider, "order_id": payment.order_id, "amount_paise": payment.amount_paise,
            "key_id": s.razorpay_key_id if payment.provider == "razorpay" else None}


@router.post("/consents/{consent_id}/reject")
async def reject(consent_id: str, request: Request, user: User = Depends(get_current_user),
                 db: AsyncSession = Depends(get_db)):
    c = await owned(db, ConsentRequest, consent_id, user)
    if c.status == "payment_submitted":
        raise HTTPException(409, "A payment is being confirmed by the vendor, so this request can't be cancelled now.")
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
    """Mark one payment paid and book the items it pays for. Atomic: bookings are created exactly once."""
    values = {"status": "paid"}
    if payment_id:
        values["payment_id"] = payment_id
    result = await db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == from_status)
                              .values(**values))
    if result.rowcount != 1:
        await db.rollback()
        return []
    consent = await db.get(ConsentRequest, payment.consent_id)
    vendor = await db.get(Vendor, payment.vendor_id) if payment.vendor_id else None
    bookings = create_bookings(db, consent, vendor.key if vendor else None)
    remaining = await db.scalar(select(Payment.id).where(Payment.consent_id == consent.id, Payment.id != payment.id,
                                                         Payment.status.in_(["created", "submitted"])))
    if remaining is None and consent.status != "payment_rejected":
        consent.status = "paid"
        consent.decided_at = utcnow()
    audit(db, "payment.captured", payment.user_id, payment.order_id, amount_paise=payment.amount_paise,
          provider=payment.provider, vendor=vendor.name if vendor else None, verified_by=actor, ip=ip)
    audit(db, "booking.created", payment.user_id, consent.id, count=len(bookings))
    await db.commit()
    return bookings


async def _bookings_for(db: AsyncSession, consent_id: str) -> list[dict]:
    rows = (await db.scalars(select(Booking).where(Booking.consent_id == consent_id))).all()
    return [booking_dict(b) for b in rows]


# ---------------------------------------------------------------- UPI (Model B, free)

class UtrIn(BaseModel):
    order_id: str = Field(max_length=64)
    utr: str = Field(max_length=20)


@router.post("/payments/upi/submit")
async def upi_submit(body: UtrIn, request: Request, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    """Traveller says "I've paid this vendor" and gives the UPI reference (UTR). Nothing is booked yet."""
    await enforce(f"utr:{user.id}", 20, 300)
    utr = body.utr.strip().replace(" ", "")
    if not gateway.UTR_RE.match(utr):
        raise HTTPException(422, "The UPI reference (UTR) is the 12-digit number shown in your UPI app after paying.")
    payment = await db.scalar(select(Payment).where(Payment.order_id == body.order_id, Payment.user_id == user.id,
                                                    Payment.provider == "upi"))
    if payment is None:
        raise HTTPException(404, "Order not found")
    consent = await db.get(ConsentRequest, payment.consent_id)
    if payment.status != "created" or consent.status not in ("awaiting_payment", "payment_submitted"):
        raise HTTPException(409, "This payment was already submitted or closed.")
    if consent.status == "awaiting_payment" and aware(consent.hold_expires_at) <= utcnow():
        raise HTTPException(409, "The price hold expired before the payment was submitted. "
                                 "If you already paid, contact the vendor with your UTR.")
    payment.status = "submitted"
    payment.payment_id = utr
    consent.status = "payment_submitted"
    audit(db, "payment.utr_submitted", user.id, payment.order_id, amount_paise=payment.amount_paise, ip=client_ip(request))
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(409, "This UTR has already been used for another payment.")
    return {"consent": consent_card(consent), "payments": await _payments_for(db, consent.id)}


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


# ---------------------------------------------------------------- vendor portal: confirm money received

def _vendor_scope(user: User):
    """Vendors this user may confirm payments for: their own vendors, plus demo vendors if admin."""
    conds = [Vendor.owner_email == user.email.lower()]
    if is_admin(user):
        conds.append(Vendor.synthetic.is_(True))
    return or_(*conds)


@router.get("/vendor-portal/me")
async def vendor_me(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    owns = await db.scalar(select(Vendor.id).where(Vendor.owner_email == user.email.lower()).limit(1))
    return {"is_vendor": owns is not None, "is_admin": is_admin(user)}


@router.get("/vendor-portal/payments")
async def portal_payments(status: str = "submitted", user: User = Depends(get_current_user),
                          db: AsyncSession = Depends(get_db)):
    if status not in ("submitted", "paid", "rejected"):
        raise HTTPException(422, "Unknown status")
    rows = (await db.execute(
        select(Payment, Vendor, ConsentRequest, User).join(Vendor, Payment.vendor_id == Vendor.id)
        .join(ConsentRequest, Payment.consent_id == ConsentRequest.id).join(User, Payment.user_id == User.id)
        .where(Payment.status == status, _vendor_scope(user)).order_by(Payment.created_at.desc()).limit(100))).all()
    return [{
        "id": p.id, "order_id": p.order_id, "utr": p.payment_id, "amount_inr": p.amount_paise // 100, "status": p.status,
        "created_at": aware(p.created_at).isoformat(), "trip": c.title,
        "items": [i["title"] for i in c.items if i.get("vendor_key") == v.key],
        "vendor": {"name": v.name, "upi_id": v.upi_id, "demo": v.synthetic},
        "traveller": {"name": u.name, "email": u.email},
    } for p, v, c, u in rows]


async def _portal_payment(db: AsyncSession, payment_id: str, user: User) -> Payment:
    row = (await db.execute(select(Payment).join(Vendor, Payment.vendor_id == Vendor.id)
                            .where(Payment.id == payment_id, _vendor_scope(user)))).first()
    if row is None:
        raise HTTPException(404, "Not found")
    return row[0]


@router.post("/vendor-portal/payments/{payment_id}/confirm")
async def portal_confirm(payment_id: str, request: Request, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    """The vendor checked their UPI/bank app and the money (same UTR and amount) arrived: book their items."""
    payment = await _portal_payment(db, payment_id, user)
    bookings = await _settle(db, payment, "submitted", None, client_ip(request), actor=user.email)
    if not bookings:
        raise HTTPException(409, "This payment is not awaiting confirmation.")
    return {"status": "paid", "bookings": [booking_dict(b) for b in bookings]}


class RejectIn(BaseModel):
    reason: str = Field(default="Payment not received", max_length=200)


@router.post("/vendor-portal/payments/{payment_id}/reject")
async def portal_reject(payment_id: str, body: RejectIn, request: Request, user: User = Depends(get_current_user),
                        db: AsyncSession = Depends(get_db)):
    payment = await _portal_payment(db, payment_id, user)
    result = await db.execute(update(Payment).where(Payment.id == payment.id, Payment.status == "submitted")
                              .values(status="rejected"))
    if result.rowcount != 1:
        await db.rollback()
        raise HTTPException(409, "This payment is not awaiting confirmation.")
    consent = await db.get(ConsentRequest, payment.consent_id)
    consent.status = "payment_rejected"
    consent.decided_at = utcnow()
    audit(db, "payment.rejected", payment.user_id, payment.order_id, reason=body.reason, verified_by=user.email,
          ip=client_ip(request))
    await db.commit()
    return {"status": "rejected"}


# ---------------------------------------------------------------- admin: manage vendors

def _vendor_dict(v: Vendor) -> dict:
    return {"id": v.id, "key": v.key, "name": v.name, "kind": v.kind, "upi_id": v.upi_id, "demo": v.synthetic,
            "owner_email": v.owner_email}


@router.get("/admin/vendors")
async def admin_vendors(admin: User = Depends(require_admin), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(Vendor).order_by(Vendor.synthetic, Vendor.kind, Vendor.name))).all()
    return [_vendor_dict(v) for v in rows]


class VendorIn(BaseModel):
    name: str | None = Field(default=None, min_length=2, max_length=120)
    upi_id: str | None = Field(default=None, max_length=120)
    owner_email: EmailStr | None = None
    live: bool | None = None


@router.patch("/admin/vendors/{vendor_id}")
async def admin_update_vendor(vendor_id: str, body: VendorIn, request: Request, admin: User = Depends(require_admin),
                              db: AsyncSession = Depends(get_db)):
    v = await db.get(Vendor, vendor_id)
    if v is None:
        raise HTTPException(404, "Not found")
    if body.name is not None:
        v.name = body.name.strip()
    if body.upi_id is not None:
        upi = body.upi_id.strip()
        if not gateway.UPI_ID_RE.match(upi):
            raise HTTPException(422, "Enter a valid UPI ID, for example homestay@okaxis.")
        v.upi_id = upi
    if body.owner_email is not None:
        v.owner_email = body.owner_email.lower()
    if body.live is not None:
        if body.live and v.upi_id.endswith("@sandbox"):
            raise HTTPException(422, "Add the vendor's real UPI ID before marking it live.")
        v.synthetic = not body.live
    audit(db, "vendor.updated", admin.id, v.id, fields=[k for k, val in body.model_dump().items() if val is not None],
          ip=client_ip(request))
    await db.commit()
    return _vendor_dict(v)


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
