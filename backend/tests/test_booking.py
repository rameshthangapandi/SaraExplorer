import json
import uuid
from datetime import date, timedelta

from app.agents.tools import ToolContext, propose_booking, search_flights, search_hotels
from tests.conftest import register


async def _user(client):
    data = await register(client, f"b{uuid.uuid4().hex[:8]}@example.com")
    return data["user"]["id"], {"Authorization": f"Bearer {data['access_token']}"}


async def _consent(user_id):
    ctx = ToolContext(user_id=user_id)
    travel = (date.today() + timedelta(days=30)).isoformat()
    flights = await search_flights(ctx, "Delhi", "Goa", travel, 2)
    hotels = await search_hotels(ctx, "Goa", travel, (date.today() + timedelta(days=33)).isoformat(), 2)
    f_id = json.loads(flights.summary)["options"][0]["id"]
    h_id = json.loads(hotels.summary)["options"][0]["id"]
    res = await propose_booking(ctx, [f_id, h_id], "Goa trip")
    assert res.card["type"] == "consent"
    expected = json.loads(flights.summary)["options"][0]["total_inr"] + json.loads(hotels.summary)["options"][0]["total_inr"]
    assert res.card["total_inr"] == expected  # total computed server-side from stored options
    return res.card


async def test_full_consent_payment_flow(client):
    user_id, auth = await _user(client)
    card = await _consent(user_id)

    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)
    assert r.status_code == 200
    order = r.json()
    assert order["amount_paise"] == card["total_inr"] * 100

    pay = (await client.post("/api/payments/mock/pay", json={"order_id": order["order_id"]}, headers=auth)).json()
    r = await client.post("/api/payments/verify", json={"order_id": order["order_id"], **pay}, headers=auth)
    assert r.status_code == 200
    assert len(r.json()["bookings"]) == 2

    # Replaying verification must not create duplicate bookings.
    r = await client.post("/api/payments/verify", json={"order_id": order["order_id"], **pay}, headers=auth)
    assert len(r.json()["bookings"]) == 2
    assert len((await client.get("/api/bookings", headers=auth)).json()) == 2

    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)
    assert r.status_code == 409


async def test_forged_signature_rejected(client):
    user_id, auth = await _user(client)
    card = await _consent(user_id)
    order = (await client.post(f"/api/consents/{card['consent_id']}/approve", headers=auth)).json()
    r = await client.post("/api/payments/verify", headers=auth,
                          json={"order_id": order["order_id"], "payment_id": "pay_fake", "signature": "0" * 64})
    assert r.status_code == 400
    assert (await client.get("/api/bookings", headers=auth)).json() == []


async def test_other_user_cannot_touch_consent(client):
    owner_id, _ = await _user(client)
    card = await _consent(owner_id)
    _, intruder = await _user(client)
    r = await client.post(f"/api/consents/{card['consent_id']}/approve", headers=intruder)
    assert r.status_code == 404


async def test_cannot_book_someone_elses_options(client):
    owner_id, _ = await _user(client)
    ctx = ToolContext(user_id=owner_id)
    flights = await search_flights(ctx, "Mumbai", "Jaipur", (date.today() + timedelta(days=20)).isoformat())
    f_id = json.loads(flights.summary)["options"][0]["id"]
    intruder_id, _ = await _user(client)
    res = await propose_booking(ToolContext(user_id=intruder_id), [f_id])
    assert "error" in json.loads(res.summary)


async def test_spend_cap_enforced(client):
    user_id, auth = await _user(client)
    r = await client.patch("/api/account/settings", json={"spend_cap_inr": 1000}, headers=auth)
    assert r.status_code == 200
    ctx = ToolContext(user_id=user_id)
    flights = await search_flights(ctx, "Delhi", "Goa", (date.today() + timedelta(days=30)).isoformat())
    f_id = json.loads(flights.summary)["options"][0]["id"]
    res = await propose_booking(ctx, [f_id])
    assert "spending limit" in json.loads(res.summary)["error"]
