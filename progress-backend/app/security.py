import uuid
from datetime import datetime, timedelta, timezone

import bcrypt
import jwt

from .config import settings

# bcrypt silently truncates at 72 bytes; reject longer input instead of pretending.
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=12)).decode()


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode(), password_hash.encode())
    except ValueError:
        return False


def _make_token(user_id: uuid.UUID, token_version: int, kind: str, ttl: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "tv": token_version,
        "typ": kind,
        "iat": int(now.timestamp()),
        "exp": int((now + ttl).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: uuid.UUID, token_version: int) -> str:
    return _make_token(
        user_id, token_version, "access", timedelta(minutes=settings.access_token_ttl_min)
    )


def create_refresh_token(user_id: uuid.UUID, token_version: int) -> str:
    return _make_token(
        user_id, token_version, "refresh", timedelta(days=settings.refresh_token_ttl_days)
    )


def decode_token(token: str, expected_type: str) -> dict:
    """Raises jwt.PyJWTError on anything invalid."""
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("typ") != expected_type:
        raise jwt.InvalidTokenError(f"expected a {expected_type} token")
    return payload


def create_verification_token(user_id: uuid.UUID, email: str) -> str:
    """Signed rather than stored: nothing to clean up, and changing the address
    invalidates the link on its own because the address is inside it."""
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "email": email,
            "type": "verify",
            "iat": now,
            "exp": now + timedelta(hours=settings.email_verification_ttl_hours),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_verification_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "verify":
        raise jwt.InvalidTokenError("wrong token type")
    return payload


def create_restore_token(user_id: uuid.UUID, deleted_at: datetime) -> str:
    """The link in the "your account was deleted" letter.

    Bound to the moment of deletion, so a link from an earlier deletion stops working
    once the account is restored and deleted again. It expires when the data does.
    """
    deleted_at = deleted_at.replace(tzinfo=deleted_at.tzinfo or timezone.utc)
    return jwt.encode(
        {
            "sub": str(user_id),
            "del": int(deleted_at.timestamp()),
            "type": "restore",
            "iat": datetime.now(timezone.utc),
            "exp": deleted_at + timedelta(days=settings.account_restore_days),
        },
        settings.jwt_secret,
        algorithm=settings.jwt_algorithm,
    )


def decode_restore_token(token: str) -> dict:
    payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    if payload.get("type") != "restore":
        raise jwt.InvalidTokenError("wrong token type")
    return payload
