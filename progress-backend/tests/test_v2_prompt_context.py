"""v2.1, task 14: the new conversation prompt and its examples, the context in three
levels, the model's reasoning effort, quick replies only on offer, and soft diagnostics
in place of the hard reply rules (spec v2.1 §2.2, stories 8-16, 27)."""

import json
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import httpx
import pytest
from sqlalchemy import select

from app.config import Settings, settings
from app.db import SessionLocal
from app.models import Conversation, Event, Goal, Message, Thread, User
from app.services import conversation, llm, outreach, prompt_examples, prompts
from app.time_utils import local_today

from conftest import parse_sse, register

TZ = "America/Los_Angeles"
MESSAGES = "/api/conversations/today/messages"
OLD_RULES = (
    "exactly one question", "At most", "small next step", "next step", "Start with",
    "max_words", "одним вопросом", "до 120 слов", "маленький следующий шаг", "начни с конкретики",
)
GENDERED = re.compile(
    r"\b(сам|сама|начинал|начинала|начал|начала|прошёл|прошел|прошла|рассказывал|рассказывала"
    r"|сделал|сделала|справился|справилась|добился|добилась|хотел|хотела|решил|решила"
    r"|пропустил|пропустила|планировал|планировала|заглянул|заглянула|вернулся|вернулась"
    r"|смог|смогла|понял|поняла|устал|устала|рад|рада)\b",
    re.I,
)
D = date(2026, 10, 27)


def _data(locale="ru", **kw) -> prompts.ContextData:
    return prompts.ContextData(locale=locale, goal_title="английский", skill="английский", **kw)


def _system(data, **kw) -> str:
    return prompts.compose_messages(data, **kw)[0]["content"]


# ------------------------------------------------------------------ the prompt


class TestPrompt:
    @pytest.mark.parametrize("locale", ["ru", "en"])
    def test_no_old_rules_and_the_brief_text_examples_and_meta(self, locale):
        system = _system(_data(locale, current="привет"))
        for rule in OLD_RULES:
            assert rule.lower() not in system.lower(), rule
        assert '{"quick_replies": [], "intent": "normal" | "plateau"}' in system
        assert "<<<META>>>" in system
        if locale == "ru":
            assert system.startswith("Ты — ForwardTrace, личный собеседник человека.")
            assert "Главное — следуй за человеком." in system
            assert "Цель — контекст, а не фильтр." in system
            assert "quick_replies — только если ты задал вопрос с явными вариантами действия, иначе []." in system
            assert "О, MVP — это уже не просто идея. Что получилось собрать?" in system
        else:
            assert system.startswith("You are ForwardTrace")
            assert "Oh, an MVP" in system
        assert "{{quote:f_12}}" in system and "{{quote:f_87}}" in system

    def test_ru_and_en_texts_are_the_constants(self):
        assert _system(_data("ru")).startswith(prompts.CHAT_SYSTEM_RU.split("{goal}")[0])
        assert _system(_data("en")).startswith(prompts.CHAT_SYSTEM_EN.split("{goal}")[0])
        # a language the app does not know gets the English text
        assert _system(_data("de")) == _system(_data("en"))

    def test_section_2_4_edits(self):
        ru = prompts.CHAT_SYSTEM_RU
        assert "(«помнишь, недавно было…»)" in ru
        assert "Не ссылайся на то, чего нет в переданных фактах или разговоре." in ru
        assert "ты же недавно говорил" not in ru and "Не говори «ты рассказывал»" not in ru
        assert "О человеке — без форм с родом" in ru
        assert "«как я за тебя\nрад!»" in ru or "«как я за тебя рад!»" in ru
        # the conversation prompt is not followed by the «вы»/«ты» service block
        assert "ADDRESS:" not in _system(_data("ru"))

    def test_goal_and_empty_blocks(self):
        system = _system(prompts.ContextData(locale="ru"))
        assert "Финиш: без финиша." in system
        assert "Продолжающиеся темы: нет" in system and "Раньше: нет" in system
        en = _system(prompts.ContextData(locale="en", goal_title="English", anchor_quote="speak", finish_line="B1"))
        assert "English" in en and "«speak»" not in en and '"speak"' in en and "B1" in en

    @pytest.mark.parametrize("locale", ["ru", "en"])
    def test_soft_and_plateau_blocks(self, locale):
        soft = _system(_data(locale), soft=True)
        assert prompts.chat_soft(locale).strip() in soft
        block = prompts.plateau_note(pairs=["p1"], closed=["c1"], conversations=4, days_to_compare=None, locale=locale)
        plateau = _system(_data(locale), plateau_block=block)
        assert block.strip() in plateau and "p1" in plateau and "c1" in plateau
        thin = prompts.plateau_note(pairs=[], closed=[], conversations=2, days_to_compare=5, locale=locale)
        assert "5" in thin and ("starting point" in thin or "точку старта" in thin)
        if locale == "ru":
            assert "Сегодня" in prompts.chat_soft("ru") and "Человек" in block


class TestExamples:
    def test_five_filled_four_todo(self):
        filled = [e for e in prompt_examples.EXAMPLES if not e.todo]
        todo = [e for e in prompt_examples.EXAMPLES if e.todo]
        assert len(filled) == 5 and len(todo) == 4
        source = Path(prompt_examples.__file__).read_text(encoding="utf-8")
        assert source.count("TODO(owner)") >= 4
        for example in filled:
            for lang in ("ru", "en"):
                assert example.user[lang] and example.bad[lang] and example.good[lang]
            assert not GENDERED.search(example.good["ru"]), example.good["ru"]
        assert filled[3].good["ru"] == (
            "Подожди. Месяц назад было {{quote:f_12}}, а недавно — {{quote:f_87}}. "
            "Что сейчас даёт ощущение, что всё стоит на месте?"
        )
        assert filled[4].good["ru"] == "Привет! Хорошо, что ты снова здесь. Как ты?"

    def test_render_takes_filled_ones_up_to_the_limit(self):
        block = prompt_examples.render_examples("ru", 8)
        for example in prompt_examples.EXAMPLES:
            if not example.todo:
                assert example.good["ru"] in block
        assert block.count("Хорошо:") == 5
        assert "f_12" in block and "услов" in block  # the ids are named as made up
        assert prompt_examples.render_examples("en", 2).count("Good:") == 2

    def test_prompt_takes_at_most_prompt_examples_max(self, monkeypatch):
        monkeypatch.setattr(settings, "prompt_examples_max", 3)
        assert _system(_data("ru")).count("Хорошо:") == 3
        assert settings.prompt_examples_max == 3
        assert Settings.model_fields["prompt_examples_max"].default == 8

    def test_example_ids_from_the_model_are_dropped(self):
        renderer = conversation.ReplyRenderer({})
        renderer.feed("Было {{quote:f_12}} и стало.")
        reply = renderer.finish()
        assert reply.used_fact_ids == []
        assert "f_12" not in json.dumps(reply.segments, ensure_ascii=False)


# ------------------------------------------------------------------ registry and shape


class TestRegistry:
    def test_versions(self):
        assert {"v2.0", "v2.1"} <= set(prompts.CHAT_PROMPTS)

    def test_v21_is_system_and_current_with_history_inside(self):
        data = _data(
            "ru",
            recent=[
                prompts.RecentLine(date(2026, 10, 26), "user", "вчера пробовал"),
                prompts.RecentLine(date(2026, 10, 26), "assistant", "и как?"),
            ],
            current="сегодня ещё",
        )
        messages = prompts.compose_messages(data)
        assert [m["role"] for m in messages] == ["system", "user"]
        assert messages[1]["content"] == "сегодня ещё"
        system = messages[0]["content"]
        assert "[2026-10-26] Человек: вчера пробовал\n[2026-10-26] ForwardTrace: и как?" in system
        en = prompts.compose_messages(prompts.ContextData(locale="en", recent=data.recent))
        assert len(en) == 1 and "[2026-10-26] Person: вчера пробовал" in en[0]["content"]

    def test_v20_keeps_the_roles(self):
        data = _data("en", recent=[prompts.RecentLine(D, "user", "hi")], current="now")
        messages = prompts.compose_messages(data, version="v2.0")
        assert [m["role"] for m in messages] == ["system", "user", "user"]
        assert "At most 120 words" in messages[0]["content"]

    def test_threads_and_facts_lines(self):
        data = _data(
            "ru",
            threads=[
                prompts.ThreadLine("t1", "Звонки", "struggle", date(2026, 10, 1)),
                prompts.ThreadLine("t2", "Ссора с другом", "topic", date(2026, 10, 20)),
            ],
            facts=[prompts.FactLine("f1", date(2026, 10, 2), "struggle", "боюсь звонить")],
        )
        system = _system(data)
        assert "[t1] (struggle) Звонки — с 2026-10-01" in system
        assert "[t2] (topic) Ссора с другом — с 2026-10-20" in system
        assert "[f1] 2026-10-02 struggle: «боюсь звонить»" in system

    def test_txt_file_takes_the_v21_placeholders(self, tmp_path):
        path = tmp_path / "draft.txt"
        path.write_text(
            "G {goal} A {anchor_quote} F {finish_line} T {threads} FA {facts} D {day_summaries} "
            'R {recent_messages} E {examples} JSON {"a": 1}',
            encoding="utf-8",
        )
        data = prompts.ContextData(
            locale="en", goal_title="english", anchor_quote="speak", finish_line="B1",
            recent=[prompts.RecentLine(D, "user", "hi")], current="now",
        )
        messages = prompts.compose_messages(data, version=str(path))
        system = messages[0]["content"]
        assert system.startswith('G english A "speak" F B1 T none')
        assert "[2026-10-27] Person: hi" in system and "Good:" in system and '{"a": 1}' in system
        assert messages[-1] == {"role": "user", "content": "now"}


# ------------------------------------------------------------------ level 1 (pure)


def _line(days_ago, text, role="user"):
    return prompts.RecentLine(D - timedelta(days=days_ago), role, text)


class TestSelectRecent:
    def _select(self, lines, **kw):
        params = {"budget": 6000, "min_days": 2, "hard": 24000, "chars_per_token": 3} | kw
        return conversation.select_recent(lines, D, **params)

    def test_everything_fits_in_chronological_order(self):
        newest_first = [_line(0, "today"), _line(1, "yesterday", "assistant"), _line(1, "yesterday q")]
        assert [r.text for r in self._select(newest_first)] == ["yesterday q", "yesterday", "today"]

    def test_older_long_messages_are_cut_by_the_budget_the_last_two_days_stay(self):
        long = "x" * 3000  # 1000 tokens at 3 chars per token
        newest_first = [_line(0, long), _line(1, long), _line(3, long), _line(4, "short")]
        kept = self._select(newest_first, budget=1500)
        assert [r.local_date for r in kept] == [D - timedelta(days=1), D]

    def test_older_messages_fill_the_budget_until_one_does_not_fit(self):
        newest_first = [_line(0, "a" * 30), _line(3, "b" * 30), _line(5, "c" * 300), _line(6, "d")]
        assert [r.text[0] for r in self._select(newest_first, budget=25)] == ["b", "a"]

    def test_hard_limit_drops_the_oldest_even_inside_the_minimum(self):
        newest_first = [_line(0, "a" * 300), _line(0, "b" * 300), _line(1, "c" * 300)]
        kept = self._select(newest_first, budget=10, hard=250)
        assert [r.text[0] for r in kept] == ["b", "a"]


# ------------------------------------------------------------------ the app's context


async def _person(client, locale="ru", email="person@example.com"):
    auth = await register(client, email=email, locale=locale)
    user_id = uuid.UUID((await client.get("/api/auth/me", headers=auth)).json()["id"])
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        user.first_conversation_done = True
        await db.commit()
    return auth, user_id


async def _past_day(user_id, day, said: list[tuple[str, str]], summary=None):
    async with SessionLocal() as db:
        conv = Conversation(user_id=user_id, local_date=day, counts_for_limit=True, summary=summary)
        db.add(conv)
        await db.flush()
        at = datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc)
        for i, (role, text) in enumerate(said):
            db.add(Message(
                conversation_id=conv.id, user_id=user_id, role=role, source="text",
                content_raw=text, content=[{"type": "text", "text": text}],
                created_at=at + timedelta(minutes=i),
            ))
        await db.commit()


def _capture(monkeypatch, *pieces):
    seen: list = []

    async def fake(messages, *, model=None, reasoning_effort=None):
        seen.append(messages)
        for piece in pieces or ("Ок.",):
            yield piece

    monkeypatch.setattr(conversation, "stream_chat", fake)
    return seen


async def _send(client, auth, text):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


class TestContext:
    @pytest.mark.asyncio
    async def test_yesterday_verbatim_and_its_summary_not_repeated(self, client, monkeypatch):
        seen = _capture(monkeypatch)
        auth, uid = await _person(client)
        today = local_today(TZ)
        yesterday, older = today - timedelta(days=1), today - timedelta(days=6)
        await _past_day(uid, yesterday, [("user", "Вчера собрал прототип игры."), ("assistant", "И как он?")],
                        summary="ВЫЖИМКА-ВЧЕРА")
        await _past_day(uid, older, [], summary="ВЫЖИМКА-РАНЬШЕ")
        await _send(client, auth, "Сегодня показал его другу.")
        [messages] = seen
        assert [m["role"] for m in messages] == ["system", "user"]
        assert messages[1]["content"] == "Сегодня показал его другу."
        system = messages[0]["content"]
        y = yesterday.isoformat()
        assert f"[{y}] Человек: Вчера собрал прототип игры.\n[{y}] ForwardTrace: И как он?" in system
        assert "Сегодня показал его другу." not in system  # the current one is the user turn
        assert "ВЫЖИМКА-ВЧЕРА" not in system and "ВЫЖИМКА-РАНЬШЕ" in system

    @pytest.mark.asyncio
    async def test_budget_cuts_long_old_messages(self, client, monkeypatch):
        seen = _capture(monkeypatch)
        monkeypatch.setattr(settings, "context_recent_tokens", 100)
        auth, uid = await _person(client)
        today = local_today(TZ)
        await _past_day(uid, today - timedelta(days=4), [("user", "СТАРОЕ " + "длинно " * 200)])
        await _past_day(uid, today - timedelta(days=1), [("user", "ВЧЕРА " + "длинно " * 200)])
        await _send(client, auth, "Привет")
        system = seen[0][0]["content"]
        assert "ВЧЕРА" in system and "СТАРОЕ" not in system

    @pytest.mark.asyncio
    async def test_threads_facts_goal(self, client, monkeypatch):
        seen = _capture(monkeypatch)
        monkeypatch.setattr(settings, "context_threads", 2)
        auth, uid = await _person(client)
        today = local_today(TZ)
        async with SessionLocal() as db:
            db.add(Goal(user_id=uid, title="СТАРАЯ-ЦЕЛЬ", why_text="старый повод", is_active=False))
            db.add(Goal(user_id=uid, title="гитара", why_text="хочу играть с друзьями"))
            for title, opened, mentioned in (
                ("Нить-давняя", today - timedelta(days=30), None),
                ("Нить-свежая", today - timedelta(days=20), today - timedelta(days=1)),
                ("Нить-средняя", today - timedelta(days=10), None),
            ):
                db.add(Thread(user_id=uid, title=title, opened_on=opened, last_mentioned_on=mentioned))
            await db.commit()
        late = await _fact(uid, "аккорды уже не путаю", today - timedelta(days=2), "achievement")
        early = await _fact(uid, "не могу взять баррэ", today - timedelta(days=20), "struggle")
        await _send(client, auth, "Сыграл песню целиком.")
        system = seen[0][0]["content"]
        assert "СТАРАЯ-ЦЕЛЬ" not in system and "старый повод" not in system
        assert "Цель: гитара." in system and "«хочу играть с друзьями»" in system
        assert system.index("Нить-свежая") < system.index("Нить-средняя")
        assert "Нить-давняя" not in system and "(struggle) Нить-свежая — с " in system
        first = f"[{early.id}] {early.local_date.isoformat()} struggle: «не могу взять баррэ»"
        second = f"[{late.id}] {late.local_date.isoformat()} achievement: «аккорды уже не путаю»"
        assert first in system and second in system and system.index(first) < system.index(second)


async def _fact(uid, quote, day, kind):
    from app.models import Fact

    async with SessionLocal() as db:
        fact = Fact(user_id=uid, local_date=day, type=kind, text="a fact", quote=quote)
        db.add(fact)
        await db.commit()
        return fact


# ------------------------------------------------------------------ the model


class TestModel:
    def test_chat_effort_default_is_medium(self):
        assert Settings.model_fields["chat_reasoning_effort"].default == "medium"
        assert Settings.model_fields["openai_reasoning_effort"].default == "low"
        for name, value in (
            ("context_recent_tokens", 6000), ("context_recent_min_days", 2),
            ("context_recent_hard_tokens", 24000), ("context_chars_per_token", 3),
        ):
            assert Settings.model_fields[name].default == value

    @pytest.mark.asyncio
    async def test_chat_sends_medium_service_calls_low(self, monkeypatch):
        seen: list = []

        def handler(request):
            payload = json.loads(request.content)
            seen.append(payload)
            if payload.get("stream"):
                return httpx.Response(200, content=b"data: [DONE]\n\n")
            return httpx.Response(200, json={
                "model": "m", "choices": [{"message": {"content": "{}"}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            })

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "chat_reasoning_effort", Settings.model_fields["chat_reasoning_effort"].default)
        monkeypatch.setattr(settings, "openai_reasoning_effort", Settings.model_fields["openai_reasoning_effort"].default)
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        assert [p async for p in llm.stream_chat([{"role": "user", "content": "x"}])] == []
        await llm.complete_json("sys", "usr", {"type": "object"})
        assert seen[0]["reasoning_effort"] == "medium"
        assert seen[1]["reasoning_effort"] == "low"


# ------------------------------------------------------------------ replies and diagnostics


class TestReplies:
    @pytest.mark.asyncio
    async def test_no_quick_replies_by_default(self, client):
        auth, _ = await _person(client, locale="en")
        events = await _send(client, auth, "Found the leak today.")
        assert events[-1][0] == "done" and events[-1][1]["quick_replies"] == []

    @pytest.mark.asyncio
    async def test_long_reply_with_two_questions_is_kept_whole(self, client, monkeypatch):
        prose = " ".join(["word"] * 98) + " guitar? " + " ".join(["more"] * 100) + " why?"
        _capture(monkeypatch, prose, "<<<META>>>", '{"quick_replies": ["Yes", "No"], "intent": "normal"}')
        auth, uid = await _person(client, locale="en")
        async with SessionLocal() as db:
            db.add(Goal(user_id=uid, title="Guitar"))
            await db.commit()
        events = await _send(client, auth, "Played a song.")
        streamed = "".join(d["text"] for e, d in events if e == "delta")
        assert streamed == prose
        async with SessionLocal() as db:
            answer = (await db.execute(select(Message).where(Message.role == "assistant"))).scalar_one()
            assert answer.content_raw == prose
            types = [e.type for e in (await db.execute(select(Event))).scalars()]
            [ai] = [e for e in (await db.execute(select(Event).where(Event.type == "ai_reply"))).scalars()]
        assert "reply_rule_violation" not in types
        assert ai.payload["words"] == 200 and ai.payload["questions"] == 2
        assert ai.payload["mentions_goal"] is True
        assert ai.payload["with_quote"] is False and ai.payload["with_quick_replies"] is True

    @pytest.mark.asyncio
    async def test_unknown_fact_id_is_still_dropped(self, client, monkeypatch):
        stranger = uuid.uuid4()
        _capture(monkeypatch, f"Look {{{{quote:{stranger}}}}} here.<<<META>>>{{}}")
        auth, _ = await _person(client, locale="en")
        events = await _send(client, auth, "hi")
        assert not [e for e, _ in events if e == "quote"]
        assert str(stranger) not in json.dumps(events)

    def test_mentions_goal(self):
        assert conversation.mentions_goal("Practiced English today", "English", None)
        assert conversation.mentions_goal("The game jam went well", "Game development", None)
        assert conversation.mentions_goal("Played the GUITAR!", None, "guitar")
        assert not conversation.mentions_goal("Had a fight with a friend", "English", "English")
        assert not conversation.mentions_goal("anything", None, None)
        assert not conversation.mentions_goal("to be or not", "Go to Mars", None)  # short words ignored
        # a stem of 5 letters: Russian inflections count
        assert conversation.mentions_goal("Сегодня занимался английским", "Английский язык", None)
        assert conversation.mentions_goal("Учил слова", None, "слова")
        assert not conversation.mentions_goal("Сегодня поругался с другом", "Английский язык", None)

    def test_old_rules_are_gone(self):
        assert not hasattr(conversation, "BANNED")
        assert not hasattr(conversation, "check_reply_rules")
        for name in ("reply_max_words", "reply_max_words_long", "reply_long_input_words"):
            assert name not in Settings.model_fields
        example = (Path(__file__).resolve().parents[1] / ".env.example").read_text(encoding="utf-8")
        assert not re.search(r"^(REPLY_MAX_WORDS|REPLY_MAX_WORDS_LONG|REPLY_LONG_INPUT_WORDS)=", example, re.M)
        assert "CHAT_REASONING_EFFORT=medium" in example
        for name in ("CONTEXT_RECENT_TOKENS=", "CONTEXT_RECENT_MIN_DAYS=", "CONTEXT_RECENT_HARD_TOKENS=",
                     "CONTEXT_CHARS_PER_TOKEN=", "PROMPT_EXAMPLES_MAX="):
            assert name in example

    def test_outreach_keeps_only_empty_length_quotes(self):
        text = [{"type": "text", "text": "Молодец! Как прошло? А что дальше?"}]
        assert outreach._breaks_rules(text, []) == []
        assert outreach._breaks_rules([{"type": "text", "text": ""}], []) == ["empty"]
        long = [{"type": "text", "text": " ".join(["w"] * (settings.outreach_max_words + 1))}]
        assert outreach._breaks_rules(long, []) == ["length"]
        assert outreach._breaks_rules(text, ["a", "b"]) == ["quotes"]


class TestRussianBlocksInTheApp:
    @pytest.mark.asyncio
    async def test_level_one_is_gentler_in_russian(self, client, monkeypatch):
        from conftest import SAFETY_RESULT

        seen = _capture(monkeypatch)
        monkeypatch.setitem(SAFETY_RESULT, "level", 1)
        auth, _ = await _person(client)
        await _send(client, auth, "Сегодня тяжело.")
        system = seen[0][0]["content"]
        assert system.startswith("Ты — ForwardTrace") and prompts.chat_soft("ru").strip() in system

    @pytest.mark.asyncio
    async def test_plateau_button_in_russian(self, client, monkeypatch):
        seen = _capture(monkeypatch)
        auth, _ = await _person(client)
        r = await client.post("/api/conversations/today/plateau", headers=auth)
        assert r.status_code == 200
        [messages] = seen
        assert [m["role"] for m in messages] == ["system"]
        assert "Человеку кажется, что всё стоит на месте" in messages[0]["content"]
        assert "точку старта" in messages[0]["content"]
