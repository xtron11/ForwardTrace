"""Fixes from the review of the whole v2 branch (ticket F1): logic numbers as settings,
the day's conversation created twice at once, a first conversation carried over to a new
day, and memory skipping messages that went down the safety path."""

import re
from datetime import date, datetime, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import Settings, settings
from app.db import SessionLocal
from app.models import Fact, User
from app.services import prompts
from conftest import register

pytestmark = pytest.mark.asyncio

# Start values from the brief (and spec.md section 1.11) for numbers that used to be
# module constants.
LOGIC_NUMBERS = {
    "level_facts_shown": 3,
    "monthly_max_pairs": 3,
    "plateau_max_pairs": 3,
    "first_default_reminder_hour": 20,
    "first_evening_hour": 21,
    "goal_title_max_chars": 120,
    "finish_option_max_chars": 60,
    "finish_options_max": 4,
    "safety_reply_max_words": 80,
}


async def test_logic_numbers_are_settings_with_lines_in_env_example():
    example = (Path(__file__).resolve().parents[1] / ".env.example").read_text("utf-8")
    defaults = Settings(_env_file=None, app_env="test")
    for name, value in LOGIC_NUMBERS.items():
        assert getattr(defaults, name, None) == value, name
        assert re.search(rf"^{name.upper()}={value}$", example, re.M), name


async def test_safety_prompt_word_limit_comes_from_settings(monkeypatch):
    monkeypatch.setattr(settings, "safety_reply_max_words", 55)
    text = prompts.safety_system("en")
    assert "At most 55 words" in text
    assert "80 words" not in text


async def test_progress_shows_as_many_level_facts_as_configured(client, monkeypatch):
    auth = await register(client, email="levels@example.com")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == "levels@example.com"))).scalar_one()
        for day in (1, 5, 9, 13):
            db.add(Fact(user_id=user.id, local_date=date(2026, 9, day), type="level",
                        text=f"level {day}", quote=f"level {day}"))
        await db.commit()
    monkeypatch.setattr(settings, "level_facts_shown", 2)
    body = (await client.get("/api/progress", headers=auth)).json()
    assert [f["quote"] for f in body["level_facts"]] == ["level 13", "level 9"]


# ------------------------------------------------------------------ the day created twice


async def _existing_day(user_id, day) -> str:
    """The row the other request inserted first."""
    from app.models import Conversation

    async with SessionLocal() as db:
        row = Conversation(user_id=user_id, local_date=day, kind="daily", started_by="user")
        db.add(row)
        await db.commit()
        return str(row.id)


async def test_today_created_by_a_parallel_request_is_returned_not_a_500(client, monkeypatch):
    from app.services import conversation
    from app.time_utils import local_today

    auth = await register(client, email="race@example.com")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == "race@example.com"))).scalar_one()
        user.first_conversation_done = True
        await db.commit()
        uid, tz = user.id, user.timezone
    other = await _existing_day(uid, local_today(tz))

    # The parallel request inserts between this request's lookup and its insert.
    real_day, calls = conversation._day, []

    async def late_lookup(db, user_id, day):
        calls.append(day)
        return None if len(calls) == 1 else await real_day(db, user_id, day)

    monkeypatch.setattr(conversation, "_day", late_lookup)
    r = await client.get("/api/conversations/today", headers=auth)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == other


async def test_outreach_into_a_day_created_at_the_same_moment(client, monkeypatch):
    from app.models import Message as MessageRow
    from app.models import Outreach
    from app.services import outreach
    from app.services.llm import LLMResult

    now = datetime(2026, 10, 20, 20, 5, tzinfo=timezone.utc)
    await register(client, email="race2@example.com", timezone="UTC")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == "race2@example.com"))).scalar_one()
        user.first_conversation_done = True
        user.reminder_hour = now.hour
        await db.commit()
        uid = user.id

    async def fake_push(db, user_id, payload):
        return 1

    async def fake_model(system, user, schema):
        return LLMResult(data={"text": "How did the jump go?", "quick_replies": []}, model="mock", elapsed_ms=1)

    monkeypatch.setattr(outreach.push, "send_to_user", fake_push)
    monkeypatch.setattr(outreach, "complete_json", fake_model)
    other = await _existing_day(uid, now.date())

    real_find, calls = outreach._find_day, []

    async def late_lookup(db, user_id, day):
        calls.append(day)
        return None if len(calls) == 1 else await real_find(db, user_id, day)

    monkeypatch.setattr(outreach, "_find_day", late_lookup)
    assert await outreach.run_once(now) == 1
    async with SessionLocal() as db:
        row = (await db.execute(select(Outreach).where(Outreach.user_id == uid))).scalar_one()
        assert str(row.conversation_id) == other
        message = await db.get(MessageRow, row.message_id)
        assert str(message.conversation_id) == other


# ------------------------------------------------------------------ memory and safety


async def test_memory_skips_messages_that_went_down_the_safety_path(client, monkeypatch):
    from app.models import Conversation
    from app.models import Message as MessageRow
    from app.services import memory
    from app.services.llm import LLMResult

    await register(client, email="safe@example.com")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == "safe@example.com"))).scalar_one()
        conversation = Conversation(user_id=user.id, local_date=date(2026, 10, 12), counts_for_limit=True)
        db.add(conversation)
        await db.flush()
        said = {}
        for i, (text, level) in enumerate([
            ("Today I finally found the memory leak in the renderer.", 0),
            ("I do not see the point of practising anything any more.", 2),
            ("I do not want to wake up tomorrow at all.", 3),
            ("Some days the scales still feel slow.", 1),
        ]):
            row = MessageRow(
                conversation_id=conversation.id, user_id=user.id, role="user", source="text",
                content_raw=text, content=[{"type": "text", "text": text}], safety_level=level,
                created_at=datetime(2026, 10, 12, 12, i, tzinfo=timezone.utc),
            )
            db.add(row)
            await db.flush()
            said[level] = (row.id, text)
        await db.commit()
        conversation_id, user_id = conversation.id, user.id

    prompts_seen: list[str] = []

    async def fake(system, user, schema):
        if "theme" in (schema.get("properties") or {}):
            return LLMResult(data={"theme": "x"}, model="mock", elapsed_ms=1)
        prompts_seen.append(user)
        facts = [
            {"message_id": str(said[0][0]), "type": "achievement", "text": "a", "quote": "found the memory leak in the renderer"},
            {"message_id": str(said[2][0]), "type": "struggle", "text": "b", "quote": "I do not see the point of practising anything"},
            {"message_id": str(said[3][0]), "type": "struggle", "text": "c", "quote": "I do not want to wake up tomorrow"},
            {"message_id": str(said[1][0]), "type": "struggle", "text": "d", "quote": "the scales still feel slow"},
        ]
        return LLMResult(data={"facts": facts, "threads": {"open": [], "mention": [], "close": []}, "day_summary": "A day"}, model="mock", elapsed_ms=1)

    monkeypatch.setattr(memory, "complete_json", fake)
    await memory.extract_memory(conversation_id)

    [prompt] = prompts_seen
    assert said[2][1] not in prompt and said[3][1] not in prompt
    async with SessionLocal() as db:
        quotes = sorted(f.quote for f in (await db.execute(select(Fact).where(Fact.user_id == user_id))).scalars())
    assert quotes == ["found the memory leak in the renderer", "the scales still feel slow"]
