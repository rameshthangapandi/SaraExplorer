import uuid

from tests.conftest import CSRF, PASSWORD, register


def email():
    return f"u{uuid.uuid4().hex[:8]}@example.com"


async def test_register_login_me(client):
    e = email()
    data = await register(client, e)
    assert data["user"]["email"] == e
    assert "sara_rt" in client.cookies
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {data['access_token']}"})
    assert r.status_code == 200


async def test_weak_password_rejected(client):
    r = await client.post("/api/auth/register", json={"name": "A B", "email": email(), "password": "password"})
    assert r.status_code == 422


async def test_wrong_password_and_lockout(client):
    e = email()
    await register(client, e)
    for _ in range(5):
        r = await client.post("/api/auth/login", json={"email": e, "password": "Wrong!Passw0rd"})
        assert r.status_code == 401
    r = await client.post("/api/auth/login", json={"email": e, "password": PASSWORD})
    assert r.status_code == 429  # locked even with the right password


async def test_refresh_requires_csrf_header(client):
    await register(client, email())
    r = await client.post("/api/auth/refresh")
    assert r.status_code == 403


async def test_refresh_rotation_and_reuse_detection(client):
    await register(client, email())
    old_cookie = client.cookies.get("sara_rt")
    r = await client.post("/api/auth/refresh", headers=CSRF)
    assert r.status_code == 200
    new_access = r.json()["access_token"]
    assert client.cookies.get("sara_rt") != old_cookie

    # Replaying the old (rotated) token revokes the whole session family.
    client.cookies.set("sara_rt", old_cookie, path="/api/auth")
    r = await client.post("/api/auth/refresh", headers=CSRF)
    assert r.status_code == 401
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {new_access}"})
    assert r.status_code == 401


async def test_logout_invalidates_access_token(client):
    data = await register(client, email())
    auth = {"Authorization": f"Bearer {data['access_token']}"}
    r = await client.post("/api/auth/logout", headers=CSRF)
    assert r.status_code == 200
    r = await client.get("/api/auth/me", headers=auth)
    assert r.status_code == 401


async def test_tampered_token_rejected(client):
    data = await register(client, email())
    token = data["access_token"][:-3] + "abc"
    r = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert r.status_code == 401


async def test_security_headers(client):
    r = await client.get("/api/health")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-content-type-options"] == "nosniff"
