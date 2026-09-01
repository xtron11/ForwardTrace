from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from .config import settings

# Pool sizing is a Postgres concern. SQLite - which the test suite runs on - uses
# NullPool, and newer SQLAlchemy raises rather than ignoring pool arguments it cannot
# apply. Passing them only where they mean something keeps both paths working.
_engine_options: dict[str, Any] = {"echo": False}
if not settings.database_url.startswith("sqlite"):
    _engine_options.update(pool_pre_ping=True, pool_size=10, max_overflow=5)

engine = create_async_engine(settings.database_url, **_engine_options)

SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


async def get_db() -> AsyncIterator[AsyncSession]:
    """Request-scoped session. Background tasks must open their own via SessionLocal."""
    async with SessionLocal() as session:
        yield session
