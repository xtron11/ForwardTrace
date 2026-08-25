import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Not authenticated",
    headers={"WWW-Authenticate": "Bearer"},
)


async def current_user(
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        payload = decode_token(creds.credentials, "access")
        user_id = uuid.UUID(payload["sub"])
    except (jwt.PyJWTError, KeyError, ValueError):
        raise _UNAUTHORIZED from None

    user = await db.get(User, user_id)
    if user is None or not user.is_active:
        raise _UNAUTHORIZED
    # token_version lets a password change invalidate every issued token at once
    if payload.get("tv") != user.token_version:
        raise _UNAUTHORIZED
    return user


CurrentUser = Annotated[User, Depends(current_user)]
Db = Annotated[AsyncSession, Depends(get_db)]


async def admin_user(user: CurrentUser) -> User:
    if user.email.lower() not in settings.admin_email_list:
        raise HTTPException(status_code=403, detail="Admin only")
    return user


AdminUser = Annotated[User, Depends(admin_user)]
