import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.db import aware, get_db, utcnow
from app.models import AuthSession, User
from app.security.tokens import decode_access_token

_bearer = HTTPBearer(auto_error=False)

CSRF_HEADER = "x-requested-with"
CSRF_VALUE = "sara-explorer"


async def get_current_user(
    request: Request,
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: AsyncSession = Depends(get_db),
) -> User:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Not authenticated",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None or creds.scheme.lower() != "bearer":
        raise unauthorized
    try:
        payload = decode_access_token(creds.credentials)
    except jwt.PyJWTError:
        raise unauthorized

    # The session must still be live: logout / "log out everywhere" takes effect immediately.
    session = await db.get(AuthSession, payload["sid"])
    if session is None or session.revoked_at is not None or aware(session.expires_at) <= utcnow():
        raise unauthorized
    user = await db.get(User, payload["sub"])
    if user is None or session.user_id != user.id:
        raise unauthorized
    request.state.session_id = session.id
    return user


def is_admin(user: User) -> bool:
    return user.email.lower() in get_settings().admin_email_list


async def require_admin(user: User = Depends(get_current_user)) -> User:
    if not is_admin(user):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return user


def csrf_guard(request: Request) -> None:
    """For endpoints authenticated by the refresh cookie: require a custom header (cannot be sent
    cross-site without a CORS preflight) and, when present, an allowed Origin."""
    if request.headers.get(CSRF_HEADER) != CSRF_VALUE:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Missing CSRF header")
    origin = request.headers.get("origin")
    if origin and origin not in get_settings().cors_origin_list:
        host_origin = f"{request.url.scheme}://{request.url.netloc}"
        if origin != host_origin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Origin not allowed")


async def owned(db: AsyncSession, model, obj_id: str, user: User):
    """Fetch a row that must belong to the user. Returns 404 (not 403) to avoid leaking existence."""
    obj = await db.scalar(select(model).where(model.id == obj_id, model.user_id == user.id))
    if obj is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Not found")
    return obj
