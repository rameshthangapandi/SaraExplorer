"""Server-side booking logic shared by the Ask Sara tools and the REST API.

The LLM can only *propose* a booking by referencing stored option IDs. Prices, totals and holds are
computed here from server data, and a booking is created only after a verified payment on the
user's authenticated consent request.
"""

import secrets
import string
from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.config import get_settings
from app.db import aware, utcnow
from app.models import Booking, ConsentRequest, SearchOption, User

OPTION_TTL = timedelta(minutes=45)
PREFIX = {"flight": "FL", "train": "TR", "hotel": "HT"}
_ALNUM = string.ascii_uppercase + string.digits


class BookingError(Exception):
    pass


def _code(n: int, alphabet: str = _ALNUM) -> str:
    return "".join(secrets.choice(alphabet) for _ in range(n))


def option_title(kind: str, d: dict) -> str:
    if kind == "flight":
        return f"{d['airline']} {d['flight_no']} {d['from']}→{d['to']} {d['depart'][:16].replace('T', ' ')}"
    if kind == "train":
        return f"{d['train_name']} ({d['train_no']}) {d['class']} {d['depart'][:16].replace('T', ' ')}"
    return f"{d['hotel']} · {d['nights']} night(s) from {d['check_in']}"


async def store_options(db: AsyncSession, user_id: str, kind: str, items: list[dict]) -> list[dict]:
    expires = utcnow() + OPTION_TTL
    out = []
    for item in items:
        oid = f"{PREFIX[kind]}-{_code(6)}"
        db.add(SearchOption(id=oid, user_id=user_id, kind=kind, title=option_title(kind, item), data=item,
                            price_inr=int(item["price_total"]), expires_at=expires))
        out.append({"id": oid, **item})
    await db.commit()
    return out


def consent_card(c: ConsentRequest) -> dict:
    return {
        "type": "consent", "consent_id": c.id, "title": c.title, "status": c.status, "total_inr": c.total_inr,
        "hold_expires_at": aware(c.hold_expires_at).isoformat(),
        "items": [{"kind": i["kind"], "title": i["title"], "price_inr": i["price_inr"], "terms": i["terms"]}
                  for i in c.items],
    }


def _terms(kind: str, d: dict) -> str:
    if kind == "flight":
        return "Refundable (cancellation fee applies)" if d.get("refundable") else "Non-refundable fare"
    if kind == "train":
        status = d.get("availability", "")
        if status.startswith("WL"):
            return f"{status} — about {int(d.get('confirm_chance', 0) * 100)}% chance to confirm; auto-refund if not confirmed"
        return f"{status}; IRCTC cancellation rules apply"
    if d.get("free_cancellation_until"):
        return f"Free cancellation until {d['free_cancellation_until']}"
    return "Non-refundable rate"


async def create_consent(db: AsyncSession, user: User, option_ids: list[str], title: str) -> ConsentRequest:
    ids = list(dict.fromkeys(i.strip().upper() for i in option_ids if i and i.strip()))
    if not 1 <= len(ids) <= 6:
        raise BookingError("Choose between 1 and 6 options to book.")
    rows = (await db.scalars(select(SearchOption).where(SearchOption.id.in_(ids),
                                                        SearchOption.user_id == user.id))).all()
    found = {r.id: r for r in rows}
    missing = [i for i in ids if i not in found]
    if missing:
        raise BookingError(f"Unknown option(s): {', '.join(missing)}. Search again to get fresh options.")
    now = utcnow()
    expired = [r.id for r in rows if aware(r.expires_at) <= now]
    if expired:
        raise BookingError(f"Option(s) {', '.join(expired)} expired. Search again for current prices.")

    items = [{"option_id": r.id, "kind": r.kind, "title": r.title, "price_inr": r.price_inr,
              "terms": _terms(r.kind, r.data), "data": r.data} for r in (found[i] for i in ids)]
    total = sum(i["price_inr"] for i in items)
    if total > user.spend_cap_inr:
        raise BookingError(f"Total ₹{total:,} is above your spending limit of ₹{user.spend_cap_inr:,}. "
                           f"You can change the limit in Account settings.")
    consent = ConsentRequest(user_id=user.id, title=(title or "Your trip")[:200], items=items, total_inr=total,
                             hold_expires_at=now + timedelta(minutes=get_settings().consent_hold_minutes))
    db.add(consent)
    await db.flush()
    audit(db, "consent.created", user.id, consent.id, total_inr=total, options=ids)
    await db.commit()
    return consent


def _reference(kind: str) -> str:
    if kind == "train":
        return _code(10, string.digits)
    if kind == "flight":
        return _code(6, string.ascii_uppercase)
    return f"HTL-{_code(8)}"


def create_bookings(db: AsyncSession, consent: ConsentRequest) -> list[Booking]:
    bookings = []
    for item in consent.items:
        status = "confirmed"
        if item["kind"] == "train" and str(item["data"].get("availability", "")).startswith("WL"):
            status = "waitlisted"
        b = Booking(user_id=consent.user_id, consent_id=consent.id, kind=item["kind"], title=item["title"],
                    details=item["data"], amount_inr=item["price_inr"], reference=_reference(item["kind"]), status=status)
        db.add(b)
        bookings.append(b)
    return bookings


def booking_dict(b: Booking) -> dict:
    return {"id": b.id, "kind": b.kind, "title": b.title, "amount_inr": b.amount_inr, "reference": b.reference,
            "status": b.status, "details": b.details, "created_at": aware(b.created_at).isoformat(),
            "cancelled_at": aware(b.cancelled_at).isoformat() if b.cancelled_at else None}
