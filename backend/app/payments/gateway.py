"""Payment gateways.

Security model (same for both providers):
- The amount always comes from the server-side consent record, never from the client.
- A payment is accepted only with a valid HMAC-SHA256 signature over "order_id|payment_id",
  compared in constant time.
- Card / UPI details never touch this server (Razorpay Checkout handles them; PCI-DSS scope stays with them).

"mock" is a free, built-in test gateway that follows the exact same signature flow, so the app can be
built and demonstrated at zero cost. Switch PAYMENT_PROVIDER=razorpay with test or live keys later.
"""

import hashlib
import hmac
import secrets

import httpx

from app.config import get_settings


class PaymentError(Exception):
    pass


def _sign(secret: str, message: str) -> str:
    return hmac.new(secret.encode(), message.encode(), hashlib.sha256).hexdigest()


def _secret() -> str:
    s = get_settings()
    secret = s.razorpay_key_secret if s.payment_provider == "razorpay" else s.mock_payment_secret
    if not secret or len(secret) < 16:
        raise PaymentError("Payment gateway is not configured")
    return secret


async def create_order(amount_paise: int, receipt: str) -> dict:
    s = get_settings()
    if amount_paise <= 0:
        raise PaymentError("Invalid amount")
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
    _secret()
    return {"provider": "mock", "order_id": f"order_mock_{secrets.token_hex(10)}", "key_id": None}


def verify_signature(order_id: str, payment_id: str, signature: str) -> bool:
    expected = _sign(_secret(), f"{order_id}|{payment_id}")
    return hmac.compare_digest(expected, signature or "")


def mock_capture(order_id: str) -> dict:
    """Simulates the gateway's success callback (only available when PAYMENT_PROVIDER=mock)."""
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
