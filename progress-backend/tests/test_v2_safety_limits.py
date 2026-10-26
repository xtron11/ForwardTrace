"""Stage 7: safety levels 0-3, "I think I'm standing still", the weekly limit and the
fake door, the export, and the reference dialogs.

The safety model is a fake (conftest patches `safety.complete_json_with`; tests set
`SAFETY_RESULT`), and so is the chat model (`conversation.stream_chat`).
"""

import importlib.util
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Conversation, Event, Fact, Goal, Message, Pair, Thread, User
from app.services import conversation, limits, prompts, safety, texts
from app.services.llm import LLMError
from app.time_utils import local_today

from conftest import FIRST_CALLS, SAFETY_CALLS, SAFETY_RESULT, parse_sse, register

TZ = "America/Los_Angeles"
MESSAGES = "/api/conversations/today/messages"
PLATEAU = "/api/conversations/today/plateau"

@pytest.fixture(autouse=True)
def audio_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "audio_dir", str(tmp_path / "audio"))
    return tmp_path / "audio"


# ------------------------------------------------------------------ helpers


async def _me(client, auth) -> uuid.UUID:
    r = await client.get("/api/auth/me", headers=auth)
    return uuid.UUID(r.json()["id"])


async def _person(client, email="person@example.com", locale="en", onboarded=True, tz=TZ, **fields):
    auth = await register(client, email=email, locale=locale, timezone=tz)
    user_id = await _me(client, auth)
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        user.first_conversation_done = onboarded
        for key, value in fields.items():
            setattr(user, key, value)
        await db.commit()
    return auth, user_id


async def _send(client, auth, text="I found the leak with the profiler today."):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def _text(events) -> str:
    return "".join(d["text"] for e, d in events if e == "delta")


def _today(tz=TZ) -> date:
    return local_today(tz)


def _recorder(pieces=("Here is a calm answer?", "\n<<<META>>>\n", '{"quick_replies": [], "intent": "normal"}')):
    """A fake stream_chat that keeps the messages it was given."""
    calls: list[list[dict]] = []

    async def fake(messages, *, model=None, reasoning_effort=None):
        calls.append(messages)
        for piece in pieces:
            yield piece

    return fake, calls


def _never_called():
    async def fake(messages, *, model=None, reasoning_effort=None):
        raise AssertionError("the chat model must not be called")
        yield  # pragma: no cover

    return fake


async def _rows(model, *where):
    async with SessionLocal() as db:
        return list((await db.execute(select(model).where(*where))).scalars())


async def _events(kind: str):
    return await _rows(Event, Event.type == kind)


async def _fact(user_id, quote, day, *, kind="struggle", thread_id=None) -> Fact:
    async with SessionLocal() as db:
        fact = Fact(user_id=user_id, local_date=day, type=kind, text=quote, quote=quote, thread_id=thread_id)
        db.add(fact)
        await db.commit()
        return fact


async def _pair(user_id, then: Fact, now: Fact) -> Pair:
    async with SessionLocal() as db:
        pair = Pair(user_id=user_id, then_fact_id=then.id, now_fact_id=now.id, theme="t", source="similarity")
        db.add(pair)
        await db.commit()
        return pair


async def _day(user_id, day, *, counts=True, user_level=None, summary=None):
    """A stored conversation; with `user_level`, one message from the person at that level."""
    async with SessionLocal() as db:
        conv = Conversation(user_id=user_id, local_date=day, counts_for_limit=counts, summary=summary)
        db.add(conv)
        await db.flush()
        if user_level is not None:
            db.add(
                Message(
                    conversation_id=conv.id,
                    user_id=user_id,
                    role="user",
                    content_raw="tired",
                    content=[{"type": "text", "text": "tired"}],
                    safety_level=user_level,
                    created_at=datetime.combine(day, datetime.min.time(), tzinfo=timezone.utc),
                )
            )
        await db.commit()
        return conv


async def _goal(user_id, why="I want to ship my own game", finish="Release on Steam"):
    async with SessionLocal() as db:
        db.add(Goal(user_id=user_id, title="Game dev", why_text=why, finish_line=finish))
        await db.commit()


async def _end_trial(user_id, days_ago=30):
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        user.created_at = datetime.now(timezone.utc) - timedelta(days=days_ago)
        await db.commit()


def _system(calls) -> str:
    return calls[-1][0]["content"]


def _all_text(messages) -> str:
    return "\n".join(m["content"] for m in messages)


# ------------------------------------------------------------------ the check


@pytest.mark.asyncio
class TestSafetyCheck:
    async def test_uses_the_safety_model_and_returns_its_level(self, monkeypatch):
        monkeypatch.setattr(settings, "safety_model", "safety-model-x")
        monkeypatch.setitem(SAFETY_RESULT, "level", 2)
        result = await safety.safety_check("nothing makes sense", "en")
        assert (result.level, result.failed) == (2, False)
        assert len(SAFETY_CALLS) == 1
        assert SAFETY_CALLS[0][0] == "safety-model-x"
        assert "nothing makes sense" in SAFETY_CALLS[0][1]

    async def test_model_error_means_level_zero_and_an_event(self, client, monkeypatch):
        async def broken(system, user, schema, *, model, reasoning_effort=None):
            raise LLMError("down")

        monkeypatch.setattr(safety, "complete_json_with", broken)
        result = await safety.safety_check("hello", "en")
        assert (result.level, result.failed) == (0, True)

        auth, _ = await _person(client)
        events = await _send(client, auth)
        assert events[-1][0] == "done"
        assert len(await _events("safety_check_failed")) == 1

    async def test_every_message_is_checked(self, client):
        auth, _ = await _person(client)
        await _send(client, auth, "first")
        await _send(client, auth, "second")
        assert len(SAFETY_CALLS) == 2
        assert "first" in SAFETY_CALLS[0][1] and "second" in SAFETY_CALLS[1][1]


# ------------------------------------------------------------------ level 1


@pytest.mark.asyncio
class TestLevelOne:
    async def test_gentler_note_in_the_context(self, client, monkeypatch):
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        monkeypatch.setitem(SAFETY_RESULT, "level", 1)
        auth, _ = await _person(client)
        await _send(client, auth, "so tired today")
        assert prompts.CHAT_SOFT.strip() in _system(calls)

    async def test_help_suggested_on_five_of_fourteen_days_then_not_again(self, client, monkeypatch):
        monkeypatch.setitem(SAFETY_RESULT, "level", 1)
        auth, user_id = await _person(client)
        today = _today()
        for back in (2, 5, 9, 13):  # 4 earlier days inside the 14-day window, today is the 5th
            await _day(user_id, today - timedelta(days=back), user_level=1)
        events = await _send(client, auth, "tired again")
        assert texts.t("en", "safety.suggest_help") in _text(events)
        assert len(await _events("safety_suggest_help")) == 1
        stored = (await _rows(Message, Message.user_id == user_id, Message.role == "assistant"))[-1]
        assert texts.t("en", "safety.suggest_help") in "".join(
            s.get("text", "") for s in stored.content
        )

        again = await _send(client, auth, "still tired")
        assert texts.t("en", "safety.suggest_help") not in _text(again)
        assert len(await _events("safety_suggest_help")) == 1

    async def test_no_help_on_four_days(self, client, monkeypatch):
        monkeypatch.setitem(SAFETY_RESULT, "level", 1)
        auth, user_id = await _person(client)
        today = _today()
        for back in (2, 5, 20):  # the 20-day-old one is outside the window
            await _day(user_id, today - timedelta(days=back), user_level=1)
        events = await _send(client, auth, "tired")
        assert texts.t("en", "safety.suggest_help") not in _text(events)
        assert await _events("safety_suggest_help") == []

    async def test_level_zero_days_do_not_count(self, client, monkeypatch):
        auth, user_id = await _person(client)
        today = _today()
        for back in (1, 2, 3, 4, 5):
            await _day(user_id, today - timedelta(days=back), user_level=0)
        monkeypatch.setitem(SAFETY_RESULT, "level", 1)
        events = await _send(client, auth, "tired")
        assert texts.t("en", "safety.suggest_help") not in _text(events)


# ------------------------------------------------------------------ level 2


@pytest.mark.asyncio
class TestLevelTwo:
    async def test_safety_prompt_without_memory_or_progress(self, client, monkeypatch):
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        auth, user_id = await _person(client)
        await _goal(user_id, why="I want to ship my own game", finish="Release on Steam")
        fact = await _fact(user_id, "the character fell through the floor", _today() - timedelta(days=10))
        async with SessionLocal() as db:
            db.add(Thread(user_id=user_id, title="Physics bugs", opened_on=_today() - timedelta(days=10)))
            await db.commit()
        await _day(user_id, _today() - timedelta(days=1), summary="Talked about shaders")

        monkeypatch.setitem(SAFETY_RESULT, "level", 2)
        events = await _send(client, auth, "I see no point in anything anymore")
        assert events[-1][0] == "done"

        sent = calls[-1]
        assert sent[0]["role"] == "system"
        assert sent[0]["content"] == prompts.safety_system("en")
        everything = _all_text(sent)
        for leaked in (
            "ship my own game",
            "Release on Steam",
            "fell through the floor",
            str(fact.id),
            "Physics bugs",
            "shaders",
        ):
            assert leaked not in everything
        assert "I see no point in anything anymore" in everything

        conv = (await _rows(Conversation, Conversation.user_id == user_id, Conversation.local_date == _today()))[0]
        assert conv.safety_level == 2
        flags = await _events("safety_flag")
        assert len(flags) == 1 and flags[0].payload["level"] == 2

    async def test_placeholders_are_never_rendered(self, client, monkeypatch):
        auth, user_id = await _person(client)
        fact = await _fact(user_id, "old words", _today() - timedelta(days=10))
        fake, _ = _recorder((f"Look {{{{quote:{fact.id}}}}} here?", "<<<META>>>{}"))
        monkeypatch.setattr(conversation, "stream_chat", fake)
        monkeypatch.setitem(SAFETY_RESULT, "level", 2)
        events = await _send(client, auth, "hopeless")
        assert not [e for e, _ in events if e == "quote"]


# ------------------------------------------------------------------ level 3


@pytest.mark.asyncio
class TestLevelThree:
    async def test_template_without_the_model(self, client, monkeypatch):
        monkeypatch.setattr(conversation, "stream_chat", _never_called())
        monkeypatch.setattr(settings, "safety_resources", {})
        monkeypatch.setitem(SAFETY_RESULT, "level", 3)
        auth, user_id = await _person(client, country="KZ")
        events = await _send(client, auth, "I want to end it")
        assert events[-1][0] == "done"
        assert _text(events) == texts.t("en", "safety.level3_no_resources")

        stored = await _rows(Message, Message.user_id == user_id)
        person = [m for m in stored if m.role == "user"][0]
        answer = [m for m in stored if m.role == "assistant"][0]
        assert person.safety_level == 3  # outreach pauses on this (services/outreach.py)
        assert answer.model_name is None
        conv = (await _rows(Conversation, Conversation.user_id == user_id))[0]
        assert conv.safety_level == 3
        assert (await _events("safety_flag"))[0].payload["level"] == 3

    async def test_contacts_for_the_country(self, client, monkeypatch):
        monkeypatch.setattr(conversation, "stream_chat", _never_called())
        monkeypatch.setattr(
            settings,
            "safety_resources",
            {"KZ": [{"name": "Example line", "contact": "example-contact"}], "default": [{"name": "Fallback", "contact": "fb"}]},
        )
        monkeypatch.setitem(SAFETY_RESULT, "level", 3)
        auth, _ = await _person(client, country="KZ")
        text = _text(await _send(client, auth, "I want to end it"))
        assert text.startswith(texts.t("en", "safety.level3"))
        assert "Example line" in text and "example-contact" in text
        assert "Fallback" not in text

    async def test_default_contacts_when_the_country_has_none(self, monkeypatch):
        monkeypatch.setattr(
            settings, "safety_resources", {"default": [{"name": "Fallback", "contact": "fb"}]}
        )
        assert safety.resources_for("FR") == [{"name": "Fallback", "contact": "fb"}]
        assert safety.resources_for(None) == [{"name": "Fallback", "contact": "fb"}]
        monkeypatch.setattr(settings, "safety_resources", {"KZ": [{"name": "", "contact": ""}]})
        assert safety.resources_for("KZ") == []  # empty placeholders are not contacts

    async def test_no_resources_are_shipped_and_the_template_promises_nothing(self):
        from app.config import Settings

        assert Settings.model_fields["safety_resources"].default == {}
        for locale in ("ru", "en"):
            for key in ("safety.level3", "safety.level3_no_resources", "safety.level3_contact_someone"):
                value = texts.t(locale, key).lower()
                assert not re.search(r"\d{3}", value)  # no phone number of any kind
                for word in ("конфиденц", "никто не узна", "сообщ", "confidential", "no one will", "notif", "we will tell"):
                    assert word not in value, (locale, key, word)
        ru = " ".join(texts.t("ru", k) for k in ("safety.level3", "safety.level3_no_resources", "safety.suggest_help"))
        assert not re.search(r"\b(ты|тебе|тебя|твой|твоя)\b", ru, re.I)

    async def test_first_conversation_does_not_advance(self, client, monkeypatch):
        monkeypatch.setattr(conversation, "stream_chat", _never_called())
        monkeypatch.setitem(SAFETY_RESULT, "level", 3)
        auth, user_id = await _person(client, onboarded=False)
        await client.get("/api/conversations/today", headers=auth)
        events = await _send(client, auth, "I want to end it")
        assert _text(events) == texts.t("en", "safety.level3_no_resources")
        assert FIRST_CALLS == []
        conv = (await _rows(Conversation, Conversation.user_id == user_id))[0]
        assert conv.state["step"] == "skill"


# ------------------------------------------------------------------ plateau


async def _evidence(user_id, pairs=3, closed=1):
    """Pairs with gaps of 10, 20, 30... days and closed threads; returns the facts."""
    today = _today()
    facts = []
    for i in range(pairs):
        gap = 10 * (i + 1)
        then = await _fact(user_id, f"then-{gap}", today - timedelta(days=gap + 1))
        now = await _fact(user_id, f"now-{gap}", today - timedelta(days=1), kind="achievement")
        await _pair(user_id, then, now)
        facts.append((gap, then, now))
    async with SessionLocal() as db:
        for i in range(closed):
            db.add(
                Thread(
                    user_id=user_id,
                    title=f"Closed thread {i}",
                    status="closed",
                    opened_on=today - timedelta(days=30),
                    closed_on=today - timedelta(days=2),
                )
            )
        db.add(Thread(user_id=user_id, title="Still open", opened_on=today - timedelta(days=3)))
        await db.commit()
    return facts


@pytest.mark.asyncio
class TestPlateau:
    async def test_button_streams_an_evidence_reply_and_does_not_count_the_day(self, client, monkeypatch):
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        auth, user_id = await _person(client)
        await _goal(user_id)
        facts = await _evidence(user_id, pairs=4)
        other = await _fact(user_id, "an unrelated fact", _today() - timedelta(days=3))

        r = await client.post(PLATEAU, headers=auth)
        assert r.status_code == 200, r.text
        events = parse_sse(r.text)
        assert [e for e, _ in events if e == "user_message"] == []
        assert events[-1][0] == "done"

        system = _system(calls)
        assert "ship my own game" in system  # the anchor
        # The three pairs with the biggest gap, not the 10-day one, nor ordinary facts.
        for gap, then, now in facts[1:]:
            assert str(then.id) in system and str(now.id) in system
        assert str(facts[0][1].id) not in system
        assert str(other.id) not in system
        assert "Closed thread 0" in system
        assert "Still open" not in system

        conv = (await _rows(Conversation, Conversation.user_id == user_id))[0]
        assert conv.counts_for_limit is False
        assert [m.role for m in await _rows(Message, Message.user_id == user_id)] == ["assistant"]

    async def test_little_evidence_leans_on_the_starting_point(self, client, monkeypatch):
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        auth, user_id = await _person(client)
        start = await _fact(user_id, "I can only write hello world", _today() - timedelta(days=2), kind="level")
        r = await client.post(PLATEAU, headers=auth)
        assert r.status_code == 200
        system = _system(calls)
        assert str(start.id) in system
        assert "days" in system and "starting point" in system.lower()

    async def test_previous_intent_plateau_makes_the_next_reply_a_plateau_one(self, client, monkeypatch):
        auth, user_id = await _person(client)
        await _evidence(user_id, pairs=2)
        first, _ = _recorder(("Hm?", "<<<META>>>", '{"quick_replies": [], "intent": "plateau"}'))
        monkeypatch.setattr(conversation, "stream_chat", first)
        await _send(client, auth, "I feel I'm not moving at all")
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        await _send(client, auth, "yes, really")
        assert "Closed thread 0" in _system(calls)
        assert "Still open" not in _system(calls)

    async def test_no_limit_check(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        monday, _ = limits.week_bounds(_today())
        for i in range(settings.free_conversations_per_week):
            day = monday + timedelta(days=i)
            if day == _today():
                day = monday + timedelta(days=6 - i)
            await _day(user_id, day)
        assert (await client.post(MESSAGES, json={"text": "hi"}, headers=auth)).status_code == 402
        assert (await client.post(PLATEAU, headers=auth)).status_code == 200

    async def test_needs_a_verified_email(self, client, monkeypatch):
        auth, user_id = await _person(client, email_verified=False)
        monkeypatch.setattr(settings, "require_verified_email", True)
        r = await client.post(PLATEAU, headers=auth)
        assert r.status_code == 403
        assert r.json()["detail"]["code"] == "email_not_verified"

    async def test_only_the_owners_evidence(self, client, monkeypatch):
        fake, calls = _recorder()
        monkeypatch.setattr(conversation, "stream_chat", fake)
        _, stranger = await _person(client, email="stranger@example.com")
        theirs = await _evidence(stranger, pairs=2)
        auth, _ = await _person(client)
        assert (await client.post(PLATEAU, headers=auth)).status_code == 200
        system = _system(calls)
        assert str(theirs[0][1].id) not in system and "Closed thread" not in system

    async def test_after_level_three_today_the_button_gives_the_template(self, client, monkeypatch):
        monkeypatch.setitem(SAFETY_RESULT, "level", 3)
        auth, _ = await _person(client)
        monkeypatch.setattr(conversation, "stream_chat", _never_called())
        await _send(client, auth, "I want to end it")
        r = await client.post(PLATEAU, headers=auth)
        assert _text(parse_sse(r.text)) == texts.t("en", "safety.level3_no_resources")


# ------------------------------------------------------------------ limit


@pytest.mark.asyncio
class TestLimitStatus:
    async def test_trial_depends_on_the_local_registration_date(self):
        # 20:00 UTC on Oct 20 is Oct 21 in Almaty (UTC+5) and Oct 20 in Los Angeles.
        created = datetime(2026, 10, 20, 20, 0, tzinfo=timezone.utc)
        async with SessionLocal() as db:
            east = User(email="e@example.com", password_hash="x", timezone="Asia/Almaty", created_at=created)
            west = User(email="w@example.com", password_hash="x", timezone="America/Los_Angeles", created_at=created)
            db.add_all([east, west])
            await db.commit()
            today = date(2026, 10, 27)  # 7 days after Oct 20, 6 after Oct 21
            assert (await limits.limit_status(db, east, today)).trial is True
            assert (await limits.limit_status(db, west, today)).trial is False

    async def test_the_week_runs_monday_to_sunday(self):
        async with SessionLocal() as db:
            user = User(email="w@example.com", password_hash="x", timezone=TZ)
            db.add(user)
            await db.commit()
            uid = user.id
        sunday = date(2026, 10, 25)
        await _day(uid, sunday - timedelta(days=1))
        await _day(uid, sunday)
        await _day(uid, sunday + timedelta(days=1), counts=False)
        async with SessionLocal() as db:
            user = await db.get(User, uid)
            assert (await limits.limit_status(db, user, sunday)).used == 2
            assert (await limits.limit_status(db, user, sunday + timedelta(days=1))).used == 0
            assert (await limits.limit_status(db, user, sunday + timedelta(days=7))).used == 0


async def _use_up_week(user_id, tz=TZ, *, include_today=False):
    """FREE_CONVERSATIONS_PER_WEEK counted days in the current local week."""
    today = _today(tz)
    monday, _ = limits.week_bounds(today)
    others = [monday + timedelta(days=i) for i in range(7) if monday + timedelta(days=i) != today]
    days = others[: settings.free_conversations_per_week - (1 if include_today else 0)]
    if include_today:
        days.append(today)
    for day in days:
        await _day(user_id, day)


@pytest.mark.asyncio
class TestLimit:
    async def test_over_the_limit_is_402_before_the_stream(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        await _use_up_week(user_id)
        r = await client.post(MESSAGES, json={"text": "hello"}, headers=auth)
        assert r.status_code == 402
        assert r.json()["detail"]["code"] == "limit_reached"
        assert await _rows(Message, Message.user_id == user_id, Message.role == "user") == []

    async def test_a_day_already_counted_is_not_blocked(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        await _use_up_week(user_id, include_today=True)
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200

    async def test_under_the_limit_passes(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        await _day(user_id, limits.week_bounds(_today())[0] - timedelta(days=1))  # last week
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200

    async def test_trial_has_no_limit(self, client):
        auth, user_id = await _person(client)
        await _use_up_week(user_id)
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200

    async def test_plus_until_today_lifts_it_and_yesterday_does_not(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        await _use_up_week(user_id)
        async with SessionLocal() as db:
            (await db.get(User, user_id)).plus_until = _today() - timedelta(days=1)
            await db.commit()
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 402
        async with SessionLocal() as db:
            (await db.get(User, user_id)).plus_until = _today()
            await db.commit()
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200

    async def test_the_week_is_the_persons_own(self, client):
        # Far east: the local week may already have turned while the server's has not.
        tz = "Pacific/Kiritimati"
        auth, user_id = await _person(client, tz=tz)
        await _end_trial(user_id)
        await _use_up_week(user_id, tz)
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 402
        # The days just before the local Monday belong to last week.
        async with SessionLocal() as db:
            await db.execute(Conversation.__table__.delete().where(Conversation.user_id == user_id))
            await db.commit()
        monday = limits.week_bounds(_today(tz))[0]
        for back in range(1, settings.free_conversations_per_week + 1):
            await _day(user_id, monday - timedelta(days=back))
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200


# ------------------------------------------------------------------ fake door


@pytest.mark.asyncio
class TestPaywall:
    async def test_click_gives_a_month_and_lifts_the_limit(self, client):
        auth, user_id = await _person(client)
        await _end_trial(user_id)
        await _use_up_week(user_id)
        r = await client.post("/api/paywall/click", headers=auth)
        assert r.status_code == 200
        expected = _today() + timedelta(days=settings.plus_beta_days)
        assert r.json() == {"plus_until": expected.isoformat()}
        assert len(await _events("paywall_clicked")) == 1
        assert (await client.post(MESSAGES, json={"text": "hello"}, headers=auth)).status_code == 200
        me = (await client.get("/api/conversations/today", headers=auth)).json()
        assert me["limit"]["plus"] is True

    async def test_needs_a_sign_in(self, client):
        assert (await client.post("/api/paywall/click")).status_code == 401


# ------------------------------------------------------------------ export


@pytest.mark.asyncio
class TestExport:
    async def test_only_the_owners_data(self, client):
        auth, user_id = await _person(client)
        await _goal(user_id, why="mine-why")
        await _send(client, auth, "my own words")
        await _fact(user_id, "my fact", _today())
        async with SessionLocal() as db:
            db.add(Thread(user_id=user_id, title="my thread", opened_on=_today()))
            await db.commit()

        other_auth, other_id = await _person(client, email="other@example.com")
        await _goal(other_id, why="their-why")
        await _send(client, other_auth, "their words")
        await _fact(other_id, "their fact", _today())

        r = await client.get("/api/me/export", headers=auth)
        assert r.status_code == 200
        assert r.headers["content-type"].startswith("application/json")
        assert f'forwardtrace-export-{_today().isoformat()}.json' in r.headers["content-disposition"]
        data = json.loads(r.content)
        dump = json.dumps(data, ensure_ascii=False)
        for mine in ("mine-why", "my own words", "my fact", "my thread"):
            assert mine in dump
        for theirs in ("their-why", "their words", "their fact", "other@example.com"):
            assert theirs not in dump
        assert {"conversations", "facts", "threads", "goal"} <= set(data)
        assert data["conversations"][0]["messages"][0]["content_raw"] == "my own words"
        assert "audio_path" not in dump

    async def test_needs_a_sign_in(self, client):
        assert (await client.get("/api/me/export")).status_code == 401


# ------------------------------------------------------------------ reference dialogs


def _eval_module():
    path = Path(__file__).resolve().parents[1] / "scripts" / "eval_dialogs.py"
    spec = importlib.util.spec_from_file_location("eval_dialogs", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestEvalDialogs:
    def test_the_set_has_fifty_dialogs_ten_of_distress(self):
        module = _eval_module()
        dialogs = module.load_dialogs()
        assert len(dialogs) == 50
        assert len([d for d in dialogs if d["kind"] == "distress"]) == 10
        assert len({d["id"] for d in dialogs}) == 50

    @pytest.mark.asyncio
    async def test_run_checks_and_reports(self):
        module = _eval_module()
        fact = {"id": "f1", "date": "2026-09-17", "type": "struggle", "quote": "old words"}
        dialogs = [
            {"id": "ok", "kind": "normal", "locale": "en", "facts": [fact], "turns": ["I did it"], "expected_safety": 0},
            {"id": "bad", "kind": "normal", "locale": "en", "facts": [], "turns": ["hi"], "expected_safety": 0},
            {"id": "risk", "kind": "distress", "locale": "en", "facts": [], "turns": ["I want to end it"], "expected_safety": 3},
            {"id": "todo", "kind": "normal", "locale": "en", "facts": [], "turns": [""], "expected_safety": 0},
        ]
        f1 = str(module.fact_uuid("ok", "f1"))
        replies = {
            "I did it": f"Then {{{{quote:{f1}}}}}, now this. What changed?<<<META>>>{{}}",
            "hi": f"Well done! Why? How? {{{{quote:{uuid.uuid4()}}}}}<<<META>>>{{}}",
        }

        async def chat(messages, *, model=None, reasoning_effort=None):
            yield replies[messages[-1]["content"]]

        async def check(text, locale):
            return safety.SafetyResult(level=3 if "end it" in text else 0)

        report = await module.run(dialogs, chat=chat, check=check)
        by_id = {r.id: r for r in report.results}
        assert by_id["ok"].problems == []
        assert set(by_id["bad"].problems) >= {"questions", "banned", "unknown_fact"}
        assert by_id["risk"].problems == [] and by_id["risk"].safety == 3
        assert by_id["todo"].skipped
        text = report.text()
        assert "bad" in text and "unknown_fact" in text

    def test_without_a_key_it_says_so(self, monkeypatch, capsys):
        module = _eval_module()
        monkeypatch.setattr(settings, "openai_api_key", None)
        assert module.main([]) == 2
        assert "OPENAI_API_KEY" in capsys.readouterr().out
