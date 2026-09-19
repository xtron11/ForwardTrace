"""Test environment, fixed before the app is imported.

Settings are read once at import time, so this has to run first - conftest.py is
loaded by pytest before any test module.

Nothing here uses setdefault: a DATABASE_URL exported in the shell would otherwise
point drop_all at a real database, and a provider key would send real requests.
"""

import os

# Ignore progress-backend/.env: its keys and limits are the developer's, not the suite's.
os.environ["APP_ENV_FILE"] = ""

os.environ["JWT_SECRET"] = "test-secret-not-used-anywhere-real"
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_suite.db"
os.environ["ADMIN_EMAILS"] = "admin@example.com"
# The suite creates tables directly from the models; no migration run is involved.
os.environ["AUTO_CREATE_TABLES"] = "true"

# Anything that would reach a paid or external service stays off.
for name in (
    "OPENAI_API_KEY",
    "DEEPGRAM_API_KEY",
    "RESEND_API_KEY",
    "VAPID_PUBLIC_KEY",
    "VAPID_PRIVATE_KEY",
    "STT_LANGUAGE",
):
    os.environ.pop(name, None)

from sqlalchemy import event  # noqa: E402

from app.db import engine  # noqa: E402


@event.listens_for(engine.sync_engine, "connect")
def _fast_sqlite(dbapi_connection, _record) -> None:
    """Every test rebuilds the schema and every request commits, and on Windows each of
    those waits for the disk. A throwaway test database has nothing worth syncing, and
    with durability on the suite takes minutes instead of seconds."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.close()
