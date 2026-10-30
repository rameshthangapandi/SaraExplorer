"""Payment gateways.

Providers
- "upi" (default, free): the traveller pays the exact amount to the merchant's UPI ID by QR / UPI app and
  submits the 12-digit UTR. The booking is created ONLY after an admin confirms the money was received.
  (Without a paid gateway nothing can detect incoming UPI money automatically, so a human verifies it.)
- "razorpay": automatic confirmation via Razorpay Checkout + HMAC-signed callbacks / webhooks.
- "mock": instant test payments, for automated tests only. Never enable it for real users.

In every provider the amount comes from the server-side consent record, never from the client.
"""

import hashlib
import hmac
import re
import secrets
from urllib.parse import quote

import httpx

from app.config import get_settings

UPI_ID_RE = re.compile(r"^[A-Za-z0-9.\-_]{2,256}@[A-Za-z]{2,64}$")
UTR_RE = re.compile(r"^\d{12}$")


class PaymentError(Exception):
    pass


def _sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _secret() -> str:
    s = get_settings()
    secret = s.razorpay_key_secret if s.payment_provider == "razorpay" else s.mock_payment_secret
    if s.payment_provider not in ("razorpay", "mock") or not secret or len(secret) < 16:
        raise PaymentError("Signature payments are not enabled")
    return secret


def upi_ready() -> bool:
    return bool(UPI_ID_RE.match(get_settings().merchant_upi_id or ""))


async def create_order(amount_paise: int, receipt: str) -> dict:
    s = get_settings()
    if amount_paise <= 0:
        raise PaymentError("Invalid amount")
    if s.payment_provider == "upi":
        if not upi_ready():
            raise PaymentError("UPI payments are not set up yet. The admin must set MERCHANT_UPI_ID.")
        return {"provider": "upi", "order_id": f"SE{secrets.token_hex(6).upper()}", "key_id": None}
    if s.payment_provider == "razorpay":
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.post(
                    "https://api.razorpay.com/v1/orders",
                    auth=(s.razorpay_key_id, s.razorpay_key_secret),
                    json={"amount": amount_paise, "currency": "INR", "receipt": receipt[:40]},
                )
                r.raise_for_status()
                data = r.json()
        except httpx.HTTPError as exc:
            raise PaymentError("Could not create payment order") from exc
        if data.get("amount") != amount_paise:
            raise PaymentError("Gateway amount mismatch")
        return {"provider": "razorpay", "order_id": data["id"], "key_id": s.razorpay_key_id}
    if s.payment_provider == "mock":
        _secret()
        return {"provider": "mock", "order_id": f"order_mock_{secrets.token_hex(10)}", "key_id": None}
    raise PaymentError("Unknown payment provider")


def upi_uri(order_id: str, amount_paise: int) -> str:
    """Standard UPI deep link (NPCI 'upi://pay'): opens any UPI app with payee and amount pre-filled."""
    s = get_settings()
    params = {
        "pa": s.merchant_upi_id,
        "pn": s.merchant_name,
        "am": f"{amount_paise / 100:.2f}",
        "cu": "INR",
        "tn": f"Sara Explorer {order_id}",
        "tr": order_id,
    }
    return "upi://pay?" + "&".join(f"{k}={quote(v, safe='@.')}" for k, v in params.items())


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    expected = _sign(_secret(), f"{order_id}|{payment_id}")
    return hmac.compare_digest(expected, signature or "")


def mock_capture(order_id: str) -> dict:
    if get_settings().payment_provider != "mock":
        raise PaymentError("Mock payments are disabled")
    payment_id = f"pay_mock_{secrets.token_hex(10)}"
    return {"payment_id": payment_id, "signature": _sign(_secret(), f"{order_id}|{payment_id}")}


def verify_webhook(body: bytes, signature: str) -> bool:
    secret = get_settings().razorpay_webhook_secret
    if not secret:
        return False
    expected = hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, signature or "")
