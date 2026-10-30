"""Model B: the traveller pays each vendor directly; each vendor's items are booked only after that vendor confirms."""

import random
import uuid
from datetime import date, timedelta

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


async def _login_or_register(client, email):
    r = await client.post("/api/auth/login", json={"email": email, "password": "Str0ng!Passw0rd"})
    if r.status_code == 200:
        return {"Authorization": f"Bearer {r.json()['access_token']}"}
    data = await register(client, email)
    return {"Authorization": f"Bearer {data['access_token']}"}


async def _approved(client):
    """Consent with a flight + hotel → two vendors → two payments."""
    user, auth = await _user(client)
    card = await _consent(user["id"])
    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)
    assert r.status_code == 200, r.text
    return user, auth, card, r.json()


async def _submit_all(client, auth, order):
    for p in order["payments"]:
        r = await client.post("/api/payments/upi/submit", json={"order_id": p["order_id"], "utr": utr()}, headers=auth)
        assert r.status_code == 200, r.text


async def test_one_payment_per_vendor_with_demo_qr(client, upi):
    _, _, card, order = await _approved(client)
    pays = order["payments"]
    assert len(pays) == 2  # airline + hotel are different vendors
    assert sum(p["amount_inr"] for p in pays) == card["total_inr"]
    for p in pays:
        assert p["vendor"]["demo"] is True
        assert p["vendor"]["upi_id"].endswith("@sandbox")  # not a real UPI handle: can't receive money
        assert p["upi_uri"].startswith(f"upi://pay?pa={p['vendor']['upi_id']}")
        assert f"am={p['amount_inr']}.00" in p["upi_uri"]


async def test_each_vendor_confirms_its_own_part(client, upi):
    _, auth, card, order = await _approved(client)
    await _submit_all(client, auth, order)
    assert (await client.get("/api/bookings", headers=auth)).json() == []  # nothing booked yet
    assert (await client.post(f"/api/consents/{card['consent_id']}/reject", headers=auth)).status_code == 409

    admin = await _login_or_register(client, "admin@example.com")  # confirms on behalf of demo vendors
    mine = {p["order_id"] for p in order["payments"]}
    pending = [p for p in (await client.get("/api/vendor-portal/payments", headers=admin)).json() if p["order_id"] in mine]
    assert len(pending) == 2

    r = await client.post(f"/api/vendor-portal/payments/{pending[0]['id']}/confirm", headers=admin)
    assert r.status_code == 200
    assert len((await client.get("/api/bookings", headers=auth)).json()) == 1  # only that vendor's item
    assert (await client.get(f"/api/consents/{card['consent_id']}", headers=auth)).json()["status"] == "payment_submitted"

    await client.post(f"/api/vendor-portal/payments/{pending[1]['id']}/confirm", headers=admin)
    assert len((await client.get("/api/bookings", headers=auth)).json()) == 2
    assert (await client.get(f"/api/consents/{card['consent_id']}", headers=auth)).json()["status"] == "paid"
    # Confirming twice never duplicates bookings.
    assert (await client.post(f"/api/vendor-portal/payments/{pending[0]['id']}/confirm", headers=admin)).status_code == 409


async def test_vendor_reject_means_no_booking(client, upi):
    _, auth, card, order = await _approved(client)
    await _submit_all(client, auth, order)
    admin = await _login_or_register(client, "admin@example.com")
    row = next(p for p in (await client.get("/api/vendor-portal/payments", headers=admin)).json()
               if p["order_id"] == order["payments"][0]["order_id"])
    assert (await client.post(f"/api/vendor-portal/payments/{row['id']}/reject", json={}, headers=admin)).status_code == 200
    assert (await client.get("/api/bookings", headers=auth)).json() == []
    assert (await client.get(f"/api/consents/{card['consent_id']}", headers=auth)).json()["status"] == "payment_rejected"


async def test_real_vendor_owner_confirms_and_others_cannot(client, upi):
    _, auth, card, order = await _approved(client)
    admin = await _login_or_register(client, "admin@example.com")
    vendors = (await client.get("/api/admin/vendors", headers=admin)).json()
    hotel_name = order["payments"][0]["vendor"]["name"] if order["payments"][0]["vendor"]["kind"] == "hotel" else order["payments"][1]["vendor"]["name"]
    hotel = next(v for v in vendors if v["name"] == hotel_name)

    # Can't go live with a demo UPI ID; can after adding a real one.
    assert (await client.patch(f"/api/admin/vendors/{hotel['id']}", json={"live": True}, headers=admin)).status_code == 422
    assert (await client.patch(f"/api/admin/vendors/{hotel['id']}", json={"upi_id": "not a upi"}, headers=admin)).status_code == 422
    owner_email = f"owner{uuid.uuid4().hex[:6]}@example.com"
    r = await client.patch(f"/api/admin/vendors/{hotel['id']}",
                           json={"upi_id": "realhotel@okaxis", "owner_email": owner_email, "live": True}, headers=admin)
    assert r.status_code == 200 and r.json()["demo"] is False

    # A new trip now shows the vendor's real UPI ID.
    _, auth2, _, order2 = await _approved(client)
    live = [p for p in order2["payments"] if p["vendor"]["name"] == hotel_name]  # same dates -> same sandbox hotel
    assert live and live[0]["vendor"]["upi_id"] == "realhotel@okaxis" and live[0]["vendor"]["demo"] is False

    # Owner sees and confirms only their own payments; a random user sees nothing.
    pay = next(p for p in order["payments"] if p["vendor"]["name"] == hotel_name)
    await client.post("/api/payments/upi/submit", json={"order_id": pay["order_id"], "utr": utr()}, headers=auth)
    owner = await _login_or_register(client, owner_email)
    assert (await client.get("/api/vendor-portal/me", headers=owner)).json()["is_vendor"] is True
    rows = (await client.get("/api/vendor-portal/payments", headers=owner)).json()
    assert [r["order_id"] for r in rows] == [pay["order_id"]]
    _, stranger = await _user(client)
    assert (await client.get("/api/vendor-portal/payments", headers=stranger)).json() == []
    assert (await client.post(f"/api/vendor-portal/payments/{rows[0]['id']}/confirm", headers=stranger)).status_code == 404
    assert (await client.post(f"/api/vendor-portal/payments/{rows[0]['id']}/confirm", headers=owner)).status_code == 200
    # Admin can no longer confirm for a live vendor (only the vendor can).
    assert all(p["order_id"] != pay["order_id"] for p in (await client.get("/api/vendor-portal/payments?status=paid", headers=admin)).json())


async def test_invalid_and_duplicate_utr(client, upi):
    _, auth, _, order = await _approved(client)
    oid = order["payments"][0]["order_id"]
    assert (await client.post("/api/payments/upi/submit", json={"order_id": oid, "utr": "12345"}, headers=auth)).status_code == 422
    used = utr()
    assert (await client.post("/api/payments/upi/submit", json={"order_id": oid, "utr": used}, headers=auth)).status_code == 200
    _, auth2, _, order2 = await _approved(client)
    r = await client.post("/api/payments/upi/submit", json={"order_id": order2["payments"][0]["order_id"], "utr": used}, headers=auth2)
    assert r.status_code == 409


async def test_non_admin_cannot_manage_vendors(client, upi):
    _, auth, _, _ = await _approved(client)
    assert (await client.get("/api/admin/vendors", headers=auth)).status_code == 404
    assert (await client.get("/api/vendor-portal/payments", headers=auth)).json() == []


async def test_mock_endpoints_disabled_in_upi_mode(client, upi):
    _, auth, _, order = await _approved(client)
    oid = order["payments"][0]["order_id"]
    assert (await client.post("/api/payments/mock/pay", json={"order_id": oid}, headers=auth)).status_code == 404
    r = await client.post("/api/payments/verify", headers=auth, json={"order_id": oid, "payment_id": "x", "signature": "y"})
    assert r.status_code == 404


async def test_plan_screen_consent_and_search(client):
    _, auth = await _user(client)
    d = (date.today() + timedelta(days=20)).isoformat()
    flights = (await client.post("/api/search/flights", json={"origin": "Delhi", "destination": "Goa", "date": d},
                                 headers=auth)).json()
    r = await client.post("/api/consents", json={"option_ids": [flights["options"][0]["id"]], "title": "Goa"}, headers=auth)
    assert r.status_code == 201 and r.json()["status"] == "pending"
    assert r.json()["items"][0]["vendor"] == flights["options"][0]["airline"]
    assert len((await client.get("/api/consents", headers=auth)).json()) == 1
