"""Test environment, fixed before the app is imported.

Settings are read once at import time, so this has to run first - conftest.py is
loaded by pytest before any test module.

Nothing here uses setdefault: a DATABASE_URL exported in the shell would otherwise
point drop_all at a real database, and a provider key would send real requests.
"""

import os

# Ignore progress-backend/.env: its keys and limits are the developer's, not the suite's.
os.environ["APP_ENV_FILE"] = ""
# The only environment allowed to run with the default JWT_SECRET (see config.py).
os.environ["APP_ENV"] = "test"

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
    "EMBEDDING_MODEL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_BOT_USERNAME",
    "TELEGRAM_WEBHOOK_SECRET",
):
    os.environ.pop(name, None)

import json  # noqa: E402

import pytest_asyncio  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import event  # noqa: E402

from app import models  # noqa: E402,F401  (registers every table on Base.metadata)
from app.db import Base, engine  # noqa: E402


@event.listens_for(engine.sync_engine, "connect")
def _fast_sqlite(dbapi_connection, _record) -> None:
    """Every test rebuilds the schema and every request commits, and on Windows each of
    those waits for the disk. A throwaway test database has nothing worth syncing, and
    with durability on the suite takes minutes instead of seconds."""
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA synchronous=OFF")
    cursor.execute("PRAGMA journal_mode=MEMORY")
    cursor.close()


# ------------------------------------------------------------------ shared fixtures
# test_app.py keeps its own fresh_db and client (same names, so they win inside that
# module). Every tests/test_v2_*.py file gets these. A v2 module that imports a
# provider by name (complete_json, stream_chat, embed, transcribe) adds its fake here.


# The model's default reply in the day's conversation, as streamed pieces.
CHAT_REPLY = [
    "What helped ",
    "you find it?",
    "\n<<<META>>>\n",
    '{"quick_replies": ["The profiler", "Search"], "intent": "normal"}',
]
TRANSCRIPT = "Today I finally found the memory leak in the renderer."
TRANSCRIPT_WORDS = [
    {"w": "Today", "start": 0.0, "end": 0.3},
    {"w": "I", "start": 0.3, "end": 0.4},
    {"w": "finally", "start": 0.4, "end": 0.8},
]


async def fake_stream_chat(messages, *, model=None, reasoning_effort=None):
    for piece in CHAT_REPLY:
        yield piece


# What the memory extraction model answers unless a test says otherwise: nothing found.
MEMORY_RESULT = {
    "facts": [],
    "threads": {"open": [], "mention": [], "close": []},
    "day_summary": "",
}
PAIR_THEME = "A theme"


async def fake_memory_json(system, user, schema):
    """memory.complete_json: the extraction answer, or a pair's theme."""
    import copy

    from app.services.llm import LLMResult

    if "theme" in (schema.get("properties") or {}):
        data = {"theme": PAIR_THEME}
    else:
        data = copy.deepcopy(MEMORY_RESULT)
    return LLMResult(data=data, model="mock", elapsed_ms=1)


async def fake_embed(texts):
    return [[1.0, 0.0, 0.0] for _ in texts]


async def fake_transcribe(path, mime=None, locale=None):
    from app.services.stt import STTResult

    return STTResult(TRANSCRIPT, 3.5, "en", 120, "mock", words=list(TRANSCRIPT_WORDS))


@pytest_asyncio.fixture(scope="function", autouse=True)
async def fresh_db(monkeypatch):
    from app.services import conversation, memory, ratelimit

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    ratelimit.reset()
    # Providers imported by name into v2 modules.
    monkeypatch.setattr(conversation, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(conversation, "transcribe", fake_transcribe)
    monkeypatch.setattr(memory, "complete_json", fake_memory_json)
    monkeypatch.setattr(memory, "embed", fake_embed)
    yield


@pytest_asyncio.fixture
async def client():
    from app.main import app

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def register(
    client, email="person@example.com", locale="en", timezone="America/Los_Angeles"
) -> dict:
    """A verified account (no RESEND_API_KEY in tests) and its Authorization header."""
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "supersecret1", "timezone": timezone, "locale": locale},
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def parse_sse(text: str) -> list[tuple[str, dict]]:
    """`event: x` / `data: {...}` blocks separated by a blank line -> [(event, data)]."""
    events: list[tuple[str, dict]] = []
    for block in text.replace("\r\n", "\n").split("\n\n"):
        name, data = "message", []
        for line in block.split("\n"):
            if line.startswith("event:"):
                name = line[len("event:"):].strip()
            elif line.startswith("data:"):
                data.append(line[len("data:"):].strip())
        if data:
            events.append((name, json.loads("\n".join(data))))
    return events
