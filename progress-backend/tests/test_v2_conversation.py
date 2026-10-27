"""Stage 2: the day's conversation, the streamed reply, quotes and the endpoints around it.

The model and speech-to-text are fakes (conftest.py patches `conversation.stream_chat`
and `conversation.transcribe`); provider tests below talk to an httpx MockTransport.
"""

import asyncio
import inspect
import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.config import settings
from app.db import SessionLocal
from app.models import Conversation, Event, Fact, Goal, Message, Outreach, Pair, Thread, User
from app.services import costs, llm, stt
from app.time_utils import local_today

from conftest import parse_sse, register

TZ = "America/Los_Angeles"


# ------------------------------------------------------------------ providers


def _sse_body(chunks: list[dict]) -> bytes:
    lines = [f"data: {json.dumps(c)}\n\n" for c in chunks]
    lines.append("data: [DONE]\n\n")
    return "".join(lines).encode()


class TestStreamChat:
    @pytest.mark.asyncio
    async def test_yields_text_chunks_and_records_final_usage(self, monkeypatch):
        seen: dict = {}

        def handler(request: httpx.Request) -> httpx.Response:
            seen["url"] = str(request.url)
            seen["payload"] = json.loads(request.content)
            body = _sse_body(
                [
                    {"model": "gpt-5.6-luna", "choices": [{"delta": {"role": "assistant"}}]},
                    {"model": "gpt-5.6-luna", "choices": [{"delta": {"content": "Hel"}}]},
                    {"model": "gpt-5.6-luna", "choices": [{"delta": {"content": "lo"}}]},
                    {
                        "model": "gpt-5.6-luna",
                        "choices": [],
                        "usage": {"prompt_tokens": 1000, "completion_tokens": 500},
                    },
                ]
            )
            return httpx.Response(200, content=body, headers={"content-type": "text/event-stream"})

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "openai_model", "gpt-5.6-luna")
        monkeypatch.setattr(settings, "chat_model", None)
        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "llm_price_output_per_1m", 2.0)
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))

        with costs.track() as usage:
            parts = [p async for p in llm.stream_chat([{"role": "user", "content": "hi"}])]

        assert parts == ["Hel", "lo"]
        assert seen["url"].endswith("/chat/completions")
        assert seen["payload"]["stream"] is True
        assert seen["payload"]["stream_options"] == {"include_usage": True}
        assert seen["payload"]["model"] == "gpt-5.6-luna"
        assert seen["payload"]["messages"] == [{"role": "user", "content": "hi"}]
        # (1000 * $1 + 500 * $2) per million tokens
        assert usage.llm_calls == 1
        assert usage.llm_usd == pytest.approx(0.002)

    @pytest.mark.asyncio
    async def test_http_error_is_llm_error(self, monkeypatch):
        def handler(request):
            return httpx.Response(500, text="boom")

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "llm_max_retries", 0)
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with pytest.raises(llm.LLMError):
            async for _ in llm.stream_chat([{"role": "user", "content": "hi"}]):
                pass

    @pytest.mark.asyncio
    async def test_chat_model_and_effort_are_used(self, monkeypatch):
        seen: dict = {}

        def handler(request):
            seen["payload"] = json.loads(request.content)
            return httpx.Response(200, content=_sse_body([]))

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "chat_model", "chat-x")
        monkeypatch.setattr(settings, "chat_reasoning_effort", "medium")
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        assert [p async for p in llm.stream_chat([{"role": "user", "content": "x"}])] == []
        assert seen["payload"]["model"] == "chat-x"
        assert seen["payload"]["reasoning_effort"] == "medium"


class TestCompleteJsonWith:
    def test_complete_json_signature_unchanged(self):
        assert list(inspect.signature(llm.complete_json).parameters) == ["system", "user", "schema"]

    @pytest.mark.asyncio
    async def test_model_and_effort_are_sent(self, monkeypatch):
        seen: dict = {}

        def handler(request):
            seen["payload"] = json.loads(request.content)
            return httpx.Response(
                200,
                json={
                    "model": "safety-x",
                    "choices": [{"message": {"content": '{"level": 2}'}}],
                    "usage": {"prompt_tokens": 10, "completion_tokens": 2},
                },
            )

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with costs.track() as usage:
            result = await llm.complete_json_with(
                "sys", "usr", {"type": "object"}, model="safety-x", reasoning_effort="minimal"
            )
        assert result.data == {"level": 2}
        assert result.model == "safety-x"
        assert seen["payload"]["model"] == "safety-x"
        assert seen["payload"]["reasoning_effort"] == "minimal"
        assert usage.llm_calls == 1


class TestDeepgramWords:
    @pytest.mark.asyncio
    async def test_words_with_timings_are_kept(self, monkeypatch, tmp_path):
        def handler(request):
            return httpx.Response(
                200,
                json={
                    "metadata": {"duration": 2.5},
                    "results": {
                        "channels": [
                            {
                                "detected_language": "en",
                                "alternatives": [
                                    {
                                        "transcript": "hello world",
                                        "words": [
                                            {"word": "hello", "punctuated_word": "Hello,", "start": 0.1, "end": 0.4},
                                            {"word": "world", "start": 0.5, "end": 0.9},
                                        ],
                                    }
                                ],
                            }
                        ]
                    },
                },
            )

        clip = tmp_path / "a.webm"
        clip.write_bytes(b"\x00" * 10)
        monkeypatch.setattr(settings, "stt_provider", "deepgram")
        monkeypatch.setattr(settings, "deepgram_api_key", "test-key")
        monkeypatch.setattr(stt, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        result = await stt.transcribe(str(clip), "audio/webm")
        assert result.text == "hello world"
        assert result.words == [
            {"w": "Hello,", "start": 0.1, "end": 0.4},
            {"w": "world", "start": 0.5, "end": 0.9},
        ]


# ------------------------------------------------------------------ rendering


def _fact(quote="персонаж проваливался сквозь пол", day=date(2026, 9, 17), **kw) -> Fact:
    return Fact(
        id=kw.pop("id", uuid.uuid4()),
        user_id=uuid.uuid4(),
        type="struggle",
        text="falls through the floor",
        quote=quote,
        local_date=day,
        **kw,
    )


def _render(chunks: list[str], known: dict | None = None, **kw):
    from app.services.conversation import ReplyRenderer

    renderer = ReplyRenderer(known or {}, **kw)
    events = []
    for chunk in chunks:
        events += renderer.feed(chunk)
    events += renderer.flush()
    return events, renderer.finish()


def _streamed_text(events) -> str:
    return "".join(d["text"] for e, d in events if e == "delta")


class TestReplyRenderer:
    def test_known_quote_becomes_a_quote_event_from_the_database(self):
        fact = _fact(message_id=uuid.uuid4(), audio_start_ms=1200, audio_end_ms=2600)
        fid = str(fact.id)
        # The placeholder is split across chunks, as a real stream would split it.
        chunks = ["Смотрите: {", "{quote:", fid[:10], fid[10:] + "}", "} — а сегодня?\n<<<", "META>>>\n",
                  '{"quick_replies": ["Профайлер", "Гугл"], "intent": "normal"}']
        events, reply = _render(chunks, {fid: fact})
        kinds = [e for e, _ in events]
        assert kinds[0] == "delta" and "quote" in kinds
        quote = next(d for e, d in events if e == "quote")
        assert quote == {
            "fact_id": fid,
            "quote": "персонаж проваливался сквозь пол",
            "local_date": "2026-09-17",
            "recalled": False,
            "message_id": str(fact.message_id),
            "audio_start_ms": 1200,
            "audio_end_ms": 2600,
        }
        assert _streamed_text(events) == "Смотрите:  — а сегодня?"
        assert "META" not in _streamed_text(events) and "{{" not in _streamed_text(events)
        assert reply.used_fact_ids == [fid]
        assert reply.meta == {"quick_replies": ["Профайлер", "Гугл"], "intent": "normal"}
        assert [s["type"] for s in reply.segments] == ["text", "quote", "text"]
        assert reply.segments[1]["fact_id"] == fid
        assert reply.content_raw == f"Смотрите: {{{{quote:{fid}}}}} — а сегодня?"

    def test_unknown_fact_id_is_dropped_silently(self):
        stranger = str(uuid.uuid4())
        events, reply = _render([f"Before {{{{quote:{stranger}}}}} after"], {})
        assert [e for e, _ in events] == ["delta"] * sum(1 for e, _ in events)
        assert stranger not in json.dumps([d for _, d in events])
        assert _streamed_text(events) == "Before  after"
        assert reply.used_fact_ids == []
        assert all(s["type"] == "text" for s in reply.segments)

    def test_unclosed_placeholder_is_dropped_and_text_before_it_kept(self):
        fact = _fact()
        events, reply = _render([f"Kept text {{{{quote:{fact.id}"], {str(fact.id): fact})
        assert _streamed_text(events) == "Kept text"
        assert reply.used_fact_ids == []
        assert reply.segments == [{"type": "text", "text": "Kept text"}]

    def test_broken_meta_falls_back_to_defaults(self):
        events, reply = _render(["Hello there?\n<<<META>>>\n{quick_replies: [oops"])
        assert _streamed_text(events) == "Hello there?"
        assert reply.meta == {"quick_replies": [], "intent": "normal"}

    def test_meta_is_cleaned(self):
        replies = [" a ", "", "b", 7, "c", "d", "e", "f"]
        _, reply = _render(["Hi<<<META>>>" + json.dumps({"quick_replies": replies, "intent": "weird"})])
        assert reply.meta["intent"] == "normal"
        assert reply.meta["quick_replies"] == ["a", "b", "c", "d", "e"]  # MAX_QUICK_REPLIES = 5
        _, reply = _render(["Hi<<<META>>>```json\n" + json.dumps({"quick_replies": [], "intent": "plateau"}) + "\n```"])
        assert reply.meta["intent"] == "plateau"

    def test_missing_meta_is_not_an_error(self):
        events, reply = _render(["Just text, no separator."])
        assert _streamed_text(events) == "Just text, no separator."
        assert reply.meta == {"quick_replies": [], "intent": "normal"}

    def test_recalled_quote_is_marked(self):
        fact = _fact()
        events, _ = _render([f"{{{{quote:{fact.id}}}}}"], {str(fact.id): fact}, recalled={str(fact.id)})
        assert next(d for e, d in events if e == "quote")["recalled"] is True


def test_sse_format():
    from app.services.conversation import sse

    assert sse("delta", {"text": "привет"}) == 'event: delta\ndata: {"text": "привет"}\n\n'
    assert parse_sse(sse("done", {"a": 1}) + sse("error", {"code": "x"})) == [("done", {"a": 1}), ("error", {"code": "x"})]


# ------------------------------------------------------------------ endpoints

MESSAGES = "/api/conversations/today/messages"


@pytest.fixture(autouse=True)
def audio_dir(monkeypatch, tmp_path):
    monkeypatch.setattr(settings, "audio_dir", str(tmp_path / "audio"))
    return tmp_path / "audio"


async def _me(client, auth) -> uuid.UUID:
    r = await client.get("/api/auth/me", headers=auth)
    return uuid.UUID(r.json()["id"])


async def _person(client, email="person@example.com", locale="en", onboarded=True):
    """A verified account; `onboarded` skips the first conversation."""
    auth = await register(client, email=email, locale=locale)
    user_id = await _me(client, auth)
    if onboarded:
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            user.first_conversation_done = True
            await db.commit()
    return auth, user_id


async def _send(client, auth, text="I found the leak with the profiler today."):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    assert r.headers["content-type"].startswith("text/event-stream")
    return parse_sse(r.text)


async def _voice(client, auth, data=b"\x1a\x45\xdf\xa3 fake webm", mime="audio/webm"):
    return await client.post(MESSAGES, files={"audio": ("note.webm", data, mime)}, headers=auth)


def _today() -> date:
    return local_today(TZ)


async def _add_fact(user_id, quote, day, *, flagged=False, message_id=None, thread_id=None) -> Fact:
    async with SessionLocal() as db:
        fact = Fact(
            user_id=user_id,
            message_id=message_id,
            local_date=day,
            type="struggle",
            text="a fact",
            quote=quote,
            thread_id=thread_id,
            flagged_at=datetime.now(timezone.utc) if flagged else None,
        )
        db.add(fact)
        await db.commit()
        return fact


async def _rows(model, *where):
    async with SessionLocal() as db:
        return list((await db.execute(select(model).where(*where))).scalars())


def _reply(*pieces):
    async def fake(messages, *, model=None, reasoning_effort=None):
        for piece in pieces:
            yield piece

    return fake


class TestToday:
    @pytest.mark.asyncio
    async def test_first_conversation_starts_with_the_greeting(self, client):
        auth, _ = await _person(client, onboarded=False)
        r = await client.get("/api/conversations/today", headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["kind"] == "first"
        assert body["local_date"] == _today().isoformat()
        assert body["state"]["step"] == "skill"
        [greeting] = body["messages"]
        assert greeting["role"] == "assistant"
        assert greeting["content"] == [
            {"type": "text", "text": "Hi! I'll help you notice how you grow — in your own words. What are you working on right now?"}
        ]
        assert greeting["quick_replies"] == ["Programming", "Game dev", "A foreign language", "Sport", "Music"]
        assert body["limit"] == {"used": 0, "free": 3, "plus": False, "trial": True}
        again = await client.get("/api/conversations/today", headers=auth)
        assert again.json()["id"] == body["id"] and len(again.json()["messages"]) == 1

    @pytest.mark.asyncio
    async def test_russian_greeting_uses_informal_address(self, client):
        # v2.1: the dialogue speaks «ты» (spec §2.1 #1, §2.4).
        auth, _ = await _person(client, locale="ru", onboarded=False)
        body = (await client.get("/api/conversations/today", headers=auth)).json()
        text = body["messages"][0]["content"][0]["text"].lower()
        assert " ты " in text and not re.search(r"\b(вы|вам|ваш\w*)\b", text)

    @pytest.mark.asyncio
    async def test_daily_conversation_after_onboarding(self, client):
        auth, _ = await _person(client)
        body = (await client.get("/api/conversations/today", headers=auth)).json()
        assert body["kind"] == "daily" and body["messages"] == []

    @pytest.mark.asyncio
    async def test_unfinished_first_conversation_continues_next_day(self, client):
        auth, user_id = await _person(client, onboarded=False)
        state = {"step": "finish", "retries": 0, "no_finish": False, "just_started": False}
        async with SessionLocal() as db:
            db.add(Conversation(user_id=user_id, local_date=_today() - timedelta(days=1),
                                kind="first", started_by="ai", state=state))
            await db.commit()
        body = (await client.get("/api/conversations/today", headers=auth)).json()
        assert body["kind"] == "first" and body["state"]["step"] == "finish"

    @pytest.mark.asyncio
    async def test_limit_counts_this_week_only(self, client):
        auth, user_id = await _person(client)
        today = _today()
        monday = today - timedelta(days=today.weekday())
        async with SessionLocal() as db:
            # Last Sunday and the Friday before belong to last week.
            for day in (monday - timedelta(days=1), monday - timedelta(days=3)):
                db.add(Conversation(user_id=user_id, local_date=day, counts_for_limit=True))
            if monday != today:
                db.add(Conversation(user_id=user_id, local_date=monday, counts_for_limit=True))
            await db.commit()
        limit = (await client.get("/api/conversations/today", headers=auth)).json()["limit"]
        assert limit["used"] == (0 if monday == today else 1)


class TestSendText:
    @pytest.mark.asyncio
    async def test_event_order_and_saved_reply(self, client):
        auth, user_id = await _person(client)
        events = await _send(client, auth)
        names = [e for e, _ in events]
        assert names[0] == "user_message" and names[-1] == "done"
        assert set(names[1:-1]) == {"delta"}
        assert events[0][1]["content"] == "I found the leak with the profiler today."
        assert events[0][1]["source"] == "text"
        done = events[-1][1]
        assert done["quick_replies"] == []  # v2.1: options only when the model offers them
        assert done["intent"] == "normal" and done["used_fact_ids"] == []
        assert "".join(d["text"] for e, d in events if e == "delta") == "What helped you find it?"

        [answer] = await _rows(Message, Message.role == "assistant")
        assert str(answer.id) == done["message_id"]
        assert answer.content_raw == "What helped you find it?"
        assert answer.content == [{"type": "text", "text": "What helped you find it?"}]
        assert answer.quick_replies == []
        assert answer.used_fact_ids == [] and answer.intent == "normal"
        assert answer.model_name and answer.llm_ms is not None
        [day] = await _rows(Conversation, Conversation.user_id == user_id)
        assert day.counts_for_limit is True

        body = (await client.get("/api/conversations/today", headers=auth)).json()
        assert [m["role"] for m in body["messages"]] == ["user", "assistant"]
        assert body["limit"]["used"] == 1

    @pytest.mark.asyncio
    async def test_cost_of_the_reply_is_saved(self, client, monkeypatch):
        async def fake(messages, *, model=None, reasoning_effort=None):
            yield "Ok?"
            costs.record_llm(settings.openai_model, {"prompt_tokens": 1000, "completion_tokens": 500})

        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "llm_price_output_per_1m", 2.0)
        monkeypatch.setattr("app.services.conversation.stream_chat", fake)
        auth, _ = await _person(client)
        await _send(client, auth)
        [answer] = await _rows(Message, Message.role == "assistant")
        assert answer.cost_usd == pytest.approx(0.002)

    @pytest.mark.asyncio
    async def test_quotes_only_for_facts_in_context(self, client, monkeypatch):
        auth, user_id = await _person(client)
        _, other_id = await _person(client, email="other@example.com")
        mine = await _add_fact(user_id, "the character kept falling through the floor", date(2026, 9, 17))
        flagged = await _add_fact(user_id, "this one is not accurate at all", date(2026, 9, 18), flagged=True)
        theirs = await _add_fact(other_id, "somebody else entirely said this", date(2026, 9, 19))
        monkeypatch.setattr(
            "app.services.conversation.stream_chat",
            _reply(
                "Look: {{quote:", str(mine.id), "}} and {{quote:", str(theirs.id), "}} ",
                f"{{{{quote:{flagged.id}}}}} {{{{quote:{uuid.uuid4()}}}}} today?<<<META>>>{{}}",
            ),
        )
        events = await _send(client, auth)
        quotes = [d for e, d in events if e == "quote"]
        assert [q["fact_id"] for q in quotes] == [str(mine.id)]
        assert quotes[0]["quote"] == "the character kept falling through the floor"
        assert quotes[0]["local_date"] == "2026-09-17"
        dump = json.dumps(events)
        assert str(theirs.id) not in dump and str(flagged.id) not in dump
        assert "somebody else" not in dump
        [answer] = await _rows(Message, Message.role == "assistant")
        assert answer.used_fact_ids == [str(mine.id)]
        assert [s["type"] for s in answer.content] == ["text", "quote", "text"]
        assert events[-1][1]["used_fact_ids"] == [str(mine.id)]

    @pytest.mark.asyncio
    async def test_broken_meta_does_not_break_the_reply(self, client, monkeypatch):
        monkeypatch.setattr(
            "app.services.conversation.stream_chat", _reply("Fine. What next?\n<<<META>>>\n{not json")
        )
        auth, _ = await _person(client)
        events = await _send(client, auth)
        assert events[-1][0] == "done"
        assert events[-1][1]["quick_replies"] == [] and events[-1][1]["intent"] == "normal"
        assert "META" not in json.dumps(events)

    @pytest.mark.asyncio
    async def test_model_failure_keeps_the_persons_message(self, client, monkeypatch):
        async def broken(messages, *, model=None, reasoning_effort=None):
            yield "Partial "
            raise llm.LLMError("boom")

        monkeypatch.setattr("app.services.conversation.stream_chat", broken)
        auth, _ = await _person(client)
        events = await _send(client, auth, "Keep this message please.")
        assert events[0][0] == "user_message"
        assert events[-1][0] == "error" and events[-1][1]["code"] == "llm_failed"
        assert [m.content_raw for m in await _rows(Message)] == ["Keep this message please."]

    @pytest.mark.asyncio
    async def test_flattery_and_questions_are_not_policed(self, client, monkeypatch):
        # v2.1: no hard reply rules; the reply is saved as written, no rule event.
        monkeypatch.setattr("app.services.conversation.stream_chat", _reply("Great job. Why? How?"))
        auth, _ = await _person(client)
        await _send(client, auth)
        [answer] = await _rows(Message, Message.role == "assistant")
        assert answer.content_raw == "Great job. Why? How?"
        assert await _rows(Event, Event.type == "reply_rule_violation") == []

    @pytest.mark.asyncio
    async def test_reply_marks_outreach_answered(self, client):
        auth, user_id = await _person(client)
        async with SessionLocal() as db:
            day = Conversation(user_id=user_id, local_date=_today(), started_by="ai")
            db.add(day)
            await db.flush()
            db.add(Outreach(user_id=user_id, conversation_id=day.id, topic="anchor", channel="push"))
            (await db.get(User, user_id)).outreach_unanswered = 2
            await db.commit()
        await _send(client, auth)
        [outreach] = await _rows(Outreach)
        assert outreach.replied_at is not None
        [user] = await _rows(User, User.id == user_id)
        assert user.outreach_unanswered == 0


class TestContext:
    @pytest.mark.asyncio
    async def test_context_carries_goal_threads_facts_and_days(self, client, monkeypatch):
        seen: list = []

        async def capture(messages, *, model=None, reasoning_effort=None):
            seen.append(messages)
            yield "Ok?"

        monkeypatch.setattr("app.services.conversation.stream_chat", capture)
        auth, user_id = await _person(client, locale="ru")
        _, other_id = await _person(client, email="other@example.com")
        fact = await _add_fact(user_id, "персонаж проваливался сквозь пол", date(2026, 9, 17))
        flagged = await _add_fact(user_id, "это неточная цитата из прошлого", date(2026, 9, 18), flagged=True)
        foreign = await _add_fact(other_id, "чужая цитата другого человека", date(2026, 9, 18))
        async with SessionLocal() as db:
            db.add(Goal(user_id=user_id, title="геймдев", why_text="хочу выпустить свою игру",
                        finish_line="релиз в Steam"))
            db.add(Thread(user_id=user_id, title="Оптимизация FPS", opened_on=date(2026, 9, 1)))
            db.add(Thread(user_id=user_id, title="Закрытая тема", status="closed", opened_on=date(2026, 9, 1)))
            db.add(Conversation(user_id=user_id, local_date=_today() - timedelta(days=1),
                                summary="Разобрался с рейкастами"))
            await db.commit()

        await _send(client, auth, "Сегодня нашёл утечку памяти.")
        [messages] = seen
        system = messages[0]["content"]
        assert messages[0]["role"] == "system"
        assert str(fact.id) in system and "персонаж проваливался сквозь пол" in system
        assert str(flagged.id) not in system and str(foreign.id) not in system
        assert "хочу выпустить свою игру" in system and "релиз в Steam" in system
        assert "Оптимизация FPS" in system and "Закрытая тема" not in system
        assert "Разобрался с рейкастами" in system
        assert "<<<META>>>" in system
        assert "«ты»" in system  # v2.1: the dialogue speaks «ты», no gendered forms
        assert messages[-1] == {"role": "user", "content": "Сегодня нашёл утечку памяти."}


class TestSendVoice:
    @pytest.mark.asyncio
    async def test_voice_is_transcribed_first_and_stored_by_message(self, client, audio_dir):
        auth, user_id = await _person(client)
        r = await _voice(client, auth)
        assert r.status_code == 200, r.text
        events = parse_sse(r.text)
        assert events[0][0] == "user_message" and events[-1][0] == "done"
        first = events[0][1]
        assert first["content"] == "Today I finally found the memory leak in the renderer."
        assert first["source"] == "voice" and first["detected_language"] == "en"
        [message] = await _rows(Message, Message.role == "user")
        assert str(message.id) == first["id"]
        assert Path(message.audio_path) == audio_dir / str(user_id) / f"{message.id}.webm"
        assert Path(message.audio_path).exists()
        assert message.words == [
            {"w": "Today", "start": 0.0, "end": 0.3},
            {"w": "I", "start": 0.3, "end": 0.4},
            {"w": "finally", "start": 0.4, "end": 0.8},
        ]
        assert message.audio_seconds == 3.5
        audio = await client.get(f"/api/messages/{message.id}/audio", headers=auth)
        assert audio.status_code == 200 and audio.content == b"\x1a\x45\xdf\xa3 fake webm"

    @pytest.mark.asyncio
    async def test_no_speech_ends_the_stream_and_leaves_nothing(self, client, monkeypatch, audio_dir):
        from app.services.stt import STTResult

        async def quiet(path, mime=None, locale=None):
            return STTResult("hm uh", 1.0, "en", 50, "mock")

        monkeypatch.setattr("app.services.conversation.transcribe", quiet)
        auth, user_id = await _person(client)
        events = parse_sse((await _voice(client, auth)).text)
        assert [(e, d["code"]) for e, d in events] == [("error", "no_speech")]
        assert await _rows(Message, Message.role == "user") == []
        assert list((audio_dir / str(user_id)).iterdir()) == []
        [day] = await _rows(Conversation, Conversation.user_id == user_id)
        assert day.counts_for_limit is False

    @pytest.mark.asyncio
    async def test_stt_failure(self, client, monkeypatch, audio_dir):
        async def broken(path, mime=None, locale=None):
            raise stt.STTError("Deepgram 500")

        monkeypatch.setattr("app.services.conversation.transcribe", broken)
        auth, user_id = await _person(client)
        events = parse_sse((await _voice(client, auth)).text)
        assert [(e, d["code"]) for e, d in events] == [("error", "stt_failed")]
        assert await _rows(Message) == []
        assert list((audio_dir / str(user_id)).iterdir()) == []
        [day] = await _rows(Conversation, Conversation.user_id == user_id)
        assert day.counts_for_limit is False


DICTATION = "/api/conversations/today/dictation"


async def _dictate(client, auth, data=b"\x1a\x45\xdf\xa3 fake webm", mime="audio/webm"):
    return await client.post(DICTATION, files={"audio": ("note.webm", data, mime)}, headers=auth)


class TestDictation:
    @pytest.mark.asyncio
    async def test_transcript_comes_back_and_the_checked_text_is_sent_as_voice(self, client, audio_dir):
        auth, user_id = await _person(client)
        r = await _dictate(client, auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["text"] == "Today I finally found the memory leak in the renderer."
        assert await _rows(Message) == []

        corrected = "Today I finally found the memory leak in the render loop."
        r = await client.post(
            MESSAGES, json={"text": corrected, "voice_draft_id": body["voice_draft_id"]}, headers=auth
        )
        events = parse_sse(r.text)
        assert events[0][1]["content"] == corrected and events[0][1]["source"] == "voice"
        [message] = await _rows(Message, Message.role == "user")
        assert message.content_raw == corrected
        assert Path(message.audio_path) == audio_dir / str(user_id) / f"{body['voice_draft_id']}.webm"
        assert message.words and message.audio_seconds == 3.5
        audio = await client.get(f"/api/messages/{message.id}/audio", headers=auth)
        assert audio.status_code == 200 and audio.content == b"\x1a\x45\xdf\xa3 fake webm"

    @pytest.mark.asyncio
    async def test_a_newer_recording_replaces_the_draft(self, client, audio_dir):
        auth, user_id = await _person(client)
        old = (await _dictate(client, auth)).json()["voice_draft_id"]
        new = (await _dictate(client, auth)).json()["voice_draft_id"]
        assert [p.stem for p in (audio_dir / str(user_id)).iterdir()] == [new]
        await client.post(MESSAGES, json={"text": "typed after all", "voice_draft_id": old}, headers=auth)
        [message] = await _rows(Message, Message.role == "user")
        assert message.source == "text" and message.audio_path is None

    @pytest.mark.asyncio
    async def test_a_stale_draft_is_dropped(self, client, monkeypatch, audio_dir):
        auth, user_id = await _person(client)
        draft_id = (await _dictate(client, auth)).json()["voice_draft_id"]
        monkeypatch.setattr(settings, "voice_draft_ttl_minutes", -1)
        await client.post(MESSAGES, json={"text": "sent much later", "voice_draft_id": draft_id}, headers=auth)
        [message] = await _rows(Message, Message.role == "user")
        assert message.source == "text"
        assert list((audio_dir / str(user_id)).iterdir()) == []

    @pytest.mark.asyncio
    async def test_no_speech_and_failure_leave_nothing(self, client, monkeypatch, audio_dir):
        from app.services.stt import STTResult

        async def quiet(path, mime=None, locale=None):
            return STTResult("hm uh", 1.0, "en", 50, "mock")

        async def broken(path, mime=None, locale=None):
            raise stt.STTError("Deepgram 500")

        auth, user_id = await _person(client)
        monkeypatch.setattr("app.services.dictation.transcribe", quiet)
        r = await _dictate(client, auth)
        assert r.status_code == 422 and r.json()["detail"]["code"] == "no_speech"
        monkeypatch.setattr("app.services.dictation.transcribe", broken)
        r = await _dictate(client, auth)
        assert r.status_code == 502 and r.json()["detail"]["code"] == "stt_failed"
        assert list((audio_dir / str(user_id)).iterdir()) == []

    @pytest.mark.asyncio
    async def test_checks_before_spending(self, client, monkeypatch):
        auth, _ = await _person(client)
        r = await _dictate(client, auth, mime="video/mp4")
        assert r.status_code == 415 and r.json()["detail"]["code"] == "unsupported_audio"
        r = await client.post(DICTATION, data={"text": "no file"}, headers=auth)
        assert r.status_code == 400 and r.json()["detail"]["code"] == "empty_audio"


class TestBeforeTheStream:
    @pytest.mark.asyncio
    async def test_codes(self, client, monkeypatch):
        auth, _ = await _person(client)

        def code(r, status):
            assert r.status_code == status, r.text
            return r.json()["detail"]["code"]

        assert code(await client.post(MESSAGES, json={"text": "   "}, headers=auth), 422) == "empty_text"
        assert code(await client.post(MESSAGES, json={}, headers=auth), 422) == "empty_text"
        too_long = "x" * (settings.max_text_chars + 1)
        assert code(await client.post(MESSAGES, json={"text": too_long}, headers=auth), 422) == "text_too_long"
        assert code(await _voice(client, auth, mime="video/mp4"), 415) == "unsupported_audio"
        assert code(await _voice(client, auth, data=b""), 400) == "empty_audio"
        monkeypatch.setattr(settings, "max_audio_mb", 0)
        assert code(await _voice(client, auth), 413) == "audio_too_large"
        assert await _rows(Message) == []

    @pytest.mark.asyncio
    async def test_unverified_email(self, client):
        auth, user_id = await _person(client)
        async with SessionLocal() as db:
            (await db.get(User, user_id)).email_verified = False
            await db.commit()
        r = await client.post(MESSAGES, json={"text": "hello there"}, headers=auth)
        assert r.status_code == 403 and r.json()["detail"]["code"] == "email_not_verified"

    @pytest.mark.asyncio
    async def test_second_message_while_replying(self, client):
        from app.services import conversation

        auth, user_id = await _person(client)
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            pending = await conversation.prepare_message(db, user, text="first one", audio=None)
        r = await client.post(MESSAGES, json={"text": "second one"}, headers=auth)
        assert r.status_code == 409 and r.json()["detail"]["code"] == "reply_in_progress"
        conversation.release_if_unstarted(pending)
        await _send(client, auth, "now it works")

    @pytest.mark.asyncio
    async def test_needs_sign_in(self, client):
        assert (await client.post(MESSAGES, json={"text": "hi"})).status_code == 401
        assert (await client.get("/api/conversations/today")).status_code == 401


class TestDisconnect:
    @pytest.mark.asyncio
    async def test_reply_is_saved_whole_after_the_client_leaves(self, client, monkeypatch):
        from app.services import conversation

        async def slow(messages, *, model=None, reasoning_effort=None):
            for piece in ["One ", "two ", "three ", "four?"]:
                await asyncio.sleep(0.02)
                yield piece

        monkeypatch.setattr(conversation, "stream_chat", slow)
        auth, user_id = await _person(client)
        async with SessionLocal() as db:
            user = await db.get(User, user_id)
            prepared = await conversation.prepare_message(db, user, text="I am leaving early", audio=None)
        stream = conversation.stream_reply(prepared)
        first = await stream.__anext__()
        assert first.startswith("event: user_message")
        await stream.aclose()  # the tab is closed

        saved: list = []
        for _ in range(200):
            saved = await _rows(Message, Message.role == "assistant")
            if saved:
                break
            await asyncio.sleep(0.02)
        assert [m.content_raw for m in saved] == ["One two three four?"]
        # The conversation is free again.
        await _send(client, auth, "back again")


# ------------------------------------------------------------------ days, search, the rest


async def _day_with(user_id, day, texts_by_role, *, counts=True, summary=None, audio_path=None):
    """A stored conversation with messages [(role, text)]; returns (conversation, messages)."""
    async with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, local_date=day, counts_for_limit=counts, summary=summary)
        db.add(conversation)
        await db.flush()
        messages = []
        for i, (role, text) in enumerate(texts_by_role):
            message = Message(
                conversation_id=conversation.id,
                user_id=user_id,
                role=role,
                source="voice" if audio_path and role == "user" else "text",
                content_raw=text,
                content=[{"type": "text", "text": text}],
                audio_path=audio_path if role == "user" else None,
                audio_mime="audio/webm" if audio_path and role == "user" else None,
                created_at=datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=i),
            )
            db.add(message)
            messages.append(message)
        await db.commit()
        return conversation, messages


class TestFeedAndDay:
    @pytest.mark.asyncio
    async def test_feed_lists_talked_days_newest_first_with_threads(self, client):
        auth, user_id = await _person(client)
        other, other_id = await _person(client, email="other@example.com")
        _, (said, _) = await _day_with(user_id, date(2026, 10, 1), [("user", "fps drops"), ("assistant", "why?")],
                                      summary="FPS trouble")
        await _day_with(user_id, date(2026, 10, 3), [("user", "better today")])
        await _day_with(user_id, date(2026, 10, 4), [("assistant", "unanswered outreach")], counts=False)
        await _day_with(other_id, date(2026, 10, 2), [("user", "someone else")])
        async with SessionLocal() as db:
            thread = Thread(user_id=user_id, title="FPS", opened_on=date(2026, 10, 1))
            gone = Thread(user_id=user_id, title="Deleted one", status="deleted", opened_on=date(2026, 10, 1))
            db.add_all([thread, gone])
            await db.flush()
            for t in (thread, thread, gone):
                db.add(Fact(user_id=user_id, message_id=said.id, local_date=date(2026, 10, 1), type="struggle",
                            text="t", quote="fps drops", thread_id=t.id))
            await db.commit()

        days = (await client.get("/api/conversations", headers=auth)).json()
        assert [d["local_date"] for d in days] == ["2026-10-03", "2026-10-01"]
        assert days[1] == {
            "local_date": "2026-10-01",
            "summary": "FPS trouble",
            "started_by": "user",
            "threads": [{"id": str(thread.id), "title": "FPS", "status": "open"}],
            "message_count": 2,
        }
        older = (await client.get("/api/conversations?before=2026-10-03&limit=5", headers=auth)).json()
        assert [d["local_date"] for d in older] == ["2026-10-01"]
        assert [d["local_date"] for d in (await client.get("/api/conversations", headers=other)).json()] == ["2026-10-02"]

    @pytest.mark.asyncio
    async def test_one_day_and_isolation(self, client):
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        conversation, _ = await _day_with(user_id, date(2026, 10, 1), [("user", "hello"), ("assistant", "hi?")])
        r = await client.get("/api/conversations/2026-10-01", headers=auth)
        assert r.status_code == 200
        assert r.json()["id"] == str(conversation.id)
        assert [m["role"] for m in r.json()["messages"]] == ["user", "assistant"]
        for headers, day in ((other, "2026-10-01"), (auth, "2026-10-02")):
            r = await client.get(f"/api/conversations/{day}", headers=headers)
            assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found"


class TestDeleteDay:
    @pytest.mark.asyncio
    async def test_delete_removes_messages_files_and_facts(self, client, audio_dir):
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        clip = audio_dir / str(user_id) / "clip.webm"
        clip.parent.mkdir(parents=True)
        clip.write_bytes(b"voice")
        conversation, (said, _) = await _day_with(
            user_id, date(2026, 10, 1), [("user", "fps drops a lot"), ("assistant", "why?")], audio_path=str(clip)
        )
        fact = await _add_fact(user_id, "fps drops a lot", date(2026, 10, 1), message_id=said.id)
        later = await _add_fact(user_id, "fps is fine now", date(2026, 10, 20))
        async with SessionLocal() as db:
            thread = Thread(user_id=user_id, title="FPS", opened_on=date(2026, 10, 1), opened_fact_id=fact.id)
            db.add(thread)
            db.add(Pair(user_id=user_id, then_fact_id=fact.id, now_fact_id=later.id, theme="FPS", source="similarity"))
            goal = Goal(user_id=user_id, title="gamedev", why_message_id=said.id)
            db.add(goal)
            await db.commit()

        r = await client.delete("/api/conversations/2026-10-01", headers=other)
        assert r.status_code == 404 and clip.exists()

        r = await client.delete("/api/conversations/2026-10-01", headers=auth)
        assert r.status_code == 204
        assert not clip.exists()
        assert await _rows(Conversation, Conversation.id == conversation.id) == []
        assert await _rows(Message, Message.conversation_id == conversation.id) == []
        assert [f.id for f in await _rows(Fact, Fact.user_id == user_id)] == [later.id]
        assert await _rows(Pair) == []
        [kept] = await _rows(Thread, Thread.id == thread.id)
        assert kept.opened_fact_id is None
        [g] = await _rows(Goal, Goal.id == goal.id)
        assert g.why_message_id is None
        assert (await client.delete("/api/conversations/2026-10-01", headers=auth)).status_code == 404

    @pytest.mark.asyncio
    async def test_deleted_today_comes_back_empty(self, client):
        auth, _ = await _person(client)
        await _send(client, auth)
        assert (await client.delete(f"/api/conversations/{_today().isoformat()}", headers=auth)).status_code == 204
        body = (await client.get("/api/conversations/today", headers=auth)).json()
        assert body["kind"] == "daily" and body["messages"] == []


class TestSearch:
    @pytest.mark.asyncio
    async def test_search_own_messages_only(self, client):
        auth, user_id = await _person(client)
        other, other_id = await _person(client, email="other@example.com")
        _, (mine, _) = await _day_with(user_id, date(2026, 10, 1), [("user", "Fixed the Memory leak at last"),
                                                                      ("assistant", "memory leak? nice")])
        await _day_with(other_id, date(2026, 10, 2), [("user", "my memory leak too")])
        hits = (await client.get("/api/search?q=memory LEAK", headers=auth)).json()
        assert hits == [{"local_date": "2026-10-01", "message_id": str(mine.id),
                         "snippet": "Fixed the Memory leak at last"}]
        assert (await client.get("/api/search?q=%25", headers=auth)).json() == []
        assert (await client.get("/api/search?q=", headers=auth)).json() == []


class TestMessageFactThread:
    @pytest.mark.asyncio
    async def test_audio_only_to_its_owner(self, client, audio_dir):
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        clip = audio_dir / "clip.webm"
        clip.parent.mkdir(parents=True)
        clip.write_bytes(b"voice")
        _, (said, reply) = await _day_with(user_id, date(2026, 10, 1), [("user", "hi"), ("assistant", "yo?")],
                                          audio_path=str(clip))
        assert (await client.get(f"/api/messages/{said.id}/audio", headers=auth)).content == b"voice"
        assert (await client.get(f"/api/messages/{said.id}/audio", headers=other)).status_code == 404
        assert (await client.get(f"/api/messages/{reply.id}/audio", headers=auth)).status_code == 404

    @pytest.mark.asyncio
    async def test_rating(self, client):
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        _, (said, reply) = await _day_with(user_id, date(2026, 10, 1), [("user", "hi"), ("assistant", "yo?")])
        url = f"/api/messages/{reply.id}/rating"
        assert (await client.post(url, json={"rating": "helped"}, headers=other)).status_code == 404
        assert (await client.post(url, json={"rating": "great"}, headers=auth)).status_code == 422
        assert (await client.post(url, json={"rating": "not_it"}, headers=auth)).status_code == 204
        [stored] = await _rows(Message, Message.id == reply.id)
        assert stored.rating == "not_it"
        r = await client.post(f"/api/messages/{said.id}/rating", json={"rating": "helped"}, headers=auth)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_flagged_fact_leaves_the_context(self, client, monkeypatch):
        seen: list = []

        async def capture(messages, *, model=None, reasoning_effort=None):
            seen.append(messages[0]["content"])
            yield "Ok?"

        monkeypatch.setattr("app.services.conversation.stream_chat", capture)
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        fact = await _add_fact(user_id, "a quote that is wrong", date(2026, 9, 1))
        assert (await client.post(f"/api/facts/{fact.id}/flag", headers=other)).status_code == 404
        assert (await client.post(f"/api/facts/{fact.id}/flag", headers=auth)).status_code == 204
        [stored] = await _rows(Fact, Fact.id == fact.id)
        assert stored.flagged_at is not None
        await _send(client, auth)
        assert "a quote that is wrong" not in seen[0]

    @pytest.mark.asyncio
    async def test_thread_update(self, client):
        auth, user_id = await _person(client)
        other, _ = await _person(client, email="other@example.com")
        async with SessionLocal() as db:
            thread = Thread(user_id=user_id, title="FPS", opened_on=date(2026, 9, 1))
            db.add(thread)
            await db.commit()
        url = f"/api/threads/{thread.id}"
        assert (await client.patch(url, json={"status": "closed"}, headers=other)).status_code == 404
        r = await client.patch(url, json={"status": "closed", "title": "FPS drops"}, headers=auth)
        assert r.status_code == 200
        body = r.json()
        assert body["status"] == "closed" and body["title"] == "FPS drops"
        assert body["closed_on"] == _today().isoformat()
        assert (await client.patch(url, json={"status": "open"}, headers=auth)).status_code == 422
        assert (await client.patch(url, json={"status": "deleted"}, headers=auth)).json()["status"] == "deleted"
        assert (await client.patch(f"/api/threads/{uuid.uuid4()}", json={}, headers=auth)).status_code == 404


class TestCalendar:
    @pytest.mark.asyncio
    async def test_green_days_in_range(self, client):
        auth, user_id = await _person(client)
        other, other_id = await _person(client, email="other@example.com")
        await _day_with(user_id, date(2026, 10, 2), [("user", "x")])
        await _day_with(user_id, date(2026, 10, 3), [("assistant", "unanswered")], counts=False)
        await _day_with(other_id, date(2026, 10, 4), [("user", "y")])
        days = (await client.get("/api/calendar?from=2026-10-01&to=2026-10-05", headers=auth)).json()
        assert days == [
            {"local_date": "2026-10-01", "active": False},
            {"local_date": "2026-10-02", "active": True},
            {"local_date": "2026-10-03", "active": False},
            {"local_date": "2026-10-04", "active": False},
            {"local_date": "2026-10-05", "active": False},
        ]
        theirs = (await client.get("/api/calendar?from=2026-10-01&to=2026-10-05", headers=other)).json()
        assert [d["local_date"] for d in theirs if d["active"]] == ["2026-10-04"]

    @pytest.mark.asyncio
    async def test_range_limits(self, client):
        auth, _ = await _person(client)
        ok = await client.get("/api/calendar?from=2026-01-01&to=2026-03-03", headers=auth)  # 62 days
        assert ok.status_code == 200 and len(ok.json()) == 62
        for query in ("from=2026-01-01&to=2026-03-04", "from=2026-03-02&to=2026-03-01"):
            r = await client.get(f"/api/calendar?{query}", headers=auth)
            assert r.status_code == 400 and r.json()["detail"]["code"] == "bad_range"
