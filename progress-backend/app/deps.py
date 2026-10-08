import uuid
from typing import Annotated

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from .config import settings
from .db import get_db
from .models import User
from .security import decode_token

bearer = HTTPBearer(auto_error=False)

# The admin panel is server-rendered HTML, so the browser carries the token in a
# cookie rather than an Authorization header. Same token, same checks - only the
# delivery differs.
ADMIN_COOKIE = "ft_admin"

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
    # A deleted account is locked until it is restored from the letter.
    if user is None or not user.is_active or user.deleted_at is not None:
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


async def admin_from_cookie(request: Request, db: Db) -> User | None:
    """Returns the admin for a browser session, or None. Never raises: the panel shows
    a login form instead of an error page."""
    token = request.cookies.get(ADMIN_COOKIE)
    if not token:
        return None
    try:
        payload = decode_token(token, "access")
        user = await db.get(User, uuid.UUID(payload["sub"]))
    except (jwt.PyJWTError, KeyError, ValueError):
        return None

    if user is None or not user.is_active or payload.get("tv") != user.token_version:
        return None
    if user.deleted_at is not None:
        return None
    if user.email.lower() not in settings.admin_email_list:
        return None
    return user


AdminUser = Annotated[User, Depends(admin_user)]
