import random
import uuid

import pytest

from app.config import get_settings
from tests.conftest import register
from tests.test_booking import _consent


@pytest.fixture
def upi(monkeypatch):
    monkeypatch.setattr(get_settings(), "payment_provider", "upi")


def utr() -> str:
    return str(random.randint(10**11, 10**12 - 1))


async def _user(client, email=None):
    data = await register(client, email or f"u{uuid.uuid4().hex[:8]}@example.com")
    return data["user"], {"Authorization": f"Bearer {data['access_token']}"}


async def _admin(client):
    # One admin account for the whole test session.
    r = await client.post("/api/auth/login", json={"email": "admin@example.com", "password": "Str0ng!Passw0rd"})
    if r.status_code != 200:
        data = await register(client, "admin@example.com")
        return {"Authorization": f"Bearer {data['access_token']}"}
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def _approved(client):
    user, auth = await _user(client)
    card = await _consent(user["id"])
    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)
    assert r.status_code == 200, r.text
    return user, auth, card, r.json()


async def test_upi_order_has_exact_amount_and_payee(client, upi):
    _, _, card, order = await _approved(client)
    assert order["provider"] == "upi"
    assert order["upi_uri"].startswith("upi://pay?pa=saraexplorer@okaxis")
    assert f"am={card['total_inr']}.00" in order["upi_uri"]


async def test_no_booking_until_admin_confirms(client, upi):
    _, auth, card, order = await _approved(client)
    r = await client.post("/api/payments/upi/submit", json={"order_id": order["order_id"], "utr": utr()}, headers=auth)
    assert r.status_code == 200 and r.json()["status"] == "payment_submitted"
    assert (await client.get("/api/bookings", headers=auth)).json() == []  # NOT booked yet

    # Cannot cancel while the payment is being verified.
    assert (await client.post(f"/api/consents/{card['consent_id']}/reject", headers=auth)).status_code == 409

    admin = await _admin(client)
    pending = (await client.get("/api/admin/payments", headers=admin)).json()
    row = next(p for p in pending if p["order_id"] == order["order_id"])
    r = await client.post(f"/api/admin/payments/{row['id']}/confirm", headers=admin)
    assert r.status_code == 200
    assert len((await client.get("/api/bookings", headers=auth)).json()) == 2
    assert (await client.get(f"/api/consents/{card['consent_id']}", headers=auth)).json()["status"] == "paid"

    # Confirming twice does not create duplicate bookings.
    assert (await client.post(f"/api/admin/payments/{row['id']}/confirm", headers=admin)).status_code == 409


async def test_admin_reject_means_no_booking(client, upi):
    _, auth, card, order = await _approved(client)
    await client.post("/api/payments/upi/submit", json={"order_id": order["order_id"], "utr": utr()}, headers=auth)
    admin = await _admin(client)
    row = next(p for p in (await client.get("/api/admin/payments", headers=admin)).json() if p["order_id"] == order["order_id"])
    r = await client.post(f"/api/admin/payments/{row['id']}/reject", json={"reason": "Not received"}, headers=admin)
    assert r.status_code == 200
    assert (await client.get("/api/bookings", headers=auth)).json() == []
    assert (await client.get(f"/api/consents/{card['consent_id']}", headers=auth)).json()["status"] == "payment_rejected"


async def test_invalid_and_duplicate_utr(client, upi):
    _, auth, _, order = await _approved(client)
    r = await client.post("/api/payments/upi/submit", json={"order_id": order["order_id"], "utr": "12345"}, headers=auth)
    assert r.status_code == 422
    used = utr()
    assert (await client.post("/api/payments/upi/submit", json={"order_id": order["order_id"], "utr": used}, headers=auth)).status_code == 200

    _, auth2, _, order2 = await _approved(client)
    r = await client.post("/api/payments/upi/submit", json={"order_id": order2["order_id"], "utr": used}, headers=auth2)
    assert r.status_code == 409


async def test_non_admin_cannot_verify(client, upi):
    _, auth, _, _ = await _approved(client)
    assert (await client.get("/api/admin/payments", headers=auth)).status_code == 404


async def test_mock_endpoints_disabled_in_upi_mode(client, upi):
    _, auth, _, order = await _approved(client)
    assert (await client.post("/api/payments/mock/pay", json={"order_id": order["order_id"]}, headers=auth)).status_code == 404
    r = await client.post("/api/payments/verify", headers=auth,
                          json={"order_id": order["order_id"], "payment_id": "x", "signature": "y"})
    assert r.status_code == 404


async def test_upi_not_configured(client, upi, monkeypatch):
    monkeypatch.setattr(get_settings(), "merchant_upi_id", "")
    user, auth = await _user(client)
    card = await _consent(user["id"])
    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)
    assert r.status_code == 503


async def test_plan_screen_consent_and_search(client):
    _, auth = await _user(client)
    from datetime import date, timedelta
    d = (date.today() + timedelta(days=20)).isoformat()
    flights = (await client.post("/api/search/flights", json={"origin": "Delhi", "destination": "Goa", "date": d},
                                 headers=auth)).json()
    r = await client.post("/api/consents", json={"option_ids": [flights["options"][0]["id"]], "title": "Goa"}, headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert len((await client.get("/api/consents", headers=auth)).json()) == 1
