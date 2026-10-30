import hashlib
import secrets
from datetime import timedelta

import jwt

from app.config import get_settings
from app.db import utcnow

ALGORITHM = "HS256"
AUDIENCE = "sara-explorer-api"


def create_access_token(user_id: str, session_id: str) -> str:
    s = get_settings()
    now = utcnow()
    payload = {
        "sub": user_id,
        "sid": session_id,
        "typ": "access",
        "iss": s.jwt_issuer,
        "aud": AUDIENCE,
        "iat": now,
        "exp": now + timedelta(minutes=s.access_token_minutes),
        "jti": secrets.token_hex(8),
    }
    return jwt.encode(payload, s.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict:
    s = get_settings()
    payload = jwt.decode(
        token, s.jwt_secret, algorithms=[ALGORITHM], audience=AUDIENCE, issuer=s.jwt_issuer,
        options={"require": ["exp", "iat", "sub", "sid", "typ"]},
    )
    if payload.get("typ") != "access":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def new_refresh_token() -> str:
    return secrets.token_urlsafe(48)


def hash_token(token: str) -> str:
    # Refresh tokens are high-entropy random strings, so a fast hash is appropriate (unlike passwords).
    return hashlib.sha256(token.encode()).hexdigest()
