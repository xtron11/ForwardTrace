"""Stage 6: the AI writes first - who gets a message, when it stays quiet, the topic,
the text, what is recorded, delivery by push or Telegram, the reset when the person
answers, POST /api/outreach/{id}/opened and the Telegram bot.

The model is a fake (`outreach.complete_json` in conftest.py); push is patched per test
(`outreach.push.send_to_user`), Telegram's `send_message` records into TELEGRAM_SENT.
"""

import uuid
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import func, select

import conftest
from app.config import settings
from app.db import SessionLocal
from app.models import Conversation, Event, Fact, Goal, Message, Outreach, Thread, User
from app.services import outreach, telegram, texts
from app.services.llm import LLMError
from conftest import TELEGRAM_SENT, parse_sse, register

NOW = datetime(2026, 10, 20, 20, 5, tzinfo=timezone.utc)
TODAY = NOW.date()
SECRET = "hook-secret"
# Captured at import, before conftest.fresh_db swaps in the recording fake.
REAL_SEND = telegram.send_message


# ------------------------------------------------------------------ helpers


async def _person(client, email="person@example.com", locale="en", **fields) -> tuple[dict, uuid.UUID]:
    """A person past the first conversation whose outreach hour is NOW's hour (UTC)."""
    auth = await register(client, email=email, locale=locale, timezone="UTC")
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.first_conversation_done = True
        user.reminder_hour = NOW.hour
        for key, value in fields.items():
            setattr(user, key, value)
        await db.commit()
        return auth, user.id


async def _said(user_id, day: date, text="I fixed the jump today.", *, safety_level=0, hour=12) -> uuid.UUID:
    """A message from the person on `day` (the day's conversation is created if needed)."""
    async with SessionLocal() as db:
        conversation = (
            await db.execute(
                select(Conversation).where(
                    Conversation.user_id == user_id, Conversation.local_date == day
                )
            )
        ).scalar_one_or_none()
        if conversation is None:
            conversation = Conversation(user_id=user_id, local_date=day, counts_for_limit=True)
            db.add(conversation)
            await db.flush()
        message = Message(
            conversation_id=conversation.id,
            user_id=user_id,
            role="user",
            source="text",
            content_raw=text,
            content=[{"type": "text", "text": text}],
            safety_level=safety_level,
            created_at=datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc),
        )
        db.add(message)
        await db.commit()
        return message.id


async def _fact(user_id, message_id, day, quote, *, thread_id=None) -> uuid.UUID:
    async with SessionLocal() as db:
        fact = Fact(
            user_id=user_id, message_id=message_id, local_date=day, type="struggle",
            text=quote, quote=quote, thread_id=thread_id,
        )
        db.add(fact)
        await db.commit()
        return fact.id


async def _thread(user_id, title="Collisions", *, mentioned: date) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = Thread(
            user_id=user_id, title=title, status="open",
            opened_on=mentioned - timedelta(days=10), last_mentioned_on=mentioned,
        )
        db.add(thread)
        await db.commit()
        return thread.id


async def _goal(user_id, title="English") -> None:
    async with SessionLocal() as db:
        db.add(Goal(user_id=user_id, title=title, why_text="to talk to clients"))
        await db.commit()


async def _rows(user_id) -> list[Outreach]:
    async with SessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(Outreach).where(Outreach.user_id == user_id).order_by(Outreach.sent_at)
                )
            ).scalars()
        )


async def _user(user_id) -> User:
    async with SessionLocal() as db:
        return await db.get(User, user_id)


async def _message(message_id) -> Message:
    async with SessionLocal() as db:
        return await db.get(Message, message_id)


def _pushes(monkeypatch, delivered=1) -> list[dict]:
    sent: list[dict] = []

    async def fake(db, user_id, payload):
        sent.append({"user_id": user_id, **payload})
        return delivered

    monkeypatch.setattr(outreach.push, "send_to_user", fake)
    return sent


def _model(monkeypatch, text, quick=()) -> list[str]:
    """The model answers `text`; returns the system prompts it was given."""
    calls: list[str] = []

    async def fake(system, user, schema):
        from app.services.llm import LLMResult

        calls.append(system + "\n" + user)
        return LLMResult(data={"text": text, "quick_replies": list(quick)}, model="mock", elapsed_ms=1)

    monkeypatch.setattr(outreach, "complete_json", fake)
    return calls


def _telegram_on(monkeypatch) -> None:
    monkeypatch.setattr(settings, "telegram_bot_token", "test-bot-token")
    monkeypatch.setattr(settings, "telegram_bot_username", "forwardtrace_test_bot")
    monkeypatch.setattr(settings, "telegram_webhook_secret", SECRET)


# ------------------------------------------------------------------ who is due


class TestSelection:
    @pytest.mark.asyncio
    async def test_due_person_gets_a_message_in_the_day_conversation(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=1))

        assert await outreach.run_once(NOW) == 1

        rows = await _rows(uid)
        assert len(rows) == 1
        row = rows[0]
        assert row.channel == "push"
        async with SessionLocal() as db:
            conversation = await db.get(Conversation, row.conversation_id)
            assert conversation.local_date == TODAY
            assert conversation.started_by == "ai"
            # An unanswered AI message does not paint the day green.
            assert conversation.counts_for_limit is False
            message = await db.get(Message, row.message_id)
            assert message.role == "assistant"
            assert message.source == "outreach"
        user = await _user(uid)
        assert user.last_reminded_on == TODAY
        assert user.outreach_unanswered == 1

    @pytest.mark.asyncio
    async def test_only_once_a_day(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        assert await outreach.run_once(NOW) == 1
        assert await outreach.run_once(NOW + timedelta(minutes=15)) == 0
        assert len(await _rows(uid)) == 1

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "fields",
        [
            {"reminder_hour": (NOW.hour + 1) % 24},
            {"reminders_on": False},
            {"outreach_channel": "none"},
            {"last_reminded_on": TODAY},
            # The opening conversation is still going: a daily message would cut it off.
            {"first_conversation_done": False},
        ],
    )
    async def test_not_due(self, client, monkeypatch, fields):
        _pushes(monkeypatch)
        _, uid = await _person(client, **fields)
        assert await outreach.run_once(NOW) == 0
        assert await _rows(uid) == []

    @pytest.mark.asyncio
    async def test_local_hour_in_the_person_zone(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client, timezone="Asia/Almaty", reminder_hour=(NOW.hour + 5) % 24)
        assert await outreach.run_once(NOW) == 1


# ------------------------------------------------------------------ when it stays quiet


class TestDontSend:
    @pytest.mark.asyncio
    async def test_person_already_wrote_today(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _said(uid, TODAY, hour=9)
        assert await outreach.run_once(NOW) == 0
        assert await _rows(uid) == []

    @pytest.mark.asyncio
    async def test_after_safety_level_3_until_the_next_message(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=1), "...", safety_level=3, hour=10)
        assert await outreach.run_once(NOW) == 0

        # A later message from the person lifts it.
        await _said(uid, TODAY - timedelta(days=1), "I'm ok now.", safety_level=0, hour=18)
        assert await outreach.run_once(NOW) == 1

    @pytest.mark.asyncio
    async def test_after_three_unanswered_only_every_three_days(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(
            client, outreach_unanswered=3, last_reminded_on=TODAY - timedelta(days=2)
        )
        await _said(uid, TODAY - timedelta(days=5))
        assert await outreach.run_once(NOW) == 0

        async with SessionLocal() as db:
            user = await db.get(User, uid)
            user.last_reminded_on = TODAY - timedelta(days=3)
            await db.commit()
        assert await outreach.run_once(NOW) == 1
        assert (await _user(uid)).outreach_unanswered == 4

    @pytest.mark.asyncio
    async def test_fewer_than_three_unanswered_is_daily(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(
            client, outreach_unanswered=2, last_reminded_on=TODAY - timedelta(days=1)
        )
        await _said(uid, TODAY - timedelta(days=3))
        assert await outreach.run_once(NOW) == 1

    @pytest.mark.asyncio
    async def test_fourteen_silent_days_one_farewell_then_nothing(self, client, monkeypatch):
        sent = _pushes(monkeypatch)
        calls = _model(monkeypatch, "Should not be used?")
        _, uid = await _person(client, locale="ru", outreach_unanswered=5)
        await _said(uid, TODAY - timedelta(days=14))

        assert await outreach.run_once(NOW) == 1
        rows = await _rows(uid)
        assert [r.topic for r in rows] == ["farewell"]
        farewell = "Я тут, когда захочешь поговорить. Всё, о чём мы говорили, никуда не делось."
        message = await _message(rows[0].message_id)
        assert message.content == [{"type": "text", "text": farewell}]
        assert sent[0]["body"] == farewell
        assert calls == []  # a fixed text, no model

        # Not again - not the next day, not three days later.
        for days in (1, 3, 9):
            assert await outreach.run_once(NOW + timedelta(days=days)) == 0
        assert len(await _rows(uid)) == 1

    @pytest.mark.asyncio
    async def test_thirteen_silent_days_is_not_a_farewell(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=13))
        assert await outreach.run_once(NOW) == 1
        assert (await _rows(uid))[0].topic != "farewell"

    @pytest.mark.asyncio
    async def test_after_the_farewell_a_new_message_starts_it_again(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=20))
        assert await outreach.run_once(NOW) == 1  # farewell

        later = NOW + timedelta(days=2)
        await _said(uid, later.date() - timedelta(days=1))
        async with SessionLocal() as db:
            (await db.get(User, uid)).outreach_unanswered = 0
            await db.commit()
        assert await outreach.run_once(later) == 1
        assert [r.topic for r in await _rows(uid)][-1] != "farewell"


# ------------------------------------------------------------------ the topic


class TestTopic:
    @pytest.mark.asyncio
    async def test_recent_open_thread_comes_first(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _goal(uid)
        await _said(uid, TODAY - timedelta(days=4))
        tid = await _thread(uid, mentioned=TODAY - timedelta(days=3))

        assert await outreach.run_once(NOW) == 1
        row = (await _rows(uid))[0]
        assert row.topic == "thread"
        assert row.thread_id == tid

    @pytest.mark.asyncio
    async def test_goal_after_two_silent_days(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _goal(uid)
        await _thread(uid, mentioned=TODAY - timedelta(days=4))  # too old
        await _said(uid, TODAY - timedelta(days=2))

        assert await outreach.run_once(NOW) == 1
        assert (await _rows(uid))[0].topic == "anchor"

    @pytest.mark.asyncio
    async def test_yesterday_when_the_person_wrote_yesterday(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        await _goal(uid)
        await _said(uid, TODAY - timedelta(days=1))

        assert await outreach.run_once(NOW) == 1
        assert (await _rows(uid))[0].topic == "yesterday"

    @pytest.mark.asyncio
    async def test_general_question_otherwise(self, client, monkeypatch):
        _pushes(monkeypatch)
        _model(monkeypatch, "")  # an empty answer falls back to the template
        _, uid = await _person(client, locale="ru")
        await _said(uid, TODAY - timedelta(days=3))  # no goal: no anchor

        assert await outreach.run_once(NOW) == 1
        row = (await _rows(uid))[0]
        assert row.topic == "general"
        message = await _message(row.message_id)
        assert message.content == [
            {"type": "text", "text": "Что сегодня получилось, что раньше не получалось?"}
        ]

    @pytest.mark.asyncio
    async def test_pick_topic_directly(self, client):
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=1))
        tid = await _thread(uid, mentioned=TODAY)
        async with SessionLocal() as db:
            user = await db.get(User, uid)
            topic = await outreach.pick_topic(db, user, TODAY)
        assert topic.kind == "thread"
        assert topic.thread.id == tid


# ------------------------------------------------------------------ the text


class TestText:
    @pytest.mark.asyncio
    async def test_model_text_with_a_quote_placeholder(self, client, monkeypatch):
        sent = _pushes(monkeypatch)
        _, uid = await _person(client)
        mid = await _said(uid, TODAY - timedelta(days=2), "the character fell through the floor")
        tid = await _thread(uid, mentioned=TODAY - timedelta(days=1))
        fid = await _fact(uid, mid, TODAY - timedelta(days=2), "fell through the floor", thread_id=tid)
        calls = _model(monkeypatch, f"You said {{{{quote:{fid}}}}} - how is it now?", ["Better", "Same"])

        assert await outreach.run_once(NOW) == 1
        assert str(fid) in calls[0]  # the model was given the fact to point at
        row = (await _rows(uid))[0]
        message = await _message(row.message_id)
        assert [s["type"] for s in message.content] == ["text", "quote", "text"]
        assert message.content[1]["quote"] == "fell through the floor"
        assert message.quick_replies == ["Better", "Same"]
        assert message.used_fact_ids == [str(fid)]

        body = sent[0]["body"]
        assert "{{" not in body
        assert "fell through the floor" in body
        assert sent[0]["url"] == f"/today?o={row.id}"

    @pytest.mark.asyncio
    async def test_russian_push_quotes_in_guillemets(self, client, monkeypatch):
        sent = _pushes(monkeypatch)
        _, uid = await _person(client, locale="ru")
        mid = await _said(uid, TODAY - timedelta(days=2), "персонаж проваливался сквозь пол")
        tid = await _thread(uid, mentioned=TODAY - timedelta(days=1))
        fid = await _fact(uid, mid, TODAY - timedelta(days=2), "проваливался сквозь пол", thread_id=tid)
        _model(monkeypatch, f"Вы говорили {{{{quote:{fid}}}}} — как сейчас?")

        assert await outreach.run_once(NOW) == 1
        assert sent[0]["body"] == "Вы говорили «проваливался сквозь пол» — как сейчас?"

    @pytest.mark.asyncio
    async def test_unknown_fact_id_is_dropped(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client)
        _model(monkeypatch, f"You said {{{{quote:{uuid.uuid4()}}}}} - what changed?")
        assert await outreach.run_once(NOW) == 1
        message = await _message((await _rows(uid))[0].message_id)
        assert all(s["type"] == "text" for s in message.content)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "text",
        [
            " ".join(["word"] * 30) + "?",  # longer than OUTREACH_MAX_WORDS
            "",  # empty
        ],
    )
    async def test_rule_violation_falls_back_to_the_topic_template(self, client, monkeypatch, text):
        _pushes(monkeypatch)
        _model(monkeypatch, text)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=4))
        await _thread(uid, "Collisions", mentioned=TODAY - timedelta(days=1))

        assert await outreach.run_once(NOW) == 1
        message = await _message((await _rows(uid))[0].message_id)
        assert message.content == [
            {"type": "text", "text": texts.t("en", "outreach.thread", title="Collisions")}
        ]

    @pytest.mark.asyncio
    @pytest.mark.parametrize("text", ["What worked? And what did not?", "Well done, what is next?"])
    async def test_questions_and_wording_are_not_policed(self, client, monkeypatch, text):
        # v2.1 §2.1 #11: only empty, length and quotes fall back to the template.
        _pushes(monkeypatch)
        _model(monkeypatch, text)
        _, uid = await _person(client)
        await _said(uid, TODAY - timedelta(days=4))
        assert await outreach.run_once(NOW) == 1
        message = await _message((await _rows(uid))[0].message_id)
        assert message.content == [{"type": "text", "text": text}]

    @pytest.mark.asyncio
    async def test_model_failure_falls_back_to_the_template(self, client, monkeypatch):
        _pushes(monkeypatch)

        async def broken(system, user, schema):
            raise LLMError("down")

        monkeypatch.setattr(outreach, "complete_json", broken)
        _, uid = await _person(client, locale="ru")
        await _goal(uid, "английский")
        await _said(uid, TODAY - timedelta(days=5))

        assert await outreach.run_once(NOW) == 1
        message = await _message((await _rows(uid))[0].message_id)
        assert message.content == [
            {"type": "text", "text": texts.t("ru", "outreach.anchor", goal="английский")}
        ]


# ------------------------------------------------------------------ delivery


class TestDelivery:
    @pytest.mark.asyncio
    async def test_push(self, client, monkeypatch):
        sent = _pushes(monkeypatch, delivered=1)
        _, uid = await _person(client)
        assert await outreach.run_once(NOW) == 1
        row = (await _rows(uid))[0]
        assert row.delivered is True
        assert sent[0]["user_id"] == uid
        assert sent[0]["title"] and sent[0]["body"]
        assert sent[0]["url"] == f"/today?o={row.id}"

    @pytest.mark.asyncio
    async def test_no_device_still_records_the_message(self, client, monkeypatch):
        _pushes(monkeypatch, delivered=0)
        _, uid = await _person(client)
        assert await outreach.run_once(NOW) == 1
        row = (await _rows(uid))[0]
        assert row.delivered is False
        assert row.message_id is not None
        assert (await _user(uid)).last_reminded_on == TODAY

    @pytest.mark.asyncio
    async def test_push_failure_is_not_fatal(self, client, monkeypatch):
        async def boom(db, user_id, payload):
            raise RuntimeError("push service down")

        monkeypatch.setattr(outreach.push, "send_to_user", boom)
        _, uid = await _person(client)
        _, other = await _person(client, email="other@example.com")
        assert await outreach.run_once(NOW) == 2
        assert [r.delivered for r in await _rows(uid)] == [False]
        assert len(await _rows(other)) == 1

    @pytest.mark.asyncio
    async def test_telegram_with_a_reply_button(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        pushes = _pushes(monkeypatch)
        _, uid = await _person(client, outreach_channel="telegram", telegram_chat_id=777)
        assert await outreach.run_once(NOW) == 1
        row = (await _rows(uid))[0]
        assert row.channel == "telegram"
        assert row.delivered is True
        assert pushes == []
        chat_id, text, button = TELEGRAM_SENT[0]
        assert chat_id == 777
        assert text == conftest.OUTREACH_RESULT["text"]
        assert button == f"{settings.app_url.rstrip('/')}/today?o={row.id}"

    @pytest.mark.asyncio
    async def test_telegram_switched_off_is_not_delivered(self, client, monkeypatch):
        _pushes(monkeypatch)
        _, uid = await _person(client, outreach_channel="telegram", telegram_chat_id=777)
        assert await outreach.run_once(NOW) == 1
        assert (await _rows(uid))[0].delivered is False
        assert TELEGRAM_SENT == []


# ------------------------------------------------------------------ the person answers


class TestReply:
    @pytest.mark.asyncio
    async def test_answer_resets_the_streak_and_marks_the_reply(self, client, monkeypatch):
        _pushes(monkeypatch)
        now = datetime.now(timezone.utc)
        auth, uid = await _person(client, reminder_hour=now.hour, outreach_unanswered=2)
        assert await outreach.run_once(now) == 1
        assert (await _user(uid)).outreach_unanswered == 3

        r = await client.post(
            "/api/conversations/today/messages", json={"text": "It went fine."}, headers=auth
        )
        assert r.status_code == 200
        assert [e for e, _ in parse_sse(r.text)][-1] == "done"

        user = await _user(uid)
        assert user.outreach_unanswered == 0
        row = (await _rows(uid))[0]
        assert row.replied_at is not None
        async with SessionLocal() as db:
            conversation = await db.get(Conversation, row.conversation_id)
            assert conversation.counts_for_limit is True
            assert conversation.started_by == "ai"


# ------------------------------------------------------------------ opened


class TestOpened:
    @pytest.mark.asyncio
    async def test_opened_is_idempotent_and_private(self, client, monkeypatch):
        _pushes(monkeypatch)
        auth, uid = await _person(client)
        other, _ = await _person(client, email="other@example.com", reminder_hour=(NOW.hour + 1) % 24)
        assert await outreach.run_once(NOW) == 1
        oid = (await _rows(uid))[0].id

        assert (await client.post(f"/api/outreach/{oid}/opened", headers=other)).status_code == 404
        assert (await _rows(uid))[0].opened_at is None

        assert (await client.post(f"/api/outreach/{oid}/opened", headers=auth)).status_code == 204
        first = (await _rows(uid))[0].opened_at
        assert first is not None
        assert (await client.post(f"/api/outreach/{oid}/opened", headers=auth)).status_code == 204
        assert (await _rows(uid))[0].opened_at == first

        async with SessionLocal() as db:
            events = (
                await db.execute(select(Event).where(Event.type == "outreach_opened"))
            ).scalars().all()
        assert len(events) == 1
        assert events[0].user_id == uid
        assert events[0].payload["outreach_id"] == str(oid)

    @pytest.mark.asyncio
    async def test_unknown_id(self, client):
        auth, _ = await _person(client)
        r = await client.post(f"/api/outreach/{uuid.uuid4()}/opened", headers=auth)
        assert r.status_code == 404
        assert r.json()["detail"]["code"] == "not_found"


# ------------------------------------------------------------------ Telegram


def _update(chat_id: int, text: str, language="en") -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 10,
            "chat": {"id": chat_id, "type": "private"},
            "from": {"id": chat_id, "language_code": language},
            "text": text,
        },
    }


async def _hook(client, update: dict, secret: str | None = SECRET):
    headers = {"X-Telegram-Bot-Api-Secret-Token": secret} if secret is not None else {}
    return await client.post("/api/telegram/webhook", json=update, headers=headers)


async def _link_token(client, auth) -> str:
    r = await client.post("/api/telegram/link", headers=auth)
    assert r.status_code == 200, r.text
    url = r.json()["url"]
    assert url.startswith("https://t.me/forwardtrace_test_bot?start=")
    return url.split("start=", 1)[1]


class TestTelegram:
    @pytest.mark.asyncio
    async def test_disabled_without_a_bot_token(self, client):
        auth, _ = await _person(client)
        r = await client.post("/api/telegram/link", headers=auth)
        assert r.status_code == 503
        assert r.json()["detail"]["code"] == "telegram_disabled"
        assert (await _hook(client, _update(1, "/start x"))).status_code == 503
        me = (await client.get("/api/auth/me", headers=auth)).json()
        assert me["telegram_available"] is False

    @pytest.mark.asyncio
    async def test_availability_has_no_side_effects(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        auth, uid = await _person(client)
        me = (await client.get("/api/auth/me", headers=auth)).json()
        assert me["telegram_available"] is True
        assert me["telegram_linked"] is False
        assert (await _user(uid)).telegram_link_token is None

    @pytest.mark.asyncio
    async def test_webhook_needs_the_secret_header(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        assert (await _hook(client, _update(1, "hi"), secret=None)).status_code == 403
        assert (await _hook(client, _update(1, "hi"), secret="wrong")).status_code == 403
        assert TELEGRAM_SENT == []

    @pytest.mark.asyncio
    async def test_start_links_once(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        auth, uid = await _person(client, locale="ru")
        token = await _link_token(client, auth)

        assert (await _hook(client, _update(555, f"/start {token}"))).status_code == 200
        user = await _user(uid)
        assert user.telegram_chat_id == 555
        assert user.outreach_channel == "telegram"
        assert user.telegram_link_token is None
        assert TELEGRAM_SENT[-1][:2] == (555, texts.t("ru", "telegram.linked"))
        assert (await client.get("/api/auth/me", headers=auth)).json()["telegram_linked"] is True

        # The same link a second time, from another chat: expired, nothing changes.
        assert (await _hook(client, _update(556, f"/start {token}", "ru"))).status_code == 200
        assert TELEGRAM_SENT[-1][:2] == (556, "Ссылка устарела — получите новую в профиле.")
        assert (await _user(uid)).telegram_chat_id == 555

    @pytest.mark.asyncio
    async def test_unknown_token(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        await _hook(client, _update(9, "/start nope"))
        assert TELEGRAM_SENT == [(9, texts.t("en", "telegram.link_expired"), None)]

    @pytest.mark.asyncio
    async def test_a_new_link_replaces_the_old_one(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        auth, uid = await _person(client)
        old = await _link_token(client, auth)
        new = await _link_token(client, auth)
        assert old != new
        await _hook(client, _update(1, f"/start {old}"))
        assert (await _user(uid)).telegram_chat_id is None
        await _hook(client, _update(1, f"/start {new}"))
        assert (await _user(uid)).telegram_chat_id == 1

    @pytest.mark.asyncio
    async def test_link_and_unlink_are_per_person(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        a, uid_a = await _person(client, email="a@example.com")
        b, uid_b = await _person(client, email="b@example.com")
        token_a = await _link_token(client, a)
        token_b = await _link_token(client, b)
        await _hook(client, _update(100, f"/start {token_a}"))
        await _hook(client, _update(200, f"/start {token_b}"))
        assert (await _user(uid_a)).telegram_chat_id == 100
        assert (await _user(uid_b)).telegram_chat_id == 200

        assert (await client.delete("/api/telegram/link", headers=b)).status_code == 204
        user_b = await _user(uid_b)
        assert user_b.telegram_chat_id is None
        assert user_b.outreach_channel == "push"
        user_a = await _user(uid_a)
        assert user_a.telegram_chat_id == 100
        assert user_a.outreach_channel == "telegram"

    @pytest.mark.asyncio
    async def test_unlink_works_with_the_bot_switched_off(self, client):
        auth, uid = await _person(client, telegram_chat_id=5, outreach_channel="telegram")
        assert (await client.delete("/api/telegram/link", headers=auth)).status_code == 204
        user = await _user(uid)
        assert user.telegram_chat_id is None
        assert user.outreach_channel == "push"

    @pytest.mark.asyncio
    async def test_text_to_the_bot_is_a_message_in_today_conversation(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        auth, uid = await _person(client, telegram_chat_id=321, outreach_channel="telegram")

        assert (await _hook(client, _update(321, "I finally fixed the jump."))).status_code == 200

        today = (await client.get("/api/conversations/today", headers=auth)).json()
        roles = [(m["role"], m["content"][0]["text"]) for m in today["messages"]]
        assert roles[0] == ("user", "I finally fixed the jump.")
        assert roles[1][0] == "assistant"
        # The streamed reply arrives in the bot as one message.
        assert TELEGRAM_SENT[-1][:2] == (321, "What helped you find it?")
        assert len(TELEGRAM_SENT) == 1

    @pytest.mark.asyncio
    async def test_text_from_an_unlinked_chat(self, client, monkeypatch):
        _telegram_on(monkeypatch)
        await _person(client)
        await _hook(client, _update(999, "hello", "ru"))
        assert TELEGRAM_SENT[-1][:2] == (999, texts.t("ru", "telegram.not_linked"))
        async with SessionLocal() as db:
            assert (await db.execute(select(func.count(Message.id)))).scalar_one() == 0


class TestTelegramSend:
    @pytest.mark.asyncio
    async def test_send_message_posts_to_the_bot_api(self, monkeypatch):
        """The real send_message (conftest replaces it) against an httpx mock transport."""
        import httpx

        _telegram_on(monkeypatch)
        seen = []

        def handler(request: httpx.Request) -> httpx.Response:
            import json

            seen.append((request.url.path, json.loads(request.content)))
            return httpx.Response(200, json={"ok": True, "result": {}})

        monkeypatch.setattr(telegram, "_transport", httpx.MockTransport(handler))
        assert await REAL_SEND(42, "Hi?", "https://app.example/today?o=1", button_text="Reply") is True
        path, body = seen[0]
        assert path.endswith("/sendMessage")
        assert "test-bot-token" in path
        assert body["chat_id"] == 42
        assert body["text"] == "Hi?"
        button = body["reply_markup"]["inline_keyboard"][0][0]
        assert button == {"text": "Reply", "url": "https://app.example/today?o=1"}
