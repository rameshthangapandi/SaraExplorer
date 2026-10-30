import os
import tempfile

_db = os.path.join(tempfile.mkdtemp(), "test.db")
os.environ.update({
    "DATABASE_URL": f"sqlite+aiosqlite:///{_db}",
    "JWT_SECRET": "test-secret-" + "x" * 40,
    "MOCK_PAYMENT_SECRET": "mock-secret-" + "y" * 30,
    "PAYMENT_PROVIDER": "mock",
    "COOKIE_SECURE": "false",
    "REDIS_URL": "",
    "GROQ_API_KEY": "",
    "CORS_ORIGINS": "http://testserver",
    "ADMIN_EMAILS": "admin@example.com",
    "MERCHANT_UPI_ID": "saraexplorer@okaxis",
})

import pytest  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import init_db  # noqa: E402
from app.main import app  # noqa: E402
from app.security.rate_limit import limiter  # noqa: E402

CSRF = {"X-Requested-With": "sara-explorer"}
PASSWORD = "Str0ng!Passw0rd"


@pytest.fixture(autouse=True)
async def _setup():
    await init_db()
    limiter.reset()
    yield


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://testserver") as c:
        yield c


async def register(client, email="asha@example.com", remember=False):
    r = await client.post("/api/auth/register", json={"name": "Asha", "email": email, "password": PASSWORD,
                                                       "remember": remember})
    assert r.status_code == 201, r.text
    return r.json()
