from datetime import datetime, timezone

import jwt
from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from ..config import settings
from ..deps import CurrentUser, Db
from ..models import User
from ..schemas import (
    ChangePasswordIn,
    LoginIn,
    RefreshIn,
    RegisterIn,
    TokenPair,
    UserOut,
    UserUpdate,
)
from ..security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _issue(user: User) -> TokenPair:
    return TokenPair(
        access_token=create_access_token(user.id, user.token_version),
        refresh_token=create_refresh_token(user.id, user.token_version),
        expires_in=settings.access_token_ttl_min * 60,
    )


@router.post("/register", response_model=TokenPair, status_code=status.HTTP_201_CREATED)
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
    return _issue(user)


@router.post("/login", response_model=TokenPair)
async def login(payload: LoginIn, db: Db) -> TokenPair:
    user = (
        await db.execute(select(User).where(User.email == payload.email.lower()))
    ).scalar_one_or_none()

    # Same message and roughly the same work either way: don't leak which emails exist.
    if user is None or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Incorrect email or password")
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
