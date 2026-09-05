import uuid
from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import User
from ..schemas import (
    RegisteredOut,
    ResendIn,
    VerifyIn,
    ChangePasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
    UserUpdate,
)
from ..services import mail
from ..security import (
    create_verification_token,
    decode_verification_token,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Anyone can ask for a letter, so there has to be a gap between them.
RESEND_INTERVAL_SECONDS = 60


async def _send_verification(db, user: User) -> bool:
    now = datetime.now(timezone.utc)
    if user.verification_sent_at is not None:
        since = (now - user.verification_sent_at.replace(tzinfo=timezone.utc)).total_seconds()
        if since < RESEND_INTERVAL_SECONDS:
            return False

    token = create_verification_token(user.id, user.email)
    sent = await mail.send_verification(
        user.email, f"{settings.app_url}/verify?token={token}", user.locale or "en"
    )
    if sent:
        user.verification_sent_at = now
        await db.commit()
    return sent


def _issue(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=create_refresh_token(user.id, user.token_version),
        expires_in=settings.access_token_ttl_min * 60,
    )


@router.post(
    "/register",
    response_model=TokenPair | RegisteredOut,
    status_code=status.HTTP_201_CREATED,
)
async def register(payload: RegisterIn, db: Db) -> TokenPair:
    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        display_name=payload.display_name,
        timezone=payload.timezone,
        locale=payload.locale,
    )
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="That email is already registered") from None
    await db.refresh(user)

    if not mail.configured():
        # Nothing can be sent, so locking people out of a product with no way to let
        # them back in would be the worst of both worlds. Local development and the
        # test suite take this path.
        user.email_verified = True
        await db.commit()
        await db.refresh(user)
        return _issue(user)

    if not await _send_verification(db, user):
        # The letter did not go out - a refused sender domain, a provider outage - and
        # the account is now unreachable: no session, and no link on the way. Undo it,
        # so the address stays free and they can try again rather than being told it
        # is already registered.
        await db.delete(user)
        await db.commit()
        raise HTTPException(
            status_code=503,
            detail="Could not send the confirmation email. Try again in a few minutes.",
        )

    # Deliberately no tokens: the account exists but is not usable yet, and handing
    # out a session here would let someone straight past the thing being checked.
    return RegisteredOut(verification_required=True, email=user.email)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginIn, db: Db) -> TokenPair:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    # Same message and roughly the same work either way: don't leak which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
    if mail.configured() and not user.email_verified:
        raise HTTPException(
            status_code=403,
            detail="Confirm your email address first. Check the letter we sent.",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="This account is disabled")

    user.last_seen_at = datetime.now(timezone.utc)
    await db.commit()
    return _issue(user)


@router.post("/refresh", response_model=TokenPair)
async def refresh(payload: RefreshIn, db: Db) -> TokenPair:
    try:
        claims = decode_token(payload.refresh_token, "refresh")
    except jwt.PyJWTError:
        raise HTTPException(status_code=401, detail="Invalid refresh token") from None

    user = await db.get(User, claims["sub"])
    if user is None or not user.is_active or claims.get("tv") != user.token_version:
        raise HTTPException(status_code=401, detail="Invalid refresh token")
    return _issue(user)


@router.post("/change-password", response_model=TokenPair)
async def change_password(payload: ChangePasswordIn, user: CurrentUser, db: Db) -> TokenPair:
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    user.password_hash = hash_password(payload.new_password)
    user.token_version += 1  # invalidates every token issued before this moment
    await db.commit()
    await db.refresh(user)
    return _issue(user)


@router.post("/logout-everywhere", status_code=204)
async def logout_everywhere(user: CurrentUser, db: Db) -> None:
    user.token_version += 1
    await db.commit()


@router.post("/verify")
async def verify_email(payload: VerifyIn, db: Db) -> dict:
    """Confirm an address. Deliberately unauthenticated: the link is opened in whatever
    browser the letter was read in, which is often not the one holding the session."""
    try:
        claims = decode_verification_token(payload.token)
        user = await db.get(User, uuid.UUID(claims["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError) as exc:
        raise HTTPException(status_code=400, detail="This link is not valid") from exc

    if user is None or user.email != claims.get("email"):
        # The address is inside the token, so changing it invalidates old links.
        raise HTTPException(status_code=400, detail="This link is not valid")

    if not user.email_verified:
        user.email_verified = True
        await db.commit()

    return {"verified": True, "email": user.email}


@router.post("/resend-verification", status_code=202)
async def resend_verification(payload: ResendIn, db: Db) -> dict:
    """Send the letter again.

    Unauthenticated, because there is no session to authenticate with until the address
    is confirmed. The response is identical whether or not the address exists: telling
    a stranger which addresses are registered here is not information worth giving away.
    """
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    if user is not None and not user.email_verified and mail.configured():
        await _send_verification(db, user)

    return {"sent": True}


@router.get("/me", response_model=UserOut)
async def me(user: CurrentUser) -> User:
    return user


@router.patch("/me", response_model=UserOut)
async def update_me(payload: UserUpdate, user: CurrentUser, db: Db) -> User:
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(user, field, value)
    await db.commit()
    await db.refresh(user)
    return user
