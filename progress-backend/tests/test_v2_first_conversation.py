"""Stage 4: the first conversation instead of onboarding screens, and PATCH /api/goal.

The step models are a fake (conftest.py patches `first_conversation.complete_json` and
answers from `FIRST_RESULTS`); the chat model is the usual fake stream. Each test sets
only the answer it needs.
"""

import re
from datetime import timedelta

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.models import Conversation, Fact, Goal, Message, Pair, User
from app.services import safety, texts
from app.services.safety import SafetyResult
from app.time_utils import local_today
from conftest import FIRST_CALLS, FIRST_RESULTS, parse_sse, register

TZ = "America/Los_Angeles"
TODAY = "/api/conversations/today"
MESSAGES = "/api/conversations/today/messages"

NO_FINISH = texts.t("en", "first.no_finish_option")
OPTIONS = ["Level B2", "IELTS 6.5", "Pass the interview", "Read without a dictionary"]


# ------------------------------------------------------------------ helpers


async def _start(client, email="person@example.com", locale="en"):
    auth = await register(client, email=email, locale=locale)
    r = await client.get(TODAY, headers=auth)
    assert r.status_code == 200
    return auth


async def _say(client, auth, text):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def _reply_text(events) -> str:
    return "".join(d["text"] for e, d in events if e == "delta")


def _done(events) -> dict:
    [done] = [d for e, d in events if e == "done"]
    return done


async def _user(email="person@example.com") -> User:
    async with SessionLocal() as db:
        return (await db.execute(select(User).where(User.email == email))).scalar_one()


async def _goal(email="person@example.com") -> Goal | None:
    user = await _user(email)
    async with SessionLocal() as db:
        return (
            await db.execute(select(Goal).where(Goal.user_id == user.id, Goal.is_active.is_(True)))
        ).scalar_one_or_none()


async def _state(email="person@example.com") -> dict:
    user = await _user(email)
    async with SessionLocal() as db:
        return (
            await db.execute(select(Conversation).where(Conversation.user_id == user.id))
        ).scalar_one().state


async def _rows(model, *where):
    async with SessionLocal() as db:
        return list((await db.execute(select(model).where(*where))).scalars())


@pytest.fixture
def results(monkeypatch):
    def put(step, **data):
        monkeypatch.setitem(FIRST_RESULTS, step, {**FIRST_RESULTS[step], **data})

    return put


async def _to_step(client, auth, step):
    """Walk the conversation to the start of `step` with simple answers."""
    order = ["skill", "motivation", "finish", "baseline", "schedule"]
    answers = {
        "skill": "I make a small game in Unity",
        "motivation": "I want to ship my own game one day",
        "finish": OPTIONS[0],
        "baseline": "I started with nothing and now I can make levels",
    }
    for name in order[: order.index(step)]:
        await _say(client, auth, answers[name])
    assert (await _state())["step"] == step


# ------------------------------------------------------------------ skill


@pytest.mark.asyncio
class TestSkill:
    async def test_skill_is_saved_and_motivation_is_asked(self, client):
        auth = await _start(client)
        events = await _say(client, auth, "I make a small game in Unity, mostly levels")
        assert (await _user()).skill == "Game development"
        assert (await _goal()).title == "Game development"
        assert _reply_text(events) == texts.t("en", "first.ask_motivation")
        assert _done(events)["quick_replies"] == []
        assert (await _state())["step"] == "motivation"
        # the model saw the person's own words
        assert FIRST_CALLS[-1][0] == "skill" and "small game in Unity" in FIRST_CALLS[-1][1]

    async def test_reply_is_one_delta_then_done(self, client):
        auth = await _start(client)
        events = await _say(client, auth, "Guitar")
        assert [e for e, _ in events] == ["user_message", "delta", "done"]
        saved = await _rows(Message, Message.role == "assistant")
        assert saved[-1].content_raw == texts.t("en", "first.ask_motivation")

    async def test_long_title_is_cut_to_120(self, client, results):
        results("skill", title="x" * 300)
        auth = await _start(client)
        await _say(client, auth, "a very long answer " * 20)
        assert len((await _user()).skill) == 120
        assert len((await _goal()).title) == 120


# ------------------------------------------------------------------ motivation


@pytest.mark.asyncio
class TestMotivation:
    TEXT = "I want to get into the university on a grant, that is why"

    async def test_verified_quote_is_saved_with_four_options_and_no_finish(self, client, results):
        auth = await _start(client)
        await _say(client, auth, "English")
        results("motivation", quote="get into the university on a grant")
        events = await _say(client, auth, self.TEXT)
        goal = await _goal()
        assert goal.why_text == "get into the university on a grant"
        saved = await _rows(Message, Message.role == "user")
        assert goal.why_message_id == saved[-1].id
        assert _reply_text(events) == texts.t(
            "en", "first.ask_finish_quoted", quote="get into the university on a grant"
        )
        assert _done(events)["quick_replies"] == OPTIONS + [NO_FINISH]
        assert (await _state())["step"] == "finish"

    async def test_quote_that_fails_verification_is_not_shown_or_saved(self, client, results):
        auth = await _start(client)
        await _say(client, auth, "English")
        results("motivation", quote="to become a famous poet in Paris")
        events = await _say(client, auth, self.TEXT)
        assert (await _goal()).why_text is None
        assert (await _goal()).why_message_id is None
        assert _reply_text(events) == texts.t("en", "first.ask_finish")
        assert "poet" not in _reply_text(events)
        assert _done(events)["quick_replies"] == OPTIONS + [NO_FINISH]


# ------------------------------------------------------------------ finish


@pytest.mark.asyncio
class TestFinish:
    async def test_option_chosen_by_button(self, client):
        auth = await _start(client)
        await _to_step(client, auth, "finish")
        events = await _say(client, auth, "IELTS 6.5")
        goal = await _goal()
        assert goal.finish_line == "IELTS 6.5"
        assert goal.finish_set_on == local_today(TZ)
        assert _reply_text(events) == texts.t("en", "first.ask_baseline")
        assert (await _state())["no_finish"] is False

    async def test_own_text(self, client):
        auth = await _start(client)
        await _to_step(client, auth, "finish")
        await _say(client, auth, "Order a coffee in Lisbon without English")
        assert (await _goal()).finish_line == "Order a coffee in Lisbon without English"

    async def test_no_finish(self, client):
        auth = await _start(client)
        await _to_step(client, auth, "finish")
        events = await _say(client, auth, NO_FINISH)
        goal = await _goal()
        assert goal.finish_line is None and goal.finish_set_on is None
        assert (await _state())["no_finish"] is True
        assert _reply_text(events) == texts.t("en", "first.ask_baseline_no_finish")


# ------------------------------------------------------------------ baseline


@pytest.mark.asyncio
class TestBaseline:
    TEXT = (
        "At the start I could not write a single sentence in past tense. "
        "Now I can tell a whole story at a dinner. "
        "I also used to freeze on the phone and now I take calls at work. "
        "Right now I am around B1."
    )

    def _pairs(self):
        return [
            {
                "then_quote": "could not write a single sentence in past tense",
                "now_quote": "I can tell a whole story at a dinner",
                "theme": "Past tense",
            },
            {
                "then_quote": "used to freeze on the phone",
                "now_quote": "now I take calls at work",
                "theme": "Phone calls",
            },
        ]

    async def test_pairs_facts_level_and_recalled_quotes(self, client, results):
        auth = await _start(client)
        await _to_step(client, auth, "baseline")
        results("baseline", pairs=self._pairs(), level_quote="Right now I am around B1")
        events = await _say(client, auth, self.TEXT)

        facts = {f.quote: f for f in await _rows(Fact)}
        assert facts["could not write a single sentence in past tense"].type == "struggle"
        assert facts["I can tell a whole story at a dinner"].type == "achievement"
        assert facts["Right now I am around B1"].type == "level"
        pairs = await _rows(Pair)
        assert len(pairs) == 2
        assert all(p.recalled and p.source == "first_conversation" for p in pairs)
        # SQLite ignores VARCHAR lengths; Postgres rejects the insert.
        assert len("first_conversation") <= Pair.__table__.c.source.type.length
        assert {p.theme for p in pairs} == {"Past tense", "Phone calls"}

        quotes = [d for e, d in events if e == "quote"]
        assert [q["quote"] for q in quotes] == [
            "could not write a single sentence in past tense",
            "I can tell a whole story at a dinner",
        ]  # the first pair goes into the reply
        assert all(q["recalled"] is True for q in quotes)
        assert _done(events)["quick_replies"] == texts.quick("en", "first.schedule")
        assert _done(events)["used_fact_ids"] == [q["fact_id"] for q in quotes]
        saved = await _rows(Message, Message.role == "user")
        assert (await _goal()).baseline_message_id == saved[-1].id
        assert (await _state())["step"] == "schedule"
        # the stored segments keep `recalled` for after a reload
        reply = (await _rows(Message, Message.role == "assistant"))[-1]
        assert [s["recalled"] for s in reply.content if s["type"] == "quote"] == [True, True]

    async def test_unverified_quotes_and_the_cap_of_three(self, client, results):
        auth = await _start(client)
        await _to_step(client, auth, "baseline")
        text = "one two three four five six seven eight nine ten eleven twelve " + (
            "alpha beta gamma delta epsilon zeta eta theta iota kappa lambda mu"
        )
        pairs = [
            {"then_quote": "invented sentence not said", "now_quote": "one two three four five six", "theme": "A"},
            {"then_quote": "seven eight nine ten eleven", "now_quote": "alpha beta gamma delta epsilon", "theme": "B"},
            {"then_quote": "zeta eta theta iota kappa", "now_quote": "two three four five six seven", "theme": "C"},
            {"then_quote": "eight nine ten eleven twelve", "now_quote": "beta gamma delta epsilon zeta", "theme": "D"},
            {"then_quote": "three four five six seven", "now_quote": "gamma delta epsilon zeta eta", "theme": "E"},
        ]
        results("baseline", pairs=pairs)
        await _say(client, auth, text)
        themes = sorted(p.theme for p in await _rows(Pair))
        assert themes == ["B", "C", "D"]  # A fails verification; at most 3 are kept
        stored = {f.quote for f in await _rows(Fact)}
        assert "invented sentence not said" not in stored

    async def test_no_pairs_gives_the_just_started_branch(self, client, results):
        auth = await _start(client)
        await _to_step(client, auth, "baseline")
        results("baseline", pairs=[], level_quote="Right now I am around B1")
        events = await _say(client, auth, "Right now I am around B1, nothing more")
        assert _reply_text(events) == texts.t("en", "first.just_started")
        assert not [e for e, _ in events if e == "quote"]
        assert await _rows(Pair) == []
        assert [f.type for f in await _rows(Fact)] == ["level"]
        assert _done(events)["quick_replies"] == texts.quick("en", "first.schedule")

    async def test_just_started_ignores_pairs(self, client, results):
        auth = await _start(client)
        await _to_step(client, auth, "baseline")
        results("baseline", pairs=self._pairs(), just_started=True)
        events = await _say(client, auth, self.TEXT)
        assert _reply_text(events) == texts.t("en", "first.just_started")
        assert await _rows(Pair) == []
        assert (await _state())["just_started"] is True


# ------------------------------------------------------------------ schedule


async def _schedule(client, auth, replies):
    await _to_step(client, auth, "schedule")
    events = []
    for reply in replies:
        events = await _say(client, auth, reply)
    return events


@pytest.mark.asyncio
class TestSchedule:
    async def test_evening_is_21_and_the_conversation_is_done(self, client):
        auth = await _start(client)
        events = await _schedule(client, auth, ["In the evening"])
        user = await _user()
        assert user.reminder_hour == 21 and user.first_conversation_done is True
        assert (await _state())["step"] == "done"
        assert _reply_text(events) == texts.t("en", "first.schedule_set", hour=21)
        assert _done(events)["quick_replies"] == []

    async def test_after_practice_asks_then_parses_the_hour(self, client):
        auth = await _start(client)
        events = await _schedule(client, auth, ["After practice"])
        assert _reply_text(events) == texts.t("en", "first.ask_session_end")
        assert _done(events)["quick_replies"] == ["18:00", "19:00", "20:00", "21:00"]
        assert (await _user()).first_conversation_done is False
        await _say(client, auth, "19:00")
        user = await _user()
        assert user.reminder_hour == 19 and user.first_conversation_done is True

    async def test_picked_time_arrives_as_hh_00(self, client):
        auth = await _start(client)
        await _schedule(client, auth, ["07:00"])
        assert (await _user()).reminder_hour == 7

    async def test_free_text_hour(self, client):
        auth = await _start(client)
        await _schedule(client, auth, ["around 8 pm please"])
        assert (await _user()).reminder_hour == 20

    async def test_unparsed_gets_one_retry_then_20(self, client):
        auth = await _start(client)
        events = await _schedule(client, auth, ["whenever"])
        assert _reply_text(events) == texts.t("en", "first.retry.schedule")
        assert (await _user()).first_conversation_done is False
        async with SessionLocal() as db:  # make the default visible: not 20 beforehand
            user = (await db.execute(select(User))).scalar_one()
            user.reminder_hour = 9
            await db.commit()
        await _say(client, auth, "no idea")
        user = await _user()
        assert user.reminder_hour == 20 and user.first_conversation_done is True

    async def test_after_done_the_normal_reply_takes_over(self, client):
        auth = await _start(client)
        await _schedule(client, auth, ["In the evening"])
        calls = len(FIRST_CALLS)
        events = await _say(client, auth, "One more thing about my day")
        assert _reply_text(events) == "What helped you find it?"
        assert len(FIRST_CALLS) == calls


# ------------------------------------------------------------------ retries


@pytest.mark.asyncio
class TestRetry:
    async def test_empty_answer_gets_one_soft_retry_then_moves_on(self, client):
        auth = await _start(client)
        events = await _say(client, auth, "...")
        assert _reply_text(events) == texts.t("en", "first.retry.skill")
        assert _done(events)["quick_replies"] == texts.quick("en", "first.skills")
        assert (await _state())["step"] == "skill"
        assert FIRST_CALLS == []  # nothing to read: the model is not asked
        events = await _say(client, auth, "???")
        assert _reply_text(events) == texts.t("en", "first.ask_motivation")
        assert (await _user()).skill == texts.t("en", "first.skill_placeholder")
        assert (await _state())["step"] == "motivation"

    async def test_off_topic_answer_is_retried_once(self, client, results):
        auth = await _start(client)
        results("skill", on_topic=False, title="")
        events = await _say(client, auth, "what is the weather like")
        assert _reply_text(events) == texts.t("en", "first.retry.skill")
        assert (await _user()).skill is None
        events = await _say(client, auth, "still the weather")
        assert _reply_text(events) == texts.t("en", "first.ask_motivation")
        assert (await _user()).skill == "my skill"

    async def test_retry_counter_resets_on_the_next_step(self, client, results):
        auth = await _start(client)
        await _say(client, auth, "...")
        await _say(client, auth, "Guitar")
        assert (await _state())["retries"] == 0
        results("motivation", on_topic=False)
        events = await _say(client, auth, "blah")
        assert _reply_text(events) == texts.t("en", "first.retry.motivation")

    async def test_finish_empty_twice_means_no_finish(self, client):
        auth = await _start(client)
        await _to_step(client, auth, "finish")
        events = await _say(client, auth, "...")
        assert _reply_text(events) == texts.t("en", "first.retry.finish")
        assert _done(events)["quick_replies"] == OPTIONS + [NO_FINISH]
        await _say(client, auth, "...")
        assert (await _goal()).finish_line is None
        assert (await _state())["no_finish"] is True
        assert (await _state())["step"] == "baseline"


# ------------------------------------------------------------------ the next day


@pytest.mark.asyncio
class TestNextDay:
    async def test_unfinished_conversation_continues_from_the_same_step(self, client):
        auth = await _start(client)
        await _to_step(client, auth, "finish")
        async with SessionLocal() as db:
            conv = (await db.execute(select(Conversation))).scalar_one()
            conv.local_date = local_today(TZ) - timedelta(days=1)
            await db.commit()
        body = (await client.get(TODAY, headers=auth)).json()
        assert body["kind"] == "first" and body["state"]["step"] == "finish"
        # Not a second greeting: the question of the saved step, with its options.
        [question] = body["messages"]
        assert question["role"] == "assistant"
        assert question["content"] == [{"type": "text", "text": texts.t("en", "first.retry.finish")}]
        assert question["quick_replies"] == OPTIONS + [NO_FINISH]
        events = await _say(client, auth, "IELTS 6.5")
        assert (await _goal()).finish_line == "IELTS 6.5"
        assert _reply_text(events) == texts.t("en", "first.ask_baseline")


    @pytest.mark.parametrize(
        "state, key, quick_key",
        [
            ({"step": "skill"}, "first.greeting", "first.skills"),
            ({"step": "motivation"}, "first.ask_motivation", None),
            ({"step": "baseline", "no_finish": True}, "first.ask_baseline_no_finish", None),
            ({"step": "schedule"}, "first.retry.schedule", "first.schedule"),
            ({"step": "schedule", "session_end": True}, "first.ask_session_end", "first.session_end_hours"),
        ],
    )
    async def test_each_saved_step_is_asked_again_on_the_new_day(self, client, state, key, quick_key):
        auth = await register(client, locale="ru")
        user = await _user()
        async with SessionLocal() as db:
            db.add(Conversation(
                user_id=user.id, local_date=local_today(TZ) - timedelta(days=2), kind="first",
                started_by="ai", state={"retries": 0, "no_finish": False, **state},
            ))
            await db.commit()
        body = (await client.get(TODAY, headers=auth)).json()
        [question] = body["messages"]
        assert question["content"][0]["text"] == texts.t("ru", key)
        assert question["quick_replies"] == (texts.quick("ru", quick_key) if quick_key else [])


# ------------------------------------------------------------------ safety


@pytest.mark.asyncio
class TestSafety:
    async def test_level_two_does_not_advance_the_step(self, client, monkeypatch):
        auth = await _start(client)
        calls = []

        async def level_two(text, locale):
            calls.append(text)
            return SafetyResult(level=2)

        monkeypatch.setattr(safety, "safety_check", level_two)
        events = await _say(client, auth, "I do not see the point of anything")
        assert calls  # the check ran on a first-conversation message
        assert (await _state())["step"] == "skill"
        assert (await _user()).skill is None
        assert await _goal() is None
        assert FIRST_CALLS == []
        assert _reply_text(events) == "What helped you find it?"  # the normal reply path

    async def test_level_zero_advances(self, client, monkeypatch):
        auth = await _start(client)

        async def level_zero(text, locale):
            return SafetyResult(level=0)

        monkeypatch.setattr(safety, "safety_check", level_zero)
        await _say(client, auth, "Guitar")
        assert (await _state())["step"] == "motivation"


# ------------------------------------------------------------------ Russian


FORBIDDEN = re.compile(r"\b(ты|тебе|тебя|тобой|твой|твоя|твоё|твои|твоих)\b", re.I)
GENDERED = re.compile(r"\b(прошёл|прошел|начал|сделал|добился|хотел|решил|сам)\b", re.I)


class TestRussian:
    def test_first_conversation_strings_address_vy_without_gender(self):
        checked = 0
        for key, value in texts.RU.items():
            if not key.startswith("first."):
                continue
            for line in [value] if isinstance(value, str) else value:
                checked += 1
                assert not FORBIDDEN.search(line), (key, line)
                assert not GENDERED.search(line), (key, line)
        assert checked >= 15

    @pytest.mark.asyncio
    async def test_ru_flow_uses_the_formal_texts(self, client):
        auth = await _start(client, locale="ru")
        events = await _say(client, auth, "Гитара")
        assert _reply_text(events) == "Зачем вам это? Чего хотите добиться?"

    @pytest.mark.asyncio
    async def test_ru_retry_text(self, client):
        auth = await _start(client, locale="ru")
        events = await _say(client, auth, "...")
        assert _reply_text(events) == "Можно коротко — одним словом. Что вы развиваете?"

    @pytest.mark.asyncio
    async def test_ru_schedule_options_are_understood(self, client):
        auth = await _start(client, locale="ru")
        await _to_step(client, auth, "schedule")
        await _say(client, auth, "Вечером")
        assert (await _user()).reminder_hour == 21


# ------------------------------------------------------------------ PATCH /api/goal


@pytest.mark.asyncio
class TestGoalPatch:
    async def _with_goal(self, client, email="person@example.com"):
        auth = await _start(client, email=email)
        await _say(client, auth, "Guitar")
        return auth

    async def test_patch_title_why_and_finish(self, client):
        auth = await self._with_goal(client)
        r = await client.patch(
            "/api/goal",
            json={"title": "Bass guitar", "why_text": "play in a band", "finish_line": "Gig in June"},
            headers=auth,
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert body["title"] == "Bass guitar" and body["why_text"] == "play in a band"
        assert body["finish_line"] == "Gig in June"
        assert body["finish_set_on"] == local_today(TZ).isoformat()
        goal = await _goal()
        assert goal.title == "Bass guitar" and goal.why_message_id is None

    async def test_null_finish_means_no_finish_and_missing_keys_stay(self, client):
        auth = await self._with_goal(client)
        await client.patch("/api/goal", json={"finish_line": "Gig in June"}, headers=auth)
        r = await client.patch("/api/goal", json={"finish_line": None}, headers=auth)
        assert r.json()["finish_line"] is None and r.json()["finish_set_on"] is None
        r = await client.patch("/api/goal", json={"title": "Bass"}, headers=auth)
        assert r.json()["title"] == "Bass" and r.json()["finish_line"] is None

    async def test_no_goal_is_404_and_anonymous_is_401(self, client):
        auth = await _start(client)
        r = await client.patch("/api/goal", json={"title": "x"}, headers=auth)
        assert r.status_code == 404 and r.json()["detail"]["code"] == "not_found"
        assert (await client.patch("/api/goal", json={"title": "x"})).status_code == 401

    async def test_one_person_cannot_change_anothers_goal(self, client):
        a = await self._with_goal(client, email="a@example.com")
        b = await self._with_goal(client, email="b@example.com")
        r = await client.patch("/api/goal", json={"title": "B goal"}, headers=b)
        assert r.status_code == 200
        assert (await _goal("a@example.com")).title == "Game development"
        assert (await _goal("b@example.com")).title == "B goal"
        await client.patch("/api/goal", json={"finish_line": "A finish"}, headers=a)
        assert (await _goal("b@example.com")).finish_line is None
