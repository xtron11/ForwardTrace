"""Stage 9: research events with day number, language and channel, and the admin panel on
v2 data (D1/D7 by cohort, replies to the AI's first message, "helped" with and without a
quotation, inaccurate quotations, safety-flagged conversations, cost per conversation).

Providers are the usual fakes from conftest.py.
"""

import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select, update

from app.config import settings
from app.db import SessionLocal
from app.models import (
    Conversation,
    Event,
    Fact,
    Goal,
    Message,
    MonthlySummary,
    Outreach,
    Pair,
    Thread,
    User,
)
from app.services import adminstats
from app.time_utils import local_today
from conftest import FIRST_RESULTS, parse_sse, register

pytestmark = pytest.mark.asyncio

TZ = "America/Los_Angeles"
TODAY = "/api/conversations/today"
MESSAGES = "/api/conversations/today/messages"
PLATEAU = "/api/conversations/today/plateau"
OPTIONS = FIRST_RESULTS["motivation"]["finish_options"]


# ------------------------------------------------------------------ helpers


async def _person(client, email="person@example.com", onboarded=True):
    auth = await register(client, email=email, locale="en", timezone=TZ)
    async with SessionLocal() as db:
        user = (await db.execute(select(User).where(User.email == email))).scalar_one()
        user.first_conversation_done = onboarded
        await db.commit()
        return auth, user.id


async def _events(kind: str) -> list[Event]:
    async with SessionLocal() as db:
        return list((await db.execute(select(Event).where(Event.type == kind))).scalars())


async def _one(kind: str) -> Event:
    rows = await _events(kind)
    assert len(rows) == 1, f"{kind}: {len(rows)} events"
    return rows[0]


def _stamped(event: Event, day: int = 1) -> None:
    """The three facts about the person every event carries."""
    assert event.payload["day_number"] == day
    assert event.payload["language"] == "en"
    assert event.payload["channel"] == "push"


async def _say(client, auth, text="I found the leak with the profiler today."):
    r = await client.post(MESSAGES, json={"text": text}, headers=auth)
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


async def _day(user_id, day, *, counts=True, level=0) -> Conversation:
    async with SessionLocal() as db:
        conv = Conversation(user_id=user_id, local_date=day, counts_for_limit=counts, safety_level=level)
        db.add(conv)
        await db.commit()
        return conv


async def _reply(conv, *, rating=None, used=None, cost=None, role="assistant", text="ok"):
    async with SessionLocal() as db:
        msg = Message(
            conversation_id=conv.id,
            user_id=conv.user_id,
            role=role,
            content_raw=text,
            content=[{"type": "text", "text": text}],
            rating=rating,
            used_fact_ids=used,
            cost_usd=cost,
        )
        db.add(msg)
        await db.commit()
        return msg


async def _fact(user_id, quote="said this", flagged=False) -> Fact:
    async with SessionLocal() as db:
        fact = Fact(
            user_id=user_id, local_date=date(2026, 9, 1), type="struggle", text=quote, quote=quote,
            flagged_at=datetime.now(timezone.utc) if flagged else None,
        )
        db.add(fact)
        await db.commit()
        return fact


async def _admin(client):
    r = await client.post(
        "/admin/login", data={"email": "admin@example.com", "password": "supersecret1"}
    )
    assert r.status_code == 303


# ------------------------------------------------------------------ server events


async def test_first_conversation_writes_its_events(client, monkeypatch):
    monkeypatch.setitem(FIRST_RESULTS, "motivation", {**FIRST_RESULTS["motivation"], "quote": "get into the university"})
    pairs = [{"then_quote": "used to freeze on the phone", "now_quote": "now I take calls", "theme": "Calls"}]
    monkeypatch.setitem(FIRST_RESULTS, "baseline", {**FIRST_RESULTS["baseline"], "pairs": pairs})
    auth, _ = await _person(client, onboarded=False)
    await client.get(TODAY, headers=auth)

    await _say(client, auth, "I make a small game")
    await _say(client, auth, "I want to get into the university on a grant")
    await _say(client, auth, OPTIONS[0])
    await _say(client, auth, "I used to freeze on the phone and now I take calls at work")
    await _say(client, auth, "8 pm")

    steps = await _events("first_conversation_step")
    assert sorted(e.payload["step"] for e in steps) == sorted(
        ["skill", "motivation", "finish", "baseline", "schedule"]
    )
    for step in steps:
        _stamped(step)
    for kind in ("anchor_saved", "finish_set", "start_comparison_shown", "onboarding_completed"):
        _stamped(await _one(kind))
    assert (await _one("start_comparison_shown")).payload["pairs"] == 1
    assert len(await _events("message_sent")) == 5
    assert len(await _events("ai_reply")) == 5
    assert all(e.payload["kind"] == "first" for e in await _events("ai_reply"))


async def test_message_ai_reply_rating_and_flag_events(client):
    auth, user_id = await _person(client)
    events = await _say(client, auth)
    [done] = [d for e, d in events if e == "done"]

    sent = await _one("message_sent")
    _stamped(sent)
    assert sent.payload["source"] == "text" and sent.payload["words"] == 8
    reply = await _one("ai_reply")
    _stamped(reply)
    assert reply.payload["message_id"] == done["message_id"]
    assert reply.payload["with_quote"] is False and reply.payload["intent"] == "normal"

    r = await client.post(f"/api/messages/{done['message_id']}/rating", json={"rating": "helped"}, headers=auth)
    assert r.status_code == 204
    rated = await _one("reply_rated")
    _stamped(rated)
    assert rated.payload["rating"] == "helped" and rated.payload["with_quote"] is False

    fact = await _fact(user_id)
    assert (await client.post(f"/api/facts/{fact.id}/flag", headers=auth)).status_code == 204
    assert (await client.post(f"/api/facts/{fact.id}/flag", headers=auth)).status_code == 204
    _stamped(await _one("quote_flagged"))  # the repeat changed nothing, so one event


async def test_plateau_and_search_events(client):
    auth, _ = await _person(client)
    await _say(client, auth, "The renderer is slow again today.")
    assert (await client.post(PLATEAU, headers=auth)).status_code == 200
    _stamped(await _one("plateau_triggered"))

    assert (await client.get("/api/search", params={"q": "renderer"}, headers=auth)).status_code == 200
    _stamped(await _one("search_used"))
    await client.get("/api/search", params={"q": " "}, headers=auth)
    assert len(await _events("search_used")) == 1  # an empty query is not a search


async def test_outreach_replied_when_the_person_answers_the_ai(client):
    auth, user_id = await _person(client)
    conv = (await client.get(TODAY, headers=auth)).json()
    async with SessionLocal() as db:
        db.add(Outreach(user_id=user_id, conversation_id=uuid.UUID(conv["id"]), topic="thread", channel="push", delivered=True))
        await db.commit()
    await _say(client, auth)
    replied = await _one("outreach_replied")
    _stamped(replied)
    assert replied.payload["topic"] == "thread"
    await _say(client, auth, "And one more thing.")
    assert len(await _events("outreach_replied")) == 1


async def test_thread_events(client):
    auth, user_id = await _person(client)
    async with SessionLocal() as db:
        thread = Thread(user_id=user_id, title="Phone calls", opened_on=local_today(TZ))
        db.add(thread)
        await db.commit()
    r = await client.patch(f"/api/threads/{thread.id}", json={"status": "closed"}, headers=auth)
    assert r.status_code == 200
    closed = await _one("thread_closed")
    _stamped(closed)
    assert closed.payload["by"] == "user"


async def test_thread_events_from_memory_extraction(client, monkeypatch):
    from app.services import memory
    from app.services.llm import LLMResult

    auth, user_id = await _person(client)
    text = "Honestly I freeze on the phone every time, and today I finally made the call."
    async with SessionLocal() as db:
        conv = Conversation(user_id=user_id, local_date=date(2026, 9, 1), counts_for_limit=True)
        db.add(conv)
        await db.flush()
        message = Message(
            conversation_id=conv.id, user_id=user_id, role="user", content_raw=text,
            content=[{"type": "text", "text": text}],
            created_at=datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc),
        )
        db.add(message)
        await db.commit()
        conv_id, message_id = conv.id, message.id

    answers = [
        {
            "facts": [{"message_id": str(message_id), "type": "struggle", "text": "phone", "quote": "I freeze on the phone every time"}],
            "threads": {"open": [{"title": "Phone calls", "fact_index": 0}], "mention": [], "close": []},
            "day_summary": "",
        },
    ]

    async def fake(system, user, schema):
        return LLMResult(data=answers[0], model="mock", elapsed_ms=1)

    monkeypatch.setattr(memory, "complete_json", fake)
    await memory.extract_memory(conv_id)
    _stamped(await _one("thread_opened"))

    async with SessionLocal() as db:
        thread = (await db.execute(select(Thread))).scalar_one()
    assert thread.title == "Phone calls"


async def test_progress_events(client):
    auth, user_id = await _person(client)
    then, now = await _fact(user_id, "then"), await _fact(user_id, "now")
    async with SessionLocal() as db:
        pair = Pair(user_id=user_id, then_fact_id=then.id, now_fact_id=now.id, theme="t", source="similarity")
        db.add(pair)
        db.add(Goal(user_id=user_id, title="Game dev", is_active=True, started_on=date(2026, 9, 1)))
        db.add(MonthlySummary(user_id=user_id, month=date(2026, 9, 1), status="thin", stats={}, content=None))
        await db.commit()

    assert (await client.post(f"/api/pairs/{pair.id}/hide", headers=auth)).status_code == 204
    assert (await client.post(f"/api/pairs/{pair.id}/hide", headers=auth)).status_code == 204
    _stamped(await _one("pair_hidden"))

    r = await client.patch("/api/goal", json={"finish_line": "Release on Steam"}, headers=auth)
    assert r.status_code == 200
    assert (await _one("finish_set")).payload["where"] == "profile"
    await client.patch("/api/goal", json={"finish_line": None}, headers=auth)
    assert len(await _events("finish_set")) == 1  # removing a finish line is not setting one

    r = await client.get("/api/progress/monthly?month=2026-09", headers=auth)
    assert r.status_code == 200, r.text
    await client.get("/api/progress/monthly?month=2026-09", headers=auth)
    _stamped(await _one("monthly_summary_viewed"))


# ------------------------------------------------------------------ client events


async def test_client_events_get_day_language_and_channel_from_the_server(client):
    auth, user_id = await _person(client)
    async with SessionLocal() as db:
        user = await db.get(User, user_id)
        user.created_at = datetime.now(timezone.utc) - timedelta(days=3)
        user.outreach_channel = "telegram"
        await db.commit()

    for kind in ("quote_opened", "feed_opened", "week_strip_day_opened", "progress_opened", "pair_shown", "paywall_viewed"):
        r = await client.post(
            "/api/events", json={"type": kind, "payload": {"day_number": 99, "pair_id": "p"}}, headers=auth
        )
        assert r.status_code == 201
        event = await _one(kind)
        assert event.user_id == user_id
        assert event.payload["day_number"] in (4, 3)  # day 1 is the registration day (their local date)
        assert event.payload["language"] == "en"
        assert event.payload["channel"] == "telegram"
    assert (await _one("pair_shown")).payload["pair_id"] == "p"


async def test_client_events_need_a_signed_in_person(client):
    assert (await client.post("/api/events", json={"type": "feed_opened"})).status_code == 401


# ------------------------------------------------------------------ admin numbers


async def test_retention_by_cohort_counts_only_people_whose_day_has_come(client):
    now = datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc)  # a Wednesday
    registered = datetime(2026, 10, 5, 18, 0, tzinfo=timezone.utc)  # Monday, 11:00 in Los Angeles
    ids = []
    for email in ("a@example.com", "b@example.com", "c@example.com"):
        _, uid = await _person(client, email=email)
        ids.append(uid)
    async with SessionLocal() as db:
        for uid in ids:
            (await db.get(User, uid)).created_at = registered
        (await db.get(User, ids[2])).created_at = datetime(2026, 10, 13, 18, 0, tzinfo=timezone.utc)
        await db.commit()
    await _day(ids[0], date(2026, 10, 6))   # a: D1 yes
    await _day(ids[0], date(2026, 10, 12))  # a: D7 yes
    await _day(ids[1], date(2026, 10, 6), counts=False)  # b: talked? no - did not count
    await _day(ids[2], date(2026, 10, 14))  # c: D1 yes, but D7 has not come

    cohorts = {c["week"]: c for c in await _retention(now)}
    first = cohorts["2026-10-05"]
    assert (first["size"], first["d1_of"], first["d1"]) == (2, 2, 0.5)
    assert (first["d7_of"], first["d7"]) == (2, 0.5)
    second = cohorts["2026-10-12"]
    assert (second["size"], second["d1"], second["d7_of"], second["d7"]) == (1, 1.0, 0, None)


async def _retention(now):
    async with SessionLocal() as db:
        return await adminstats.retention(db, now)


async def test_overview_metrics_on_seeded_data(client):
    _, a = await _person(client, email="a@example.com")
    _, b = await _person(client, email="b@example.com")
    c1 = await _day(a, date(2026, 10, 1))
    c2 = await _day(b, date(2026, 10, 1))
    quoted = await _fact(a, "quoted one")
    flagged = await _fact(a, "quoted two", flagged=True)
    await _reply(c1, rating="helped", used=[str(quoted.id)], cost=0.01)
    await _reply(c1, rating="not_it", used=[str(flagged.id)], cost=0.01)
    await _reply(c1, rating="helped", used=[])
    await _reply(c2, rating="not_it", used=None, cost=0.03)
    await _reply(c2, role="user", cost=None)  # a message with no cost recorded
    async with SessionLocal() as db:
        db.add_all([
            Outreach(user_id=a, conversation_id=c1.id, topic="thread", channel="push", delivered=True, replied_at=datetime.now(timezone.utc)),
            Outreach(user_id=b, conversation_id=c2.id, topic="thread", channel="push", delivered=True),
            Outreach(user_id=b, topic="thread", channel="push", delivered=False),  # never delivered: not counted
        ])
        await db.commit()

    async with SessionLocal() as db:
        data = await adminstats.overview(db)
    assert data["ai_first"] == {"sent": 2, "replied": 1, "opened": 0, "share": 0.5}
    assert data["helped"]["with_quote"] == {"helped": 1, "rated": 2, "share": 0.5}
    assert data["helped"]["without_quote"] == {"helped": 1, "rated": 2, "share": 0.5}
    assert data["flagged_quotes"] == {"shown": 2, "flagged": 1, "share": 0.5}
    assert data["cost"]["conversations"] == 2
    assert data["cost"]["average_usd"] == pytest.approx(0.025)  # (0.02 + 0.03) / 2


async def test_admin_pages_open_and_the_safety_conversation_is_linked(client):
    _, uid = await _person(client, email="admin@example.com")
    conv = await _day(uid, date(2026, 10, 1), level=3)
    await _day(uid, date(2026, 10, 2), level=1)
    await _reply(conv, role="user", text="I do not want to go on")
    await client.post("/api/events", json={"type": "feed_opened"}, headers=(await register(client, "x@example.com")))
    await _admin(client)

    home = await client.get("/admin")
    assert home.status_code == 200
    link = f"/admin/conversations/{conv.id}"
    assert link in home.text and "Разговоры с флагом безопасности" in home.text
    assert "/admin/conversations/" in home.text and home.text.count("/admin/conversations/") == 1  # level 1 is not listed

    page = await client.get(link)
    assert page.status_code == 200
    assert "I do not want to go on" in page.text

    assert "admin@example.com" in (await client.get("/admin/users")).text
    assert str(conv.id) in (await client.get(f"/admin/users/{uid}")).text
    assert "feed_opened" in (await client.get("/admin/events")).text
    # the unknown conversation does not open
    assert (await client.get(f"/admin/conversations/{uuid.uuid4()}")).status_code == 303


async def test_admin_json_is_for_admins_only(client):
    auth, uid = await _person(client, email="admin@example.com")
    conv = await _day(uid, date(2026, 10, 1), level=2)
    body = (await client.get("/api/admin/overview", headers=auth)).json()
    assert body["safety"][0]["url"] == f"/admin/conversations/{conv.id}"
    assert body["stt_provider"] and body["llm_model"]
    assert (await client.get(f"/api/admin/conversations/{conv.id}", headers=auth)).status_code == 200

    other = await register(client, "other@example.com")
    assert (await client.get("/api/admin/overview", headers=other)).status_code == 403
    assert (await client.get(f"/api/admin/conversations/{conv.id}", headers=other)).status_code == 403


async def test_admin_pages_need_the_admin_cookie(client):
    for path in ("/admin", "/admin/users", "/admin/events", f"/admin/conversations/{uuid.uuid4()}"):
        r = await client.get(path)
        assert r.status_code == 303 and r.headers["location"] == "/admin/login"


async def test_admin_no_longer_reads_v1_tables():
    root = Path(__file__).resolve().parent.parent / "app"
    for name in ("services/adminstats.py", "routers/admin.py", "routers/adminui.py"):
        source = (root / name).read_text(encoding="utf-8")
        for v1 in ("Entry", "Activity", "Report", "Task"):
            assert f"import {v1}" not in source and f" {v1}," not in source, f"{name} uses {v1}"
    for page in (root / "templates").glob("*.html"):
        assert page.stem not in ("entries", "feedback")
