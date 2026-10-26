"""Stage 3: memory - verified facts, threads, word alignment, embeddings, "then -> now"
pairs, the extraction loops and GET /api/memory.

The extraction model and the embeddings are fakes (conftest.py patches
`memory.complete_json` and `memory.embed`); `llm.embed` itself talks to an httpx
MockTransport.
"""

import asyncio
import copy
import json
import uuid
from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import func, select

from app.config import settings
from app.db import SessionLocal
from app.models import Conversation, Event, Fact, Goal, Message, Pair, Thread, User
from app.services import costs, llm, memory
from app.services.llm import LLMError, LLMResult

from conftest import register

TZ = "America/Los_Angeles"
DAY = date(2026, 10, 12)
LONG_AGO = datetime(2026, 1, 1, tzinfo=timezone.utc)


# ------------------------------------------------------------------ helpers


async def _person(client, email="person@example.com", tz=TZ) -> tuple[dict, uuid.UUID]:
    auth = await register(client, email=email, timezone=tz)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        return auth, user.id


async def _day(
    user_id, day, texts, *, at: datetime = LONG_AGO, words=None, extracted_at=None
) -> tuple[uuid.UUID, list[uuid.UUID]]:
    """A conversation on `day` with the person's messages, the last one sent at `at`."""
    async with SessionLocal() as db:
        conversation = Conversation(
            user_id=user_id, local_date=day, counts_for_limit=True,
            memory_extracted_at=extracted_at,
        )
        db.add(conversation)
        await db.flush()
        ids = []
        for i, text in enumerate(texts):
            message = Message(
                conversation_id=conversation.id,
                user_id=user_id,
                role="user",
                source="voice" if words else "text",
                content_raw=text,
                content=[{"type": "text", "text": text}],
                words=words,
                created_at=at - timedelta(seconds=len(texts) - i),
            )
            db.add(message)
            await db.flush()
            ids.append(message.id)
        await db.commit()
        return conversation.id, ids


def _result(facts=(), open=(), mention=(), close=(), summary="A day") -> dict:
    return {
        "facts": list(facts),
        "threads": {"open": list(open), "mention": list(mention), "close": list(close)},
        "day_summary": summary,
    }


def _model(monkeypatch, result: dict, theme: str = "Finding leaks") -> list[dict]:
    """The extraction model answers `result`; a pair's theme request answers `theme`."""
    calls: list[dict] = []

    async def fake(system, user, schema):
        if "theme" in (schema.get("properties") or {}):
            calls.append({"kind": "theme", "user": user})
            return LLMResult(data={"theme": theme}, model="mock", elapsed_ms=1)
        calls.append({"kind": "memory", "user": user, "system": system})
        return LLMResult(data=copy.deepcopy(result), model="mock", elapsed_ms=1)

    monkeypatch.setattr(memory, "complete_json", fake)
    return calls


def _fact(message_id, type_, quote, text="a fact") -> dict:
    return {"message_id": str(message_id), "type": type_, "text": text, "quote": quote}


async def _facts(user_id) -> list[Fact]:
    async with SessionLocal() as db:
        return list(
            (
                await db.execute(
                    select(Fact).where(Fact.user_id == user_id).order_by(Fact.created_at)
                )
            ).scalars()
        )


async def _add_fact(user_id, type_, quote, day, *, embedding=None, thread_id=None,
                    message_id=None, flagged=False) -> Fact:
    async with SessionLocal() as db:
        fact = Fact(
            user_id=user_id, message_id=message_id, local_date=day, type=type_,
            text=f"{type_} fact", quote=quote, embedding=embedding, thread_id=thread_id,
            flagged_at=datetime.now(timezone.utc) if flagged else None,
        )
        db.add(fact)
        await db.commit()
        return fact


async def _reset(conversation_id) -> None:
    async with SessionLocal() as db:
        conversation = await db.get(Conversation, conversation_id)
        conversation.memory_extracted_at = None
        await db.commit()


# ------------------------------------------------------------------ providers


class TestEmbedProvider:
    @pytest.mark.asyncio
    async def test_one_request_vectors_in_order_and_cost(self, monkeypatch):
        seen: list = []

        def handler(request: httpx.Request) -> httpx.Response:
            seen.append((str(request.url), json.loads(request.content)))
            return httpx.Response(200, json={
                "model": "embed-small",
                "data": [
                    {"index": 1, "embedding": [0.0, 1.0]},
                    {"index": 0, "embedding": [1.0, 0.0]},
                ],
                "usage": {"prompt_tokens": 1000, "total_tokens": 1000},
            })

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        monkeypatch.setattr(settings, "embedding_price_per_1m", 2.0)
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))

        with costs.track() as usage:
            vectors = await llm.embed(["first", "second"])

        assert vectors == [[1.0, 0.0], [0.0, 1.0]]
        [(url, payload)] = seen
        assert url.endswith("/embeddings")
        assert payload == {"model": "embed-small", "input": ["first", "second"]}
        assert usage.llm_usd == pytest.approx(0.002)  # 1000 tokens * $2 / 1M

    @pytest.mark.asyncio
    async def test_provider_error_is_llm_error(self, monkeypatch):
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(400, json={"error": {"message": "bad model"}})

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        with pytest.raises(LLMError):
            await llm.embed(["text"])


class TestMissingPrices:
    def test_unset_chat_and_safety_models_inherit_openai_model(self, monkeypatch):
        monkeypatch.setattr(settings, "openai_model", "base-model")
        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "chat_model", None)
        monkeypatch.setattr(settings, "safety_model", "")
        monkeypatch.setattr(settings, "chat_price_input_per_1m", 0.0)
        monkeypatch.setattr(settings, "chat_price_output_per_1m", 0.0)
        monkeypatch.setattr(settings, "safety_price_input_per_1m", 0.0)
        monkeypatch.setattr(settings, "safety_price_output_per_1m", 0.0)
        monkeypatch.setattr(settings, "embedding_model", None)
        assert costs.missing_prices() == []


# ------------------------------------------------------------------ pure helpers


# "Сегодня, наконец, нашёл утечку памяти в рендере." - Deepgram's punctuated words.
WORDS = [
    {"w": "Сегодня,", "start": 0.0, "end": 0.48},
    {"w": "наконец,", "start": 0.5, "end": 0.9},
    {"w": "нашёл", "start": 1.0, "end": 1.31},
    {"w": "утечку", "start": 1.35, "end": 1.8},
    {"w": "памяти", "start": 1.82, "end": 2.2},
    {"w": "в", "start": 2.25, "end": 2.3},
    {"w": "рендере.", "start": 2.32, "end": 2.95},
]


class TestAlignQuote:
    def test_exact_words_give_milliseconds(self):
        assert memory.align_quote(WORDS, "нашёл утечку памяти") == (1000, 2200)
        # Punctuation and case do not matter.
        assert memory.align_quote(WORDS, "Памяти в рендере!") == (1820, 2950)

    def test_no_exact_alignment_is_none(self):
        assert memory.align_quote(WORDS, "нашёл утечку памят") is None
        assert memory.align_quote(WORDS, "нашёл баг в рендере") is None
        assert memory.align_quote([], "нашёл утечку памяти") is None


class TestCosine:
    def test_known_values(self):
        assert memory.cosine([1.0, 0.0], [1.0, 0.0]) == pytest.approx(1.0)
        assert memory.cosine([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)
        assert memory.cosine([3.0, 4.0], [4.0, 3.0]) == pytest.approx(24 / 25)
        assert memory.cosine([0.0, 0.0], [1.0, 0.0]) == 0.0
        assert memory.cosine([1.0, 0.0], [1.0, 0.0, 0.0]) == 0.0


# ------------------------------------------------------------------ extract_memory


class TestExtractFacts:
    @pytest.mark.asyncio
    async def test_unverified_quote_and_foreign_message_are_dropped_and_counted(
        self, client, monkeypatch
    ):
        _, user_id = await _person(client)
        _, [other_day_message] = await _day(user_id, DAY - timedelta(days=1),
                                            ["I fixed the shader compile error yesterday."])
        conversation_id, [m1, m2] = await _day(user_id, DAY, [
            "Today I finally found the memory leak in the renderer.",
            "FPS drops to 20 when there are many enemies.",
        ])
        _model(monkeypatch, _result(
            facts=[
                _fact(m1, "achievement", "found the memory leak in the renderer"),
                _fact(m2, "struggle", "the game crashes on every level load"),  # invented
                _fact(other_day_message, "achievement", "fixed the shader compile error"),
                _fact(m2, "struggle", "drops to 20 when there are many enemies"),
            ],
            summary="x" * 300,
        ))

        await memory.extract_memory(conversation_id)

        facts = await _facts(user_id)
        assert [(f.type, f.quote, f.message_id) for f in facts] == [
            ("achievement", "found the memory leak in the renderer", m1),
            ("struggle", "drops to 20 when there are many enemies", m2),
        ]
        assert all(f.local_date == DAY and f.origin == "conversation" for f in facts)
        async with SessionLocal() as db:
            conversation = await db.get(Conversation, conversation_id)
            assert conversation.summary == "x" * 200
            assert conversation.memory_extracted_at is not None
            [event] = (
                await db.execute(select(Event).where(Event.type == "memory_dropped_facts"))
            ).scalars().all()
        assert event.user_id == user_id
        assert event.payload["dropped"] == 2
        assert event.payload["conversation_id"] == str(conversation_id)

    @pytest.mark.asyncio
    async def test_rerun_does_not_duplicate_facts_including_first_conversation_ones(
        self, client, monkeypatch
    ):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(user_id, DAY, [
            "Today I finally found the memory leak in the renderer. Five years ago I could not draw at all.",
        ])
        # Created by the first conversation's comparison before extraction ran.
        await _add_fact(user_id, "achievement", "Found the memory leak in the renderer!", DAY,
                        message_id=m1)
        _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "found the memory leak in the renderer"),
            _fact(m1, "struggle", "five years ago I could not draw at all"),
        ]))

        await memory.extract_memory(conversation_id)
        await _reset(conversation_id)
        await memory.extract_memory(conversation_id)

        quotes = sorted(f.quote for f in await _facts(user_id))
        assert quotes == [
            "Found the memory leak in the renderer!",
            "five years ago I could not draw at all",
        ]
        async with SessionLocal() as db:
            assert not (
                await db.execute(select(Event).where(Event.type == "memory_dropped_facts"))
            ).scalars().all()

    @pytest.mark.asyncio
    async def test_voice_quote_gets_audio_range(self, client, monkeypatch):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(
            user_id, DAY, ["Сегодня, наконец, нашёл утечку памяти в рендере."], words=WORDS
        )
        _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "нашёл утечку памяти в рендере"),
            _fact(m1, "learned", "Сегодня наконец нашёл утечку памят"),  # fuzzy: verified, not aligned
        ]))

        await memory.extract_memory(conversation_id)

        exact, fuzzy = await _facts(user_id)
        assert (exact.audio_start_ms, exact.audio_end_ms) == (1000, 2950)
        assert (fuzzy.audio_start_ms, fuzzy.audio_end_ms) == (None, None)


class TestThreads:
    @pytest.mark.asyncio
    async def test_open_needs_a_verified_struggle(self, client, monkeypatch):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(user_id, DAY, [
            "FPS drops to 20 when there are many enemies, but I fixed the camera jitter.",
        ])
        _model(monkeypatch, _result(
            facts=[
                _fact(m1, "struggle", "FPS drops to 20 when there are many enemies"),
                _fact(m1, "achievement", "I fixed the camera jitter"),
                _fact(m1, "struggle", "the build server is down for a week"),  # dropped
            ],
            open=[
                {"title": "FPS optimisation", "fact_index": 0},
                {"title": "Camera", "fact_index": 1},       # not a struggle
                {"title": "Build server", "fact_index": 2},  # its fact was dropped
                {"title": "Nowhere", "fact_index": 9},       # no such fact
            ],
        ))

        await memory.extract_memory(conversation_id)

        async with SessionLocal() as db:
            [thread] = (await db.execute(select(Thread))).scalars().all()
            struggle = (
                await db.execute(select(Fact).where(Fact.type == "struggle"))
            ).scalar_one()
        assert thread.title == "FPS optimisation" and thread.status == "open"
        assert thread.opened_fact_id == struggle.id and struggle.thread_id == thread.id
        assert thread.opened_on == DAY and thread.last_mentioned_on == DAY

    @pytest.mark.asyncio
    async def test_close_only_own_open_thread_with_achievement_or_learned(
        self, client, monkeypatch
    ):
        _, user_id = await _person(client)
        _, other_id = await _person(client, email="other@example.com")
        async with SessionLocal() as db:
            own = Thread(user_id=user_id, title="FPS", opened_on=DAY - timedelta(days=3))
            mentioned = Thread(user_id=user_id, title="Shaders", opened_on=DAY - timedelta(days=3),
                               last_mentioned_on=DAY - timedelta(days=3))
            foreign = Thread(user_id=other_id, title="Not yours", opened_on=DAY - timedelta(days=3))
            closed = Thread(user_id=user_id, title="Old", status="closed",
                            opened_on=DAY - timedelta(days=30), closed_on=DAY - timedelta(days=20))
            db.add_all([own, mentioned, foreign, closed])
            await db.commit()
        conversation_id, [m1] = await _day(user_id, DAY, [
            "I fixed the FPS drops with object pooling. Still fighting the shader compile times.",
        ])
        result = _result(
            facts=[
                _fact(m1, "achievement", "I fixed the FPS drops with object pooling"),
                _fact(m1, "struggle", "Still fighting the shader compile times"),
            ],
            mention=[{"thread_id": str(mentioned.id), "fact_index": 1}],
            close=[
                {"thread_id": str(foreign.id), "fact_index": 0},      # someone else's
                {"thread_id": str(uuid.uuid4()), "fact_index": 0},    # invented
                {"thread_id": str(closed.id), "fact_index": 0},       # not open
                {"thread_id": str(mentioned.id), "fact_index": 1},    # a struggle cannot close
            ],
        )
        _model(monkeypatch, result)

        await memory.extract_memory(conversation_id)

        async with SessionLocal() as db:
            rows = {t.id: t for t in (await db.execute(select(Thread))).scalars().all()}
        assert rows[foreign.id].status == "open" and rows[foreign.id].closed_fact_id is None
        assert rows[closed.id].closed_on == DAY - timedelta(days=20)
        assert rows[closed.id].closed_fact_id is None
        assert rows[mentioned.id].status == "open"
        assert rows[mentioned.id].last_mentioned_on == DAY
        assert rows[own.id].status == "open" and rows[own.id].last_mentioned_on is None
        assert len(rows) == 4

        # Now the real close of their own thread.
        await _reset(conversation_id)
        result["threads"] = {"open": [], "mention": [],
                             "close": [{"thread_id": str(own.id), "fact_index": 0}]}
        _model(monkeypatch, result)
        await memory.extract_memory(conversation_id)

        async with SessionLocal() as db:
            thread = await db.get(Thread, own.id)
            achievement = (
                await db.execute(select(Fact).where(Fact.type == "achievement"))
            ).scalar_one()
        assert thread.status == "closed" and thread.closed_on == DAY
        assert thread.closed_fact_id == achievement.id
        assert thread.last_mentioned_on == DAY
        assert achievement.thread_id == own.id


class TestEmbeddings:
    @pytest.mark.asyncio
    async def test_new_facts_embedded_in_one_request(self, client, monkeypatch):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(user_id, DAY, [
            "Today I finally found the memory leak in the renderer and learned the profiler.",
        ])
        _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "found the memory leak in the renderer"),
            _fact(m1, "learned", "learned the profiler"),
        ]))
        calls: list[list[str]] = []

        async def embed(texts):
            calls.append(texts)
            return [[float(i), 1.0] for i in range(len(texts))]

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")

        await memory.extract_memory(conversation_id)

        assert len(calls) == 1 and len(calls[0]) == 2
        assert [f.embedding for f in await _facts(user_id)] == [[0.0, 1.0], [1.0, 1.0]]

    @pytest.mark.asyncio
    async def test_embedding_failure_does_not_break_extraction(self, client, monkeypatch):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(user_id, DAY, [
            "Today I finally found the memory leak in the renderer.",
        ])
        _model(monkeypatch, _result(
            facts=[_fact(m1, "achievement", "found the memory leak in the renderer")],
            summary="Found the leak",
        ))

        async def broken(texts):
            raise LLMError("embeddings are down")

        monkeypatch.setattr(memory, "embed", broken)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")

        await memory.extract_memory(conversation_id)

        [fact] = await _facts(user_id)
        assert fact.embedding is None
        async with SessionLocal() as db:
            conversation = await db.get(Conversation, conversation_id)
        assert conversation.summary == "Found the leak"
        assert conversation.memory_extracted_at is not None

    @pytest.mark.asyncio
    async def test_no_embedding_model_no_request(self, client, monkeypatch):
        _, user_id = await _person(client)
        conversation_id, [m1] = await _day(user_id, DAY, [
            "Today I finally found the memory leak in the renderer.",
        ])
        _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "found the memory leak in the renderer"),
        ]))

        async def must_not_run(texts):
            raise AssertionError("embed called without EMBEDDING_MODEL")

        monkeypatch.setattr(memory, "embed", must_not_run)
        monkeypatch.setattr(settings, "embedding_model", None)

        await memory.extract_memory(conversation_id)
        [fact] = await _facts(user_id)
        assert fact.embedding is None


# ------------------------------------------------------------------ relevant_facts


class TestRelevantFacts:
    @pytest.mark.asyncio
    async def test_by_meaning_without_flagged_or_foreign(self, client, monkeypatch):
        _, user_id = await _person(client)
        _, other_id = await _person(client, email="other@example.com")
        near = await _add_fact(user_id, "struggle", "near quote", DAY - timedelta(days=30),
                               embedding=[1.0, 0.0])
        far = await _add_fact(user_id, "struggle", "far quote", DAY, embedding=[0.0, 1.0])
        await _add_fact(user_id, "struggle", "flagged quote", DAY, embedding=[1.0, 0.0],
                        flagged=True)
        await _add_fact(other_id, "struggle", "foreign quote", DAY, embedding=[1.0, 0.0])

        async def embed(texts):
            return [[0.9, 0.1]]

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        async with SessionLocal() as db:
            facts = await memory.relevant_facts(db, user_id, "the leak again", 1)
            both = await memory.relevant_facts(db, user_id, "the leak again", 5)
        assert [f.id for f in facts] == [near.id]
        assert [f.id for f in both] == [near.id, far.id]

    @pytest.mark.asyncio
    async def test_by_date_without_embeddings_or_on_error(self, client, monkeypatch):
        _, user_id = await _person(client)
        old = await _add_fact(user_id, "struggle", "old quote", DAY - timedelta(days=30),
                              embedding=[1.0, 0.0])
        new = await _add_fact(user_id, "struggle", "new quote", DAY, embedding=[0.0, 1.0])
        await _add_fact(user_id, "struggle", "flagged quote", DAY + timedelta(days=1),
                        flagged=True)

        async def embed(texts):
            return [[1.0, 0.0]]

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", None)
        async with SessionLocal() as db:
            assert [f.id for f in await memory.relevant_facts(db, user_id, "x", 5)] == [
                new.id, old.id
            ]

        async def broken(texts):
            raise LLMError("down")

        monkeypatch.setattr(memory, "embed", broken)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        async with SessionLocal() as db:
            assert [f.id for f in await memory.relevant_facts(db, user_id, "x", 1)] == [new.id]

    @pytest.mark.asyncio
    async def test_reply_context_uses_facts_closest_by_meaning(self, client, monkeypatch):
        seen: list = []

        async def capture(messages, *, model=None, reasoning_effort=None):
            seen.append(messages)
            yield "Ok?"

        monkeypatch.setattr("app.services.conversation.stream_chat", capture)
        auth, user_id = await _person(client)
        async with SessionLocal() as db:
            (await db.get(User, user_id)).first_conversation_done = True
            await db.commit()
        near = await _add_fact(user_id, "struggle", "the leak in the renderer again",
                               date(2026, 1, 1), embedding=[1.0, 0.0])
        recent = await _add_fact(user_id, "struggle", "the music is too loud",
                                 date(2026, 9, 1), embedding=[0.0, 1.0])

        async def embed(texts):
            return [[1.0, 0.05]]

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        monkeypatch.setattr(settings, "context_facts", 1)

        r = await client.post("/api/conversations/today/messages",
                              json={"text": "The renderer leaks memory again."}, headers=auth)
        assert r.status_code == 200, r.text
        [messages] = seen
        system = messages[0]["content"]
        assert str(near.id) in system and str(recent.id) not in system


# ------------------------------------------------------------------ pairs


class TestPairs:
    @pytest.mark.asyncio
    async def test_closed_thread_older_than_min_days_makes_one_pair(self, client, monkeypatch):
        _, user_id = await _person(client)
        first_day = DAY - timedelta(days=10)
        c1, [m1] = await _day(user_id, first_day, ["The character keeps falling through the floor."])
        _model(monkeypatch, _result(
            facts=[_fact(m1, "struggle", "keeps falling through the floor")],
            open=[{"title": "Collisions", "fact_index": 0}],
        ))
        await memory.extract_memory(c1)
        async with SessionLocal() as db:
            thread = (await db.execute(select(Thread))).scalar_one()

        c2, [m2] = await _day(user_id, DAY, ["I fixed the collisions, nobody falls through anymore."])
        _model(monkeypatch, _result(
            facts=[_fact(m2, "achievement", "I fixed the collisions")],
            close=[{"thread_id": str(thread.id), "fact_index": 0}],
        ))
        await memory.extract_memory(c2)

        async with SessionLocal() as db:
            [pair] = (await db.execute(select(Pair))).scalars().all()
            then = await db.get(Fact, pair.then_fact_id)
            now = await db.get(Fact, pair.now_fact_id)
            thread = await db.get(Thread, thread.id)
        assert pair.source == "thread_closed" and pair.theme == "Collisions"
        assert pair.user_id == user_id and pair.recalled is False
        assert (then.quote, now.quote) == ("keeps falling through the floor", "I fixed the collisions")

        # Again: the same closed thread does not make a second card.
        await _reset(c2)
        await memory.extract_memory(c2)
        async with SessionLocal() as db:
            assert await memory.make_pairs(db, user_id, [now], [thread]) == []
            await db.commit()
            assert (await db.execute(select(func.count()).select_from(Pair))).scalar_one() == 1

    @pytest.mark.asyncio
    async def test_thread_closed_too_soon_makes_no_pair(self, client, monkeypatch):
        _, user_id = await _person(client)
        then = await _add_fact(user_id, "struggle", "falls through the floor", DAY - timedelta(days=3))
        now = await _add_fact(user_id, "achievement", "fixed the collisions", DAY)
        async with SessionLocal() as db:
            thread = Thread(user_id=user_id, title="Collisions", status="closed",
                            opened_fact_id=then.id, closed_fact_id=now.id,
                            opened_on=then.local_date, closed_on=DAY)
            db.add(thread)
            await db.flush()
            assert await memory.make_pairs(db, user_id, [], [thread]) == []

    @pytest.mark.asyncio
    async def test_similar_old_struggle_makes_one_similarity_pair(self, client, monkeypatch):
        _, user_id = await _person(client)
        old = await _add_fact(user_id, "struggle", "I cannot hear the past tense",
                              DAY - timedelta(days=12), embedding=[1.0, 0.0, 0.0])
        # Closer in meaning, but only 3 days old: not a "then".
        await _add_fact(user_id, "struggle", "past tense is still hard",
                        DAY - timedelta(days=3), embedding=[1.0, 0.0, 0.0])
        conversation_id, [m1] = await _day(user_id, DAY, [
            "Today I used the past tense in a real conversation without thinking.",
        ])
        calls = _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "used the past tense in a real conversation"),
        ]), theme="Past tense")

        async def embed(texts):
            return [[0.95, 0.31, 0.0] for _ in texts]  # cosine with old ~ 0.95

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")

        await memory.extract_memory(conversation_id)

        async with SessionLocal() as db:
            [pair] = (await db.execute(select(Pair))).scalars().all()
            now = await db.get(Fact, pair.now_fact_id)
        assert pair.source == "similarity" and pair.then_fact_id == old.id
        assert now.quote == "used the past tense in a real conversation"
        assert pair.theme == "Past tense"
        assert [c["kind"] for c in calls].count("theme") == 1

        await _reset(conversation_id)
        await memory.extract_memory(conversation_id)
        async with SessionLocal() as db:
            assert await memory.make_pairs(db, user_id, [now], []) == []
            await db.commit()
            assert (await db.execute(select(func.count()).select_from(Pair))).scalar_one() == 1

    @pytest.mark.asyncio
    async def test_dissimilar_struggle_makes_no_pair(self, client, monkeypatch):
        _, user_id = await _person(client)
        await _add_fact(user_id, "struggle", "I cannot hear the past tense",
                        DAY - timedelta(days=12), embedding=[1.0, 0.0, 0.0])
        conversation_id, [m1] = await _day(user_id, DAY, ["I baked bread for the first time."])
        _model(monkeypatch, _result(facts=[
            _fact(m1, "achievement", "baked bread for the first time"),
        ]))

        async def embed(texts):
            return [[0.0, 1.0, 0.0] for _ in texts]

        monkeypatch.setattr(memory, "embed", embed)
        monkeypatch.setattr(settings, "embedding_model", "embed-small")
        await memory.extract_memory(conversation_id)
        async with SessionLocal() as db:
            assert (await db.execute(select(func.count()).select_from(Pair))).scalar_one() == 0


# ------------------------------------------------------------------ loops


NOW = datetime(2026, 10, 20, 12, 0, tzinfo=timezone.utc)


async def _extracted(conversation_id):
    async with SessionLocal() as db:
        return (await db.get(Conversation, conversation_id)).memory_extracted_at


class TestLoops:
    @pytest.mark.asyncio
    async def test_extract_due_picks_quiet_unprocessed_conversations(self, client):
        _, user_id = await _person(client)
        quiet, _ = await _day(user_id, date(2026, 10, 16), ["one"], at=NOW - timedelta(minutes=40))
        busy, _ = await _day(user_id, date(2026, 10, 17), ["two"], at=NOW - timedelta(minutes=10))
        done, _ = await _day(user_id, date(2026, 10, 18), ["three"],
                             at=NOW - timedelta(hours=5), extracted_at=NOW - timedelta(hours=4))
        newer, _ = await _day(user_id, date(2026, 10, 19), ["four"],
                              at=NOW - timedelta(minutes=45), extracted_at=NOW - timedelta(hours=2))
        async with SessionLocal() as db:
            silent = Conversation(user_id=user_id, local_date=date(2026, 10, 15))
            db.add(silent)  # no messages: nothing to extract
            await db.commit()

        assert await memory.extract_due(NOW) == 2

        assert await _extracted(quiet) is not None
        assert await _extracted(newer) is not None
        assert await _extracted(busy) is None
        assert await _extracted(silent.id) is None
        done_at = await _extracted(done)
        assert done_at.replace(tzinfo=timezone.utc) == NOW - timedelta(hours=4)
        # Nothing left: a second pass does nothing.
        assert await memory.extract_due(NOW) == 0

    @pytest.mark.asyncio
    async def test_extract_due_survives_one_failure(self, client, monkeypatch):
        _, user_id = await _person(client)
        bad, _ = await _day(user_id, date(2026, 10, 16), ["one"], at=NOW - timedelta(hours=2))
        good, _ = await _day(user_id, date(2026, 10, 17), ["two"], at=NOW - timedelta(hours=1))
        real = memory.extract_memory

        async def flaky(conversation_id):
            if conversation_id == bad:
                raise RuntimeError("boom")
            await real(conversation_id)

        monkeypatch.setattr(memory, "extract_memory", flaky)
        assert await memory.extract_due(NOW) == 1
        assert await _extracted(good) is not None
        assert await _extracted(bad) is None

    @pytest.mark.asyncio
    async def test_close_day_at_local_close_hour(self, client):
        # Almaty is UTC+5: 04:00 there on Oct 20 is 23:00 UTC on Oct 19.
        _, user_id = await _person(client, tz="Asia/Almaty")
        before = datetime(2026, 10, 19, 22, 59, tzinfo=timezone.utc)
        after = datetime(2026, 10, 19, 23, 1, tzinfo=timezone.utc)
        # The 19th ended at 23:50 local; the 20th started at 03:58 local.
        yesterday, _ = await _day(user_id, date(2026, 10, 19), ["late"],
                                  at=datetime(2026, 10, 19, 18, 50, tzinfo=timezone.utc))
        today, _ = await _day(user_id, date(2026, 10, 20), ["early"],
                              at=before - timedelta(minutes=1))

        assert await memory.close_day(before) == 0
        assert await _extracted(yesterday) is None
        assert await memory.close_day(after) == 1
        assert await _extracted(yesterday) is not None
        assert await _extracted(today) is None

    @pytest.mark.asyncio
    async def test_loops_survive_errors_and_stop_on_cancel(self, monkeypatch):
        monkeypatch.setattr(settings, "memory_tick_minutes", 0)
        for loop_name, tick_name in (("memory_loop", "extract_due"), ("close_day_loop", "close_day")):
            calls = 0
            second = asyncio.Event()

            async def tick(now=None):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise RuntimeError("first pass fails")
                second.set()
                return 0

            monkeypatch.setattr(memory, tick_name, tick)
            task = asyncio.create_task(getattr(memory, loop_name)())
            await asyncio.wait_for(second.wait(), timeout=2)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert calls >= 2


# ------------------------------------------------------------------ GET /api/memory


class TestMemoryEndpoint:
    @pytest.mark.asyncio
    async def test_goal_threads_and_recent_facts_only_own(self, client, monkeypatch):
        auth, user_id = await _person(client)
        other_auth, other_id = await _person(client, email="other@example.com")
        monkeypatch.setattr(settings, "memory_recent_facts", 2)
        async with SessionLocal() as db:
            db.add(Goal(user_id=user_id, title="English", why_text="to talk to my clients",
                        finish_line="B2"))
            db.add_all([
                Thread(user_id=user_id, title="Past tense", opened_on=DAY),
                Thread(user_id=user_id, title="Listening", status="closed", opened_on=DAY,
                       closed_on=DAY),
                Thread(user_id=user_id, title="Gone", status="deleted", opened_on=DAY),
                Thread(user_id=other_id, title="Not yours", opened_on=DAY),
            ])
            await db.commit()
        await _add_fact(user_id, "struggle", "oldest quote", DAY - timedelta(days=2))
        await _add_fact(user_id, "learned", "middle quote", DAY - timedelta(days=1), flagged=True)
        await _add_fact(user_id, "achievement", "newest quote", DAY)
        await _add_fact(other_id, "achievement", "foreign quote", DAY)

        r = await client.get("/api/memory", headers=auth)
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["goal"]["title"] == "English" and body["goal"]["finish_line"] == "B2"
        assert [t["title"] for t in body["open_threads"]] == ["Past tense"]
        assert [t["title"] for t in body["closed_threads"]] == ["Listening"]
        assert [(f["quote"], f["flagged"]) for f in body["facts"]] == [
            ("newest quote", False), ("middle quote", True),
        ]

        r = await client.get("/api/memory", headers=other_auth)
        body = r.json()
        assert body["goal"] is None
        assert [t["title"] for t in body["open_threads"]] == ["Not yours"]
        assert [f["quote"] for f in body["facts"]] == ["foreign quote"]

        assert (await client.get("/api/memory")).status_code == 401
