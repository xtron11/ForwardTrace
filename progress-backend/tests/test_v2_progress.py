"""Stage 8: the Progress screen, "then -> now" cards, the monthly summary and its loop.

The model is a fake (`progress.complete_json` in conftest.py: MONTHLY_RESULT, MONTHLY_CALLS);
push is patched per test (`outreach.push.send_to_user`).
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import func, select

import conftest
import pytest
from app.config import settings
from app.db import SessionLocal
from app.models import (
    Conversation,
    Fact,
    Goal,
    Message,
    MonthlySummary,
    Outreach,
    Pair,
    Thread,
    User,
)
from app.services import outreach, progress
from app.services.llm import LLMError
from conftest import MONTHLY_CALLS, register

pytestmark = pytest.mark.asyncio

MONTH = date(2026, 9, 1)
# October 1st, 05:00 in Los Angeles is 12:00 UTC: the person's day is past CLOSE_DAY_HOUR (4).
FIRST = datetime(2026, 10, 1, 12, 0, tzinfo=timezone.utc)


# ------------------------------------------------------------------ helpers


async def _person(client, email="person@example.com", locale="en", tz="America/Los_Angeles", **fields):
    auth = await register(client, email=email, locale=locale, timezone=tz)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.first_conversation_done = True
        for key, value in fields.items():
            setattr(user, key, value)
        await db.commit()
        return auth, user.id


async def _goal(user_id, *, finish="Level B2", why="I want to talk to clients") -> uuid.UUID:
    async with SessionLocal() as db:
        goal = Goal(user_id=user_id, title="English", why_text=why, finish_line=finish)
        db.add(goal)
        await db.commit()
        return goal.id


async def _day(user_id, day: date, text="I fixed the jump today.") -> uuid.UUID:
    """A day the person talked: a counted conversation with one message of theirs."""
    async with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, local_date=day, counts_for_limit=True)
        db.add(conversation)
        await db.flush()
        message = Message(
            conversation_id=conversation.id, user_id=user_id, role="user", source="text",
            content_raw=text, content=[{"type": "text", "text": text}],
            created_at=datetime(day.year, day.month, day.day, 12, tzinfo=timezone.utc),
        )
        db.add(message)
        await db.commit()
        return message.id


async def _fact(user_id, day, quote, *, type="struggle", flagged=False, thread_id=None) -> uuid.UUID:
    async with SessionLocal() as db:
        fact = Fact(
            user_id=user_id, local_date=day, type=type, text=quote, quote=quote,
            thread_id=thread_id, flagged_at=datetime.now(timezone.utc) if flagged else None,
        )
        db.add(fact)
        await db.commit()
        return fact.id


async def _pair(user_id, then_id, now_id, theme="Collisions") -> uuid.UUID:
    async with SessionLocal() as db:
        pair = Pair(
            user_id=user_id, then_fact_id=then_id, now_fact_id=now_id, theme=theme,
            source="similarity",
        )
        db.add(pair)
        await db.commit()
        return pair.id


async def _thread(user_id, title, status="open", *, opened, closed=None, mentioned=None) -> uuid.UUID:
    async with SessionLocal() as db:
        thread = Thread(
            user_id=user_id, title=title, status=status, opened_on=opened, closed_on=closed,
            last_mentioned_on=mentioned or closed or opened,
        )
        db.add(thread)
        await db.commit()
        return thread.id


async def _month_of_talk(user_id, days=8) -> None:
    for i in range(days):
        await _day(user_id, MONTH + timedelta(days=i))


async def _pair_in_month(user_id, then_day, now_day, then_q="the jump broke", now_q="the jump works"):
    then = await _fact(user_id, then_day, then_q)
    now = await _fact(user_id, now_day, now_q, type="achievement")
    return await _pair(user_id, then, now), then, now


async def _summary(user_id) -> MonthlySummary | None:
    async with SessionLocal() as db:
        return (
            await db.execute(select(MonthlySummary).where(MonthlySummary.user_id == user_id))
        ).scalar_one_or_none()


def _pushes(monkeypatch) -> list[dict]:
    sent: list[dict] = []

    async def fake(db, user_id, payload):
        sent.append({"user_id": user_id, **payload})
        return 1

    monkeypatch.setattr(outreach.push, "send_to_user", fake)
    return sent


EMPTY_PROGRESS = {
    "goal": None, "level_facts": [], "pairs": [], "open_threads": [],
    "closed_threads": [], "monthly": None,
}


# ------------------------------------------------------------------ GET /api/progress


async def test_progress_empty_person(client):
    auth, _ = await _person(client)
    assert (await client.get("/api/progress", headers=auth)).json() == EMPTY_PROGRESS


async def test_progress_requires_sign_in(client):
    assert (await client.get("/api/progress")).status_code == 401


async def test_progress_shows_goal_path_cards_threads_and_unviewed_summary(client):
    auth, uid = await _person(client)
    await _goal(uid)
    await _month_of_talk(uid)
    for i, quote in enumerate(["level A", "level B", "level C", "level D"]):
        await _fact(uid, date(2026, 9, 1 + i * 5), quote, type="level")
    await _fact(uid, date(2026, 9, 28), "a struggle, not a level")
    old, _, _ = await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 10), "old then", "old now")
    new, _, _ = await _pair_in_month(uid, date(2026, 9, 5), date(2026, 9, 25), "new then", "new now")
    await _thread(uid, "Collisions", opened=date(2026, 9, 3), mentioned=date(2026, 9, 20))
    await _thread(uid, "Menus", "closed", opened=date(2026, 9, 2), closed=date(2026, 9, 12))
    await _thread(uid, "Gone", "deleted", opened=date(2026, 9, 2))
    await progress.build_monthly(uid, MONTH)

    body = (await client.get("/api/progress", headers=auth)).json()

    assert body["goal"]["title"] == "English"
    assert body["goal"]["finish_line"] == "Level B2"
    assert body["goal"]["why_text"] == "I want to talk to clients"
    # The last three "level" facts, newest first, with their dates; nothing else.
    assert [(f["quote"], f["local_date"]) for f in body["level_facts"]] == [
        ("level D", "2026-09-16"), ("level C", "2026-09-11"), ("level B", "2026-09-06"),
    ]
    # New cards on top, each with two quotes and a theme.
    assert [p["id"] for p in body["pairs"]] == [str(new), str(old)]
    first = body["pairs"][0]
    assert (first["then"]["quote"], first["now"]["quote"]) == ("new then", "new now")
    assert first["theme"] == "Collisions"
    assert [t["title"] for t in body["open_threads"]] == ["Collisions"]
    assert [t["title"] for t in body["closed_threads"]] == ["Menus"]
    assert body["monthly"]["month"] == "2026-09"
    assert body["monthly"]["status"] == "done"
    assert body["monthly"]["viewed_at"] is None


async def test_progress_without_finish_line_sends_null(client):
    auth, uid = await _person(client)
    await _goal(uid, finish=None)
    assert (await client.get("/api/progress", headers=auth)).json()["goal"]["finish_line"] is None


async def test_progress_hides_hidden_cards_and_flagged_facts(client):
    auth, uid = await _person(client)
    shown, _, _ = await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 20), "t1", "n1")
    hidden, _, _ = await _pair_in_month(uid, date(2026, 9, 3), date(2026, 9, 21), "t2", "n2")
    flagged, _, _ = await _pair_in_month(uid, date(2026, 9, 4), date(2026, 9, 22), "t3", "n3")
    async with SessionLocal() as db:
        (await db.get(Pair, hidden)).hidden_at = datetime.now(timezone.utc)
        pair = await db.get(Pair, flagged)
        (await db.get(Fact, pair.then_fact_id)).flagged_at = datetime.now(timezone.utc)
        await db.commit()
    await _fact(uid, date(2026, 9, 5), "inaccurate level", type="level", flagged=True)

    body = (await client.get("/api/progress", headers=auth)).json()

    assert [p["id"] for p in body["pairs"]] == [str(shown)]
    assert body["level_facts"] == []


async def test_progress_is_isolated_between_people(client):
    mine, _ = await _person(client, "me@example.com")
    _, other = await _person(client, "other@example.com")
    await _goal(other)
    await _pair_in_month(other, date(2026, 9, 2), date(2026, 9, 20))
    await _fact(other, date(2026, 9, 5), "their level", type="level")
    await _thread(other, "Theirs", opened=date(2026, 9, 3))
    await _month_of_talk(other)
    await progress.build_monthly(other, MONTH)

    assert (await client.get("/api/progress", headers=mine)).json() == EMPTY_PROGRESS


# ------------------------------------------------------------------ POST /api/pairs/{id}/hide


async def test_hide_pair_removes_the_card_and_is_repeatable(client):
    auth, uid = await _person(client)
    pair, _, _ = await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 20))

    assert (await client.post(f"/api/pairs/{pair}/hide", headers=auth)).status_code == 204
    assert (await client.post(f"/api/pairs/{pair}/hide", headers=auth)).status_code == 204

    assert (await client.get("/api/progress", headers=auth)).json()["pairs"] == []
    async with SessionLocal() as db:
        assert (await db.get(Pair, pair)).hidden_at is not None


async def test_hide_pair_of_someone_else_is_not_found(client):
    mine, _ = await _person(client, "me@example.com")
    theirs, other = await _person(client, "other@example.com")
    pair, _, _ = await _pair_in_month(other, date(2026, 9, 2), date(2026, 9, 20))

    r = await client.post(f"/api/pairs/{pair}/hide", headers=mine)

    assert r.status_code == 404
    assert r.json()["detail"]["code"] == "not_found"
    assert len((await client.get("/api/progress", headers=theirs)).json()["pairs"]) == 1
    assert (await client.post(f"/api/pairs/{uuid.uuid4()}/hide", headers=mine)).status_code == 404


# ------------------------------------------------------------------ GET /api/progress/monthly


async def test_monthly_marks_viewed_on_first_open_only(client):
    auth, uid = await _person(client)
    await _month_of_talk(uid)
    await progress.build_monthly(uid, MONTH)

    first = await client.get("/api/progress/monthly?month=2026-09", headers=auth)
    assert first.status_code == 200
    stamp = first.json()["viewed_at"]
    assert stamp is not None
    second = (await client.get("/api/progress/monthly?month=2026-09", headers=auth)).json()
    # (SQLite hands the stamp back without its zone; Postgres keeps it.)
    assert second["viewed_at"][:19] == stamp[:19]
    # Once seen it no longer sits on top of the Progress screen.
    assert (await client.get("/api/progress", headers=auth)).json()["monthly"] is None


async def test_monthly_unknown_month_and_other_people_are_not_found(client):
    mine, _ = await _person(client, "me@example.com")
    _, other = await _person(client, "other@example.com")
    await _month_of_talk(other)
    await progress.build_monthly(other, MONTH)

    assert (await client.get("/api/progress/monthly?month=2026-09", headers=mine)).status_code == 404
    assert (await client.get("/api/progress/monthly?month=2020-01", headers=mine)).status_code == 404
    assert (await client.get("/api/progress/monthly?month=nope", headers=mine)).status_code == 422
    assert (await client.get("/api/progress/monthly", headers=mine)).status_code == 422


async def test_monthly_failed_summary_is_not_shown(client, monkeypatch):
    auth, uid = await _person(client)
    await _month_of_talk(uid)

    async def broken(system, user, schema):
        raise LLMError("down")

    monkeypatch.setattr(progress, "complete_json", broken)
    await progress.build_monthly(uid, MONTH)

    assert (await _summary(uid)).status == "failed"
    assert (await client.get("/api/progress/monthly?month=2026-09", headers=auth)).status_code == 404
    assert (await client.get("/api/progress", headers=auth)).json()["monthly"] is None


# ------------------------------------------------------------------ build_monthly


async def test_no_conversations_no_summary(client):
    _, uid = await _person(client)
    # A conversation the AI started and the person never answered does not count.
    async with SessionLocal() as db:
        db.add(Conversation(user_id=uid, local_date=MONTH, started_by="ai", counts_for_limit=False))
        await db.commit()

    assert await progress.build_monthly(uid, MONTH) is None
    assert await _summary(uid) is None
    assert MONTHLY_CALLS == []


async def test_thin_month_counts_in_code_and_never_calls_the_model(client):
    _, uid = await _person(client)
    await _month_of_talk(uid, days=3)
    await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 20))  # one pair, below the minimum
    await _thread(uid, "Menus", "closed", opened=date(2026, 9, 2), closed=date(2026, 9, 12))
    await _fact(uid, date(2026, 9, 6), "level one", type="level")
    await _day(uid, date(2026, 8, 30))  # another month: must not leak in

    row = await progress.build_monthly(uid, MONTH)

    assert MONTHLY_CALLS == []
    assert row.status == "thin"
    assert row.content is None
    assert row.stats["days"] == 3
    assert row.stats["conversations"] == 3
    assert row.stats["closed_threads"] == 1
    assert row.stats["new_pairs"] == 1
    assert row.stats["level_facts"] == 1


async def test_enough_conversations_or_enough_pairs_calls_the_model(client):
    _, one = await _person(client, "a@example.com")
    await _month_of_talk(one, days=settings.monthly_min_conversations)
    _, two = await _person(client, "b@example.com")
    await _day(two, MONTH)
    await _pair_in_month(two, date(2026, 9, 2), date(2026, 9, 20), "t1", "n1")
    await _pair_in_month(two, date(2026, 9, 3), date(2026, 9, 21), "t2", "n2")

    assert (await progress.build_monthly(one, MONTH)).status == "done"
    assert (await progress.build_monthly(two, MONTH)).status == "done"
    assert len(MONTHLY_CALLS) == 2


async def test_done_summary_keeps_only_quotes_of_passed_facts(client, monkeypatch):
    auth, uid = await _person(client)
    await _goal(uid)
    await _month_of_talk(uid)
    pair, then, now = await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 20))
    outside = await _fact(uid, date(2026, 9, 7), "never offered to the model")
    _, stranger_id = await _person(client, "x@example.com")
    stranger = await _fact(stranger_id, date(2026, 9, 7), "another person's words")
    thread = await _thread(uid, "Collisions", opened=date(2026, 9, 3), mentioned=date(2026, 9, 20))
    struggle = await _fact(uid, date(2026, 9, 20), "collisions again", thread_id=thread)
    monkeypatch.setitem(
        conftest.MONTHLY_RESULT, "intro", f"Before: {{{{quote:{then}}}}} Now: {{{{quote:{now}}}}}."
    )
    monkeypatch.setitem(
        conftest.MONTHLY_RESULT, "open_struggle", f"Still: {{{{quote:{struggle}}}}} {{{{quote:{outside}}}}}"
    )
    monkeypatch.setitem(conftest.MONTHLY_RESULT, "next_step", f"Test it. {{{{quote:{stranger}}}}}")

    await progress.build_monthly(uid, MONTH)
    body = (await client.get("/api/progress/monthly?month=2026-09", headers=auth)).json()

    def quotes(segments):
        return [s["quote"] for s in segments if s["type"] == "quote"]

    content = body["content"]
    assert quotes(content["intro"]) == ["the jump broke", "the jump works"]
    assert quotes(content["open_struggle"]) == ["collisions again"]
    assert quotes(content["next_step"]) == []
    everything = str(content)
    assert "never offered" not in everything and "another person" not in everything
    assert "{{" not in everything
    # The numbers and the cards come from code, not from the model.
    assert body["stats"]["days"] == 8
    assert [p["id"] for p in body["stats"]["pairs"]] == [str(pair)]
    assert body["stats"]["why_text"] == "I want to talk to clients"
    # The model was handed the offered facts and nothing else.
    assert str(then) in MONTHLY_CALLS[0] and str(struggle) in MONTHLY_CALLS[0]
    assert str(outside) not in MONTHLY_CALLS[0]


async def test_flagged_fact_disappears_from_a_stored_summary(client, monkeypatch):
    auth, uid = await _person(client)
    await _month_of_talk(uid)
    _, _, now = await _pair_in_month(uid, date(2026, 9, 2), date(2026, 9, 20))
    monkeypatch.setitem(conftest.MONTHLY_RESULT, "intro", f"Now: {{{{quote:{now}}}}}.")
    await progress.build_monthly(uid, MONTH)

    assert (await client.post(f"/api/facts/{now}/flag", headers=auth)).status_code == 204
    body = (await client.get("/api/progress/monthly?month=2026-09", headers=auth)).json()

    assert all(s["type"] == "text" for s in body["content"]["intro"])
    assert body["stats"]["pairs"] == []


async def test_cards_are_the_three_with_the_longest_time_between(client):
    auth, uid = await _person(client)
    await _month_of_talk(uid)
    ids = {}
    spans = {"d5": (1, 6), "d25": (1, 26), "d10": (2, 12), "d20": (3, 23), "d1": (4, 5)}
    for name, (a, b) in spans.items():
        ids[name], _, _ = await _pair_in_month(
            uid, date(2026, 9, a), date(2026, 9, b), f"then {name}", f"now {name}"
        )
    await progress.build_monthly(uid, MONTH)

    body = (await client.get("/api/progress/monthly?month=2026-09", headers=auth)).json()

    assert body["stats"]["new_pairs"] == 5
    assert [p["id"] for p in body["stats"]["pairs"]] == [
        str(ids["d25"]), str(ids["d20"]), str(ids["d10"])
    ]


async def test_percentages_fail_the_summary_and_the_next_run_retries(client, monkeypatch):
    _, uid = await _person(client)
    await _month_of_talk(uid)
    monkeypatch.setitem(conftest.MONTHLY_RESULT, "intro", "You improved by 40% this month.")

    row = await progress.build_monthly(uid, MONTH)
    assert row.status == "failed" and row.content is None

    monkeypatch.setitem(conftest.MONTHLY_RESULT, "intro", "A calm month.")
    again = await progress.build_monthly(uid, MONTH)
    assert again.status == "done"
    assert again.id == row.id
    async with SessionLocal() as db:
        assert (await db.scalar(select(func.count()).select_from(MonthlySummary))) == 1


async def test_a_finished_summary_is_built_once(client):
    _, uid = await _person(client)
    await _month_of_talk(uid)

    first = await progress.build_monthly(uid, MONTH)
    second = await progress.build_monthly(uid, MONTH)

    assert first.id == second.id
    assert len(MONTHLY_CALLS) == 1


# ------------------------------------------------------------------ the notification


async def test_ready_summary_notifies_with_topic_monthly(client, monkeypatch):
    pushes = _pushes(monkeypatch)
    _, uid = await _person(client, locale="ru", outreach_channel="push")
    await _month_of_talk(uid)

    await progress.build_monthly(uid, MONTH)

    assert len(pushes) == 1
    assert pushes[0]["body"] == "Сводка за сентябрь готова"
    assert pushes[0]["url"].startswith("/today?o=")
    async with SessionLocal() as db:
        rows = list((await db.execute(select(Outreach).where(Outreach.user_id == uid))).scalars())
        assert [(r.topic, r.channel, r.delivered, r.message_id, r.conversation_id) for r in rows] == [
            ("monthly", "push", True, None, None)
        ]
        # It is not the AI writing first: no message, no unanswered count.
        assert (
            await db.scalar(select(func.count()).select_from(Message).where(Message.role == "assistant"))
        ) == 0
        assert (await db.get(User, uid)).outreach_unanswered == 0
    # Built once, notified once.
    await progress.build_monthly(uid, MONTH)
    assert len(pushes) == 1


async def test_no_notification_without_a_channel(client, monkeypatch):
    pushes = _pushes(monkeypatch)
    _, uid = await _person(client, outreach_channel="none")
    await _month_of_talk(uid)

    await progress.build_monthly(uid, MONTH)

    assert pushes == []
    async with SessionLocal() as db:
        assert (await db.scalar(select(func.count()).select_from(Outreach))) == 0
    assert (await _summary(uid)).status == "done"


# ------------------------------------------------------------------ the loop


async def test_loop_builds_on_the_first_after_close_day_hour_in_the_persons_time(client):
    _, la = await _person(client, "la@example.com", tz="America/Los_Angeles")
    _, tokyo = await _person(client, "tokyo@example.com", tz="Asia/Tokyo")
    await _month_of_talk(la)
    await _month_of_talk(tokyo)

    # 2026-10-01 05:00 in LA (12:00 UTC); in Tokyo it is 21:00 on the 1st.
    assert await progress.monthly_once(FIRST) == 2
    assert (await _summary(la)).month == MONTH
    assert (await _summary(tokyo)).month == MONTH


async def test_loop_waits_for_the_hour_and_skips_other_days(client):
    _, uid = await _person(client, tz="America/Los_Angeles")
    await _month_of_talk(uid)

    # Midnight UTC on the 1st is still September 30 in Los Angeles.
    assert await progress.monthly_once(datetime(2026, 10, 1, 0, 0, tzinfo=timezone.utc)) == 0
    # 02:00 local on the 1st is before CLOSE_DAY_HOUR.
    assert await progress.monthly_once(datetime(2026, 10, 1, 9, 0, tzinfo=timezone.utc)) == 0
    # The 2nd is not the day.
    assert await progress.monthly_once(datetime(2026, 10, 2, 12, 0, tzinfo=timezone.utc)) == 0
    assert await _summary(uid) is None
    assert MONTHLY_CALLS == []

    assert await progress.monthly_once(FIRST) == 1


async def test_loop_builds_once_per_month_and_retries_a_failure_later_that_day(client, monkeypatch):
    _, uid = await _person(client)
    await _month_of_talk(uid)
    calls = []

    async def flaky(system, user, schema):
        calls.append(1)
        if len(calls) == 1:
            raise LLMError("down")
        return await conftest.fake_monthly_json(system, user, schema)

    monkeypatch.setattr(progress, "complete_json", flaky)

    assert await progress.monthly_once(FIRST) == 0  # failed: not counted as built
    assert (await _summary(uid)).status == "failed"
    assert await progress.monthly_once(FIRST + timedelta(hours=1)) == 1
    assert (await _summary(uid)).status == "done"
    assert await progress.monthly_once(FIRST + timedelta(hours=2)) == 0
    assert len(calls) == 2


async def test_loop_skips_people_who_did_not_talk_and_deleted_accounts(client):
    _, quiet = await _person(client, "quiet@example.com")
    _, gone = await _person(client, "gone@example.com")
    await _month_of_talk(gone)
    async with SessionLocal() as db:
        (await db.get(User, gone)).deleted_at = FIRST
        await db.commit()

    assert await progress.monthly_once(FIRST) == 0
    assert await _summary(quiet) is None
    assert await _summary(gone) is None


async def test_the_loop_survives_a_failing_pass(monkeypatch):
    runs = []

    async def boom(now=None):
        runs.append(1)
        if len(runs) == 1:
            raise RuntimeError("db hiccup")
        raise asyncio.CancelledError

    monkeypatch.setattr(progress, "monthly_once", boom)
    monkeypatch.setattr(settings, "monthly_tick_minutes", 0)

    try:
        await progress.monthly_loop()
    except asyncio.CancelledError:
        pass
    assert len(runs) == 2
