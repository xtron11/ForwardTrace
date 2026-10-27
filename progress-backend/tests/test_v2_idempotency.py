"""v2.1, ticket 12: one message per `client_msg_id`, however many times it is sent.

A double click, or "Try again" after the network dropped, resends the same message
with the same id. The server keeps one message, one reply and one model call, and
answers every repeat with the saved message and reply (spec §2.2 «Идемпотентная
отправка», stories 1-5).
"""

import uuid
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Event, Message, User
from app.services import conversation, limits
from app.services.errors import api_error

from conftest import CHAT_REPLY, parse_sse, register

MESSAGES = "/api/conversations/today/messages"
TEXT = "I found the leak with the profiler today."


@pytest.fixture(autouse=True)
def audio_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "audio_dir", str(tmp_path / "audio"))
    return tmp_path / "audio"


@pytest.fixture
def chat_calls(monkeypatch):
    calls: list[list[dict]] = []

    async def counting(messages, *, model=None, reasoning_effort=None):
        calls.append(messages)
        for piece in CHAT_REPLY:
            yield piece

    monkeypatch.setattr(conversation, "stream_chat", counting)
    return calls


async def _person(client, email="person@example.com"):
    auth = await register(client, email=email)
    user_id = uuid.UUID((await client.get("/api/auth/me", headers=auth)).json()["id"])
    async with SessionLocal() as db:
        (await db.get(User, user_id)).first_conversation_done = True
        await db.commit()
    return auth, user_id


async def _rows(model, *where):
    async with SessionLocal() as db:
        return list((await db.execute(select(model).where(*where))).scalars())


async def _post(client, auth, body):
    r = await client.post(MESSAGES, json=body, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def _voice(client, auth, client_msg_id):
    return client.post(
        MESSAGES,
        files={"audio": ("note.webm", b"\x1a\x45\xdf\xa3 fake webm", "audio/webm")},
        data={"client_msg_id": client_msg_id},
        headers=auth,
    )


class TestRepeatAfterTheReply:
    @pytest.mark.asyncio
    async def test_three_sends_make_one_message_one_reply_one_call(self, client, chat_calls):
        auth, user_id = await _person(client)
        key = str(uuid.uuid4())
        streams = [await _post(client, auth, {"text": TEXT, "client_msg_id": key}) for _ in range(3)]

        assert len(chat_calls) == 1
        users = await _rows(Message, Message.role == "user")
        answers = await _rows(Message, Message.role == "assistant")
        assert len(users) == 1 and len(answers) == 1
        assert users[0].client_msg_id == key

        first = streams[0]
        for repeat in streams[1:]:
            names = [e for e, _ in repeat]
            assert names[0] == "user_message" and names[-1] == "done"
            assert repeat[0][1]["id"] == str(users[0].id)
            assert repeat[0][1]["content"] == TEXT
            assert "".join(d["text"] for e, d in repeat if e == "delta") == "What helped you find it?"
            assert repeat[-1][1]["message_id"] == first[-1][1]["message_id"] == str(answers[0].id)
            assert repeat[-1][1]["quick_replies"] == ["The profiler", "Search"]

        events = await _rows(Event, Event.type == "message_duplicate")
        assert [e.payload["state"] for e in events] == ["replayed", "replayed"]
        assert all(e.payload["client_msg_id"] == key for e in events)
        assert len(await _rows(Event, Event.type == "message_sent")) == 1

        body = (await client.get("/api/conversations/today", headers=auth)).json()
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert body["limit"]["used"] == 1

    @pytest.mark.asyncio
    async def test_a_repeat_skips_the_limit(self, client, chat_calls, monkeypatch):
        auth, _ = await _person(client)
        key = "abc-123"
        await _post(client, auth, {"text": TEXT, "client_msg_id": key})

        async def refuse(*args, **kwargs):
            raise api_error(402, "limit_reached", "no")

        monkeypatch.setattr(limits, "ensure_can_message", refuse)
        repeat = await _post(client, auth, {"text": TEXT, "client_msg_id": key})
        assert repeat[-1][0] == "done"
        refused = await client.post(MESSAGES, json={"text": TEXT, "client_msg_id": "other"}, headers=auth)
        assert refused.status_code == 402
        assert len(chat_calls) == 1

    @pytest.mark.asyncio
    async def test_the_same_id_from_another_person_is_a_new_message(self, client, chat_calls):
        auth, _ = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        await _post(client, auth, {"text": TEXT, "client_msg_id": "same-id"})
        theirs = await _post(client, other, {"text": TEXT, "client_msg_id": "same-id"})
        assert theirs[-1][0] == "done" and theirs[-1][1].get("duplicate") is None
        assert len(await _rows(Message, Message.role == "user")) == 2
        assert len(chat_calls) == 2


class TestRepeatWhileWriting:
    @pytest.mark.asyncio
    async def test_in_flight_repeat_gets_duplicate_done_not_409(self, client, chat_calls):
        auth, user_id = await _person(client)
        key = str(uuid.uuid4())
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            pending = await conversation.prepare_message(
                db, user, text=TEXT, audio=None, client_msg_id=key
            )
        r = await client.post(MESSAGES, json={"text": TEXT, "client_msg_id": key}, headers=auth)
        assert r.status_code == 200, r.text
        events = parse_sse(r.text)
        assert [e for e, _ in events] == ["user_message", "done"]
        assert events[0][1]["id"] == str(pending.message_id)
        assert events[-1][1] == {
            "message_id": None,
            "duplicate": True,
            "quick_replies": [],
            "used_fact_ids": [],
            "intent": "normal",
        }
        assert chat_calls == []
        [event] = await _rows(Event, Event.type == "message_duplicate")
        assert event.payload["state"] == "in_flight"

        # Without the key the conversation is still busy.
        busy = await client.post(MESSAGES, json={"text": "another"}, headers=auth)
        assert busy.status_code == 409
        conversation.release_if_unstarted(pending)
        # Released: the same key is a fresh message again.
        fresh = await _post(client, auth, {"text": TEXT, "client_msg_id": key})
        assert fresh[-1][1]["message_id"] is not None
        assert len(chat_calls) == 1

    @pytest.mark.asyncio
    async def test_race_on_insert_is_answered_as_a_repeat(self, client, chat_calls):
        auth, user_id = await _person(client)
        key = "raced"
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            prepared = await conversation.prepare_message(
                db, user, text=TEXT, audio=None, client_msg_id=key
            )
        # Another worker saved the same message in between.
        async with SessionLocal() as db:
            winner = Message(
                conversation_id=prepared.conversation_id,
                user_id=user_id,
                role="user",
                source="text",
                content_raw=TEXT,
                content=[{"type": "text", "text": TEXT}],
                client_msg_id=key,
            )
            db.add(winner)
            await db.commit()
            winner_id = winner.id
        events = parse_sse("".join([item async for item in conversation.stream_reply(prepared)]))
        assert events[0] == (
            "user_message",
            {"id": str(winner_id), "content": TEXT, "source": "text", "detected_language": None},
        )
        assert events[-1][0] == "done" and events[-1][1]["duplicate"] is True
        assert chat_calls == []
        assert len(await _rows(Message, Message.role == "user")) == 1
        assert not conversation.is_busy(prepared.conversation_id)


class TestVoice:
    @pytest.mark.asyncio
    async def test_voice_repeat_writes_no_second_file(self, client, chat_calls, audio_dir):
        auth, user_id = await _person(client)
        key = str(uuid.uuid4())
        first = await _voice(client, auth, key)
        second = await _voice(client, auth, key)
        assert first.status_code == 200 and second.status_code == 200, second.text
        replay = parse_sse(second.text)
        assert replay[0][0] == "user_message" and replay[0][1]["source"] == "voice"
        assert replay[-1][1]["message_id"] == parse_sse(first.text)[-1][1]["message_id"]
        assert len(list(Path(audio_dir / str(user_id)).iterdir())) == 1
        assert len(await _rows(Message, Message.role == "user")) == 1
        assert len(chat_calls) == 1


class TestWithoutKey:
    @pytest.mark.asyncio
    async def test_two_sends_without_key_are_two_messages(self, client, chat_calls):
        auth, _ = await _person(client)
        await _post(client, auth, {"text": TEXT})
        await _post(client, auth, {"text": TEXT})
        assert len(await _rows(Message, Message.role == "user")) == 2
        assert len(chat_calls) == 2

    @pytest.mark.asyncio
    @pytest.mark.parametrize("bad", ["", "has space", "x" * 65, "ключ", 42, "a/b"])
    async def test_bad_key_is_422(self, client, chat_calls, bad):
        auth, _ = await _person(client)
        r = await client.post(MESSAGES, json={"text": TEXT, "client_msg_id": bad}, headers=auth)
        assert r.status_code == 422, r.text
        assert r.json()["detail"]["code"] == "bad_client_msg_id"
        assert await _rows(Message) == []

    @pytest.mark.asyncio
    async def test_bad_key_in_multipart_is_422(self, client, chat_calls):
        auth, _ = await _person(client)
        r = await _voice(client, auth, "no spaces please")
        assert r.status_code == 422 and r.json()["detail"]["code"] == "bad_client_msg_id"


class TestSchema:
    def test_model_has_the_column_and_the_unique_index(self):
        column = Message.__table__.c.client_msg_id
        assert column.nullable and column.type.length == 64
        names = {c.name for c in Message.__table__.constraints}
        assert "uq_messages_user_client_msg" in names

    def test_migration_0017(self):
        path = Path(__file__).parent.parent / "alembic" / "versions" / "0017_client_msg_id.py"
        source = path.read_text(encoding="utf-8")
        assert 'down_revision = "0016_pair_source_length"' in source
        assert "uq_messages_user_client_msg" in source
        assert "def downgrade" in source and "drop_column" in source
