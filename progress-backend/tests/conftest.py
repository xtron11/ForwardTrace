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


# The model's default reply in the day's conversation, as streamed pieces. No quick
# replies: the model offers them only with a question that has explicit options (v2.1).
CHAT_REPLY = [
    "What helped ",
    "you find it?",
    "\n<<<META>>>\n",
    '{"quick_replies": [], "intent": "normal"}',
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


# First-conversation model answers by step; tests replace entries with monkeypatch.setitem.
FIRST_RESULTS = {
    "skill": {"on_topic": True, "title": "Game development"},
    "motivation": {
        "on_topic": True,
        "quote": "",
        "finish_options": ["Level B2", "IELTS 6.5", "Pass the interview", "Read without a dictionary"],
    },
    "baseline": {"on_topic": True, "pairs": [], "level_quote": "", "just_started": False},
}
FIRST_CALLS: list[tuple[str, str]] = []  # (step, the person's text sent to the model)


async def fake_first_json(system, user, schema):
    """first_conversation.complete_json: the answer for the step the schema belongs to."""
    import copy

    from app.services.llm import LLMResult

    props = schema.get("properties") or {}
    step = "baseline" if "pairs" in props else "motivation" if "finish_options" in props else "skill"
    FIRST_CALLS.append((step, user))
    return LLMResult(data=copy.deepcopy(FIRST_RESULTS[step]), model="mock", elapsed_ms=1)


# The AI-writes-first model's answer unless a test says otherwise (monkeypatch.setitem).
OUTREACH_RESULT = {"text": "What went better today than a week ago?", "quick_replies": ["A lot", "Nothing yet"]}


async def fake_outreach_json(system, user, schema):
    """outreach.complete_json: the short question."""
    import copy

    from app.services.llm import LLMResult

    return LLMResult(data=copy.deepcopy(OUTREACH_RESULT), model="mock", elapsed_ms=1)


# Every Telegram message the code tried to send: (chat_id, text, button_url).
TELEGRAM_SENT: list[tuple[int, str, str | None]] = []


async def fake_send_message(chat_id, text, button_url=None, *, button_text=None):
    TELEGRAM_SENT.append((chat_id, text, button_url))
    return True


# The monthly summary model's answer unless a test says otherwise (monkeypatch.setitem),
# and the system prompt of every call.
MONTHLY_RESULT = {
    "intro": "A month of steady work on the renderer.",
    "open_struggle": "Collisions still bother you.",
    "next_step": "Try one small test scene this week.",
}
MONTHLY_CALLS: list[str] = []  # the system prompt of every call


async def fake_monthly_json(system, user, schema):
    """progress.complete_json: the three fields of the monthly summary."""
    import copy

    from app.services.llm import LLMResult

    MONTHLY_CALLS.append(system)
    return LLMResult(data=copy.deepcopy(MONTHLY_RESULT), model="mock", elapsed_ms=1)


# The safety check's answer unless a test says otherwise (monkeypatch.setitem), and
# every call it received: (model, the person's text).
SAFETY_RESULT = {"level": 0, "reason": ""}
SAFETY_CALLS: list[tuple[str | None, str]] = []


async def fake_safety_json(system, user, schema, *, model, reasoning_effort=None):
    """safety.complete_json_with: the level for any message."""
    from app.services.llm import LLMResult

    SAFETY_CALLS.append((model, user))
    return LLMResult(data=dict(SAFETY_RESULT), model=model or "mock", elapsed_ms=1)


async def fake_transcribe(path, mime=None, locale=None):
    from app.services.stt import STTResult

    return STTResult(TRANSCRIPT, 3.5, "en", 120, "mock", words=list(TRANSCRIPT_WORDS))


@pytest_asyncio.fixture(scope="function", autouse=True)
async def fresh_db(monkeypatch):
    from app.services import (
        conversation,
        first_conversation,
        memory,
        outreach,
        progress,
        ratelimit,
        safety,
        telegram,
    )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    ratelimit.reset()
    # Providers imported by name into v2 modules.
    monkeypatch.setattr(conversation, "stream_chat", fake_stream_chat)
    monkeypatch.setattr(conversation, "transcribe", fake_transcribe)
    monkeypatch.setattr(memory, "complete_json", fake_memory_json)
    monkeypatch.setattr(memory, "embed", fake_embed)
    monkeypatch.setattr(first_conversation, "complete_json", fake_first_json)
    monkeypatch.setattr(outreach, "complete_json", fake_outreach_json)
    monkeypatch.setattr(progress, "complete_json", fake_monthly_json)
    monkeypatch.setattr(safety, "complete_json_with", fake_safety_json)
    # Nothing ever reaches the Bot API from the suite.
    monkeypatch.setattr(telegram, "send_message", fake_send_message)
    FIRST_CALLS.clear()
    TELEGRAM_SENT.clear()
    SAFETY_CALLS.clear()
    MONTHLY_CALLS.clear()
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
