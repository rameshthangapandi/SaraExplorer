from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from pydantic import BaseModel, EmailStr, Field
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.audit import audit
from app.config import get_settings
from app.db import aware, get_db, utcnow
from app.models import AuthSession, User, uid
from app.security.deps import csrf_guard, get_current_user
from app.security.passwords import hash_password, needs_rehash, password_problems, verify_password
from app.security.rate_limit import client_ip, enforce
from app.security.tokens import create_access_token, hash_token, new_refresh_token

router = APIRouter(prefix="/api/auth", tags=["auth"])

COOKIE_NAME = "sara_rt"
COOKIE_PATH = "/api/auth"


class RegisterIn(BaseModel):
    name: str = Field(min_length=2, max_length=100)
    email: EmailStr
    phone: str | None = Field(default=None, pattern=r"^\+?[0-9 ]{10,15}$")
    password: str = Field(max_length=128)
    remember: bool = False


class LoginIn(BaseModel):
    email: EmailStr
    password: str = Field(max_length=128)
    remember: bool = False


class UserOut(BaseModel):
    id: str
    name: str
    email: str
    phone: str | None
    account_type: str
    consent_level: str
    spend_cap_inr: int


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, name=u.name, email=u.email, phone=u.phone, account_type=u.account_type,
                   consent_level=u.consent_level, spend_cap_inr=u.spend_cap_inr)


def _set_cookie(response: Response, token: str, remember: bool) -> None:
    s = get_settings()
    response.set_cookie(
        COOKIE_NAME, token, httponly=True, secure=s.cookie_secure, samesite="strict", path=COOKIE_PATH,
        # No max_age => browser-session cookie: logged in until the browser session ends.
        max_age=s.refresh_token_days * 86400 if remember else None,
    )


def _clear_cookie(response: Response) -> None:
    s = get_settings()
    response.delete_cookie(COOKIE_NAME, path=COOKIE_PATH, secure=s.cookie_secure, httponly=True, samesite="strict")


async def _start_session(db: AsyncSession, user: User, request: Request, response: Response,
                         remember: bool, family_id: str | None = None) -> dict:
    s = get_settings()
    token = new_refresh_token()
    lifetime = timedelta(days=s.refresh_token_days) if remember else timedelta(hours=s.session_hours)
    session = AuthSession(
        id=uid(), user_id=user.id, family_id=family_id or uid(), token_hash=hash_token(token), remember=remember,
        user_agent=(request.headers.get("user-agent") or "")[:300], ip=client_ip(request),
        expires_at=utcnow() + lifetime,
    )
    db.add(session)
    _set_cookie(response, token, remember)
    return {
        "access_token": create_access_token(user.id, session.id),
        "token_type": "bearer",
        "expires_in": s.access_token_minutes * 60,
        "user": user_out(user),
    }


@router.post("/register", status_code=201)
async def register(body: RegisterIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    await enforce(f"register:{client_ip(request)}", 5, 3600)
    email = body.email.lower().strip()
    problems = password_problems(body.password, email)
    if problems:
        raise HTTPException(422, "Password needs " + ", ".join(problems) + ".")
    if await db.scalar(select(User.id).where(User.email == email)):
        raise HTTPException(409, "An account with this email already exists.")
    user = User(id=uid(), name=body.name.strip(), email=email, phone=body.phone,
                password_hash=hash_password(body.password), spend_cap_inr=get_settings().default_spend_cap_inr)
    db.add(user)
    await db.flush()
    result = await _start_session(db, user, request, response, body.remember)
    audit(db, "auth.register", user.id, ip=client_ip(request))
    await db.commit()
    return result


@router.post("/login")
async def login(body: LoginIn, request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    s = get_settings()
    ip = client_ip(request)
    email = body.email.lower().strip()
    await enforce(f"login-ip:{ip}", 20, 300)
    await enforce(f"login-email:{email}", 10, 300)

    user = await db.scalar(select(User).where(User.email == email))
    if user and user.locked_until and aware(user.locked_until) > utcnow():
        audit(db, "auth.login_locked", user.id, ip=ip)
        await db.commit()
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "Too many failed attempts. Please try again in a few minutes.")

    if not verify_password(body.password, user.password_hash if user else None):
        if user:
            user.failed_logins += 1
            if user.failed_logins >= s.max_failed_logins:
                user.locked_until = utcnow() + timedelta(minutes=s.lockout_minutes)
                user.failed_logins = 0
            audit(db, "auth.login_failed", user.id, ip=ip)
            await db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid email or password.")

    user.failed_logins = 0
    user.locked_until = None
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
    result = await _start_session(db, user, request, response, body.remember)
    audit(db, "auth.login", user.id, ip=ip)
    await db.commit()
    return result


@router.post("/refresh", dependencies=[Depends(csrf_guard)])
async def refresh(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    """Exchange the refresh cookie for a new access token, rotating the refresh token."""
    await enforce(f"refresh:{client_ip(request)}", 60, 60)
    token = request.cookies.get(COOKIE_NAME)
    if not token:
        raise HTTPException(401, "No session")
    session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
    if session is None:
        _clear_cookie(response)
        raise HTTPException(401, "Session expired")

    if session.revoked_at is not None:
        # A rotated token was used again: it was likely stolen. Kill the whole token family.
        await db.execute(update(AuthSession).where(AuthSession.family_id == session.family_id,
                                                   AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
        audit(db, "auth.refresh_reuse_detected", session.user_id, ip=client_ip(request))
        await db.commit()
        _clear_cookie(response)
        raise HTTPException(401, "Session expired")

    if aware(session.expires_at) <= utcnow():
        _clear_cookie(response)
        raise HTTPException(401, "Session expired")

    user = await db.get(User, session.user_id)
    session.revoked_at = utcnow()
    # Rotated session keeps the original absolute expiry.
    s = get_settings()
    new_token = new_refresh_token()
    new_session = AuthSession(
        id=uid(), user_id=user.id, family_id=session.family_id, token_hash=hash_token(new_token),
        remember=session.remember, user_agent=session.user_agent, ip=client_ip(request),
        created_at=session.created_at, expires_at=session.expires_at,
    )
    db.add(new_session)
    _set_cookie(response, new_token, session.remember)
    await db.commit()
    return {
        "access_token": create_access_token(user.id, new_session.id),
        "token_type": "bearer",
        "expires_in": s.access_token_minutes * 60,
        "user": user_out(user),
    }


@router.post("/logout", dependencies=[Depends(csrf_guard)])
async def logout(request: Request, response: Response, db: AsyncSession = Depends(get_db)):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        session = await db.scalar(select(AuthSession).where(AuthSession.token_hash == hash_token(token)))
        if session:
            await db.execute(update(AuthSession).where(AuthSession.family_id == session.family_id,
                                                       AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
            audit(db, "auth.logout", session.user_id, ip=client_ip(request))
            await db.commit()
    _clear_cookie(response)
    return {"ok": True}


@router.post("/logout-all")
async def logout_all(request: Request, response: Response, user: User = Depends(get_current_user),
                     db: AsyncSession = Depends(get_db)):
    await db.execute(update(AuthSession).where(AuthSession.user_id == user.id,
                                               AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    audit(db, "auth.logout_all", user.id, ip=client_ip(request))
    await db.commit()
    _clear_cookie(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)):
    return user_out(user)


@router.get("/sessions")
async def sessions(request: Request, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    rows = (await db.scalars(select(AuthSession).where(AuthSession.user_id == user.id,
                                                       AuthSession.revoked_at.is_(None))
                             .order_by(AuthSession.created_at.desc()))).all()
    current = getattr(request.state, "session_id", None)
    return [
        {"id": r.id, "user_agent": r.user_agent, "ip": r.ip, "created_at": aware(r.created_at),
         "expires_at": aware(r.expires_at), "remember": r.remember, "current": r.id == current}
        for r in rows if aware(r.expires_at) > utcnow()
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(session_id: str, request: Request, user: User = Depends(get_current_user),
                         db: AsyncSession = Depends(get_db)):
    session = await db.scalar(select(AuthSession).where(AuthSession.id == session_id,
                                                        AuthSession.user_id == user.id))
    if session is None:
        raise HTTPException(404, "Not found")
    await db.execute(update(AuthSession).where(AuthSession.family_id == session.family_id,
                                               AuthSession.revoked_at.is_(None)).values(revoked_at=utcnow()))
    audit(db, "auth.session_revoked", user.id, session_id, ip=client_ip(request))
    await db.commit()
    return {"ok": True}
