"""Test suite.

Runs on SQLite with both AI providers mocked, so it needs no keys and no database
server:  pytest -q

What is tested is deliberately narrow: the invariants that, if they broke, would make
the product quietly lie rather than visibly fail. A misrouted activity or an invented
statistic does not raise an exception - it produces a confident, wrong report. Those
are the failures worth a test.
"""

import asyncio
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

# The environment is fixed in conftest.py, which pytest loads before this module.
from app.db import Base, SessionLocal, engine
from app.main import app
from app.models import Activity, Entry, Report, Status
from app.services import extraction, llm, prompts, ratelimit, verify
from app.services import reports as report_svc
from app.services.aggregate import compute_stats
from app.services.llm import LLMResult
from app.services.stt import STTResult

TRANSCRIPT = (
    "Today I coded for about two hours. I finished the API and I was stuck on "
    "authentication for a while, but I figured it out on my own without looking at a "
    "tutorial. I also listened to English for thirty minutes."
)

# Filled in by the fixtures; the fake model reads them so routing can be asserted.
GOALS: dict[str, str] = {}
EXTRACTION_RESPONSE: dict = {}
REPORT_RESPONSE: dict = {}


CAPTURED_STT_LOCALE: list[str | None] = []


async def fake_transcribe(path, mime=None, locale=None):
    CAPTURED_STT_LOCALE.append(locale)
    return STTResult(TRANSCRIPT, 58.0, "en", 640, "mock")


async def fake_complete_json(system, user, schema):
    if "extractor" in system:
        return LLMResult(data=EXTRACTION_RESPONSE, model="mock", elapsed_ms=900)
    if "criteria" in schema.get("properties", {}):
        return LLMResult(data={"criteria": ["A", "B", "C", "D"]}, model="mock", elapsed_ms=100)
    return LLMResult(data=REPORT_RESPONSE, model="mock", elapsed_ms=3200)


@pytest_asyncio.fixture(scope="function", autouse=True)
async def fresh_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    extraction.transcribe = fake_transcribe
    extraction.complete_json = fake_complete_json
    llm.complete_json = fake_complete_json
    report_svc.complete_json = fake_complete_json
    ratelimit.reset()
    yield


@pytest_asyncio.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as c:
        yield c


async def register(client, email="admin@example.com", locale="en"):
    r = await client.post(
        "/api/auth/register",
        json={
            "email": email,
            "password": "supersecret1",
            "timezone": "America/Los_Angeles",
            "locale": locale,
        },
    )
    assert r.status_code == 201, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


async def make_goal(client, auth, title, criteria):
    r = await client.post(
        "/api/goals",
        headers=auth,
        json={
            "title": title,
            "why_text": "Because it matters.",
            "criteria": [{"text": c} for c in criteria],
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


async def settle(client, url, auth, tries=80):
    for _ in range(tries):
        r = await client.get(url, headers=auth)
        assert r.status_code == 200, r.text
        if r.json()["status"] in ("done", "failed", "awaiting_review"):
            return r.json()
        await asyncio.sleep(0.05)
    raise AssertionError(f"{url} never settled")


# --------------------------------------------------------------- quote verification


class TestQuoteVerification:
    """The guard that stops a fluent invention becoming a stored fact."""

    def test_exact_quote_is_accepted(self):
        norm = verify.normalize(TRANSCRIPT)
        assert verify.quote_supported("I coded for about two hours", norm)

    def test_absent_quote_is_rejected(self):
        norm = verify.normalize(TRANSCRIPT)
        assert not verify.quote_supported("I went to the gym and did squats", norm)

    def test_minor_transcription_noise_still_matches(self):
        # Speech-to-text drops and mangles small words; demanding identity would throw
        # away true facts, so near-identity is the bar.
        norm = verify.normalize(TRANSCRIPT)
        assert verify.quote_supported("I coded for about two hour", norm)

    def test_trivially_short_quote_is_rejected(self):
        norm = verify.normalize(TRANSCRIPT)
        assert not verify.quote_supported("the", norm)

    def test_punctuation_and_case_are_ignored(self):
        norm = verify.normalize(TRANSCRIPT)
        assert verify.quote_supported("I FINISHED THE API!!!", norm)

    def test_category_variants_collapse_to_one_bucket(self):
        # Otherwise "coding" and "Coding" split the weekly total in half.
        known: dict[str, str] = {}
        display_a, key_a = verify.normalize_category("Programming", known)
        known[key_a] = display_a
        _display_b, key_b = verify.normalize_category("programming ", known)
        assert key_a == key_b


# --------------------------------------------------------------- extraction pipeline


class TestExtraction:
    @pytest.mark.asyncio
    async def test_hallucinated_activity_never_reaches_the_database(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        GOALS["prog"] = goal["id"]

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": goal["id"],
                        "category": "Programming",
                        "minutes": 120,
                        "minutes_explicit": True,
                        "details": ["finished the API"],
                        "quote": "I coded for about two hours",
                    },
                    {
                        "goal_id": goal["id"],
                        "category": "Gym",
                        "minutes": 45,
                        "minutes_explicit": True,
                        "details": ["squats"],
                        "quote": "I went to the gym and did squats for 45 minutes",
                    },
                ],
                "wins": [],
                "friction": [],
                "mood": "positive",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["status"] == "done"
        assert [a["category"] for a in entry["activities"]] == ["Programming"]
        assert entry["dropped_facts"] == 1

    @pytest.mark.asyncio
    async def test_unstated_duration_is_stored_as_null_not_guessed(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": goal["id"],
                        "category": "Programming",
                        # The model claims 90 minutes while admitting none was stated.
                        # Believing it would turn a guess into a weekly total.
                        "minutes": 90,
                        "minutes_explicit": False,
                        "details": [],
                        "quote": "I finished the API",
                    }
                ],
                "wins": [],
                "friction": [],
                "mood": "neutral",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        activity = entry["activities"][0]
        assert activity["minutes"] is None
        assert activity["minutes_explicit"] is False

    @pytest.mark.asyncio
    async def test_one_recording_is_split_across_goals(self, client):
        auth = await register(client)
        prog = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        eng = await make_goal(client, auth, "Improve English", ["Understand videos"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": prog["id"],
                        "category": "Programming",
                        "minutes": 120,
                        "minutes_explicit": True,
                        "details": [],
                        "quote": "I coded for about two hours",
                    },
                    {
                        "goal_id": eng["id"],
                        "category": "English",
                        "minutes": 30,
                        "minutes_explicit": True,
                        "details": [],
                        "quote": "I also listened to English for thirty minutes",
                    },
                ],
                "wins": [],
                "friction": [],
                "mood": "positive",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        routed = {a["category"]: a["goal_id"] for a in entry["activities"]}
        assert routed == {"Programming": prog["id"], "English": eng["id"]}

    @pytest.mark.asyncio
    async def test_invented_goal_id_leaves_the_item_unrouted(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": str(uuid.uuid4()),  # does not exist
                        "category": "Programming",
                        "minutes": 120,
                        "minutes_explicit": True,
                        "details": [],
                        "quote": "I coded for about two hours",
                    }
                ],
                "wins": [],
                "friction": [],
                "mood": "positive",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        # Unrouted is recoverable by the person; misfiled is invisible to them.
        assert entry["activities"][0]["goal_id"] is None
        assert goal["id"] is not None

    @pytest.mark.asyncio
    async def test_stated_quantities_are_captured_and_fabricated_ones_dropped(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Understand videos"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": goal["id"],
                        "category": "English",
                        "minutes": 30,
                        "minutes_explicit": True,
                        "details": ["listening"],
                        "metrics": [
                            {
                                "name": "minutes listened",
                                "value": 30,
                                "unit": "minutes",
                                "quote": "I also listened to English for thirty minutes",
                            },
                            {
                                # never said - must not become a weekly total
                                "name": "new words",
                                "value": 50,
                                "unit": "words",
                                "quote": "I learned fifty new words today",
                            },
                        ],
                        "quote": "I also listened to English for thirty minutes",
                    }
                ],
                "wins": [],
                "friction": [],
                "mood": "neutral",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        metrics = entry["activities"][0]["metrics"]
        assert [m["name"] for m in metrics] == ["minutes listened"]
        assert entry["dropped_facts"] == 1

    @pytest.mark.asyncio
    async def test_silent_recording_is_not_an_error(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Learn programming", ["Write code alone"])

        r = await client.post("/api/entries/text", headers=auth, json={"text": "uh"})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["status"] == "done"
        assert entry["activities"] == []


class TestEmailVerification:
    """The gate is at the door, not at the check-in: an unverified account cannot get
    a session at all."""

    @pytest.mark.asyncio
    async def test_registration_does_not_hand_out_a_session(self, client, monkeypatch):
        from app.config import settings
        from app.services import mail

        monkeypatch.setattr(settings, "resend_api_key", "test-key")
        links: list[str] = []

        async def fake_send(to, link, locale="en", name=None):
            links.append(link)
            return True

        monkeypatch.setattr(mail, "send_verification", fake_send)

        r = await client.post(
            "/api/auth/register",
            json={
                "email": "new@example.com",
                "password": "supersecret1",
                "timezone": "Asia/Almaty",
                "locale": "ru",
            },
        )
        assert r.status_code == 201, r.text
        body = r.json()
        assert body["verification_required"] is True
        assert "access_token" not in body, "a session here walks straight past the check"
        assert len(links) == 1

        # And logging in is refused until the link is followed.
        blocked = await client.post(
            "/api/auth/login",
            json={"email": "new@example.com", "password": "supersecret1"},
        )
        assert blocked.status_code == 403

        token = links[0].split("token=")[1]
        assert (
            await client.post("/api/auth/verify", json={"token": token})
        ).status_code == 200

        ok = await client.post(
            "/api/auth/login",
            json={"email": "new@example.com", "password": "supersecret1"},
        )
        assert ok.status_code == 200
        assert "access_token" in ok.json()

    @pytest.mark.asyncio
    async def test_resend_works_without_a_session_and_reveals_nothing(
        self, client, monkeypatch
    ):
        """There is no session to authenticate with yet, and the answer must be the
        same whether or not the address is registered here."""
        from app.config import settings
        from app.services import mail

        monkeypatch.setattr(settings, "resend_api_key", "test-key")
        sent: list[str] = []

        async def fake_send(to, link, locale="en", name=None):
            sent.append(to)
            return True

        monkeypatch.setattr(mail, "send_verification", fake_send)

        await client.post(
            "/api/auth/register",
            json={
                "email": "real@example.com",
                "password": "supersecret1",
                "timezone": "Asia/Almaty",
            },
        )
        sent.clear()

        known = await client.post(
            "/api/auth/resend-verification", json={"email": "real@example.com"}
        )
        unknown = await client.post(
            "/api/auth/resend-verification", json={"email": "nobody@example.com"}
        )
        assert known.status_code == unknown.status_code == 202
        assert known.json() == unknown.json()
        assert sent == [], "a second letter within the minute is not sent"

    @pytest.mark.asyncio
    async def test_a_letter_that_could_not_be_sent_undoes_the_account(
        self, client, monkeypatch
    ):
        """No session and no link means an unreachable account. Leaving it behind also
        blocks the address, so the person is told it is taken and still cannot get in."""
        from app.config import settings
        from app.services import mail

        monkeypatch.setattr(settings, "resend_api_key", "test-key")

        async def refuses(to, link, locale="en", name=None):
            return False

        monkeypatch.setattr(mail, "send_verification", refuses)

        body = {
            "email": "stranded@example.com",
            "password": "supersecret1",
            "timezone": "Asia/Almaty",
        }
        r = await client.post("/api/auth/register", json=body)
        assert r.status_code == 503

        # The address is free again, so they can simply try once more.
        async def works(to, link, locale="en", name=None):
            return True

        monkeypatch.setattr(mail, "send_verification", works)
        again = await client.post("/api/auth/register", json=body)
        assert again.status_code == 201

    @pytest.mark.asyncio
    async def test_a_forged_link_is_refused(self, client):
        r = await client.post("/api/auth/verify", json={"token": "not-a-real-token"})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_without_a_mail_provider_nobody_is_locked_out(self, client):
        """No key means no letter, and locking people out of a product that cannot
        send them a way back in would be the worst of both."""
        auth = await register(client)
        me = (await client.get("/api/auth/me", headers=auth)).json()
        assert me["email_verified"] is True


class TestGoalRequired:
    """A check-in with no goal is a diary entry the system cannot say anything about:
    nothing to route activities to, nothing to measure against, nothing to compare."""

    @pytest.mark.asyncio
    async def test_no_goal_means_no_check_in(self, client):
        auth = await register(client)

        typed = await client.post(
            "/api/entries/text", headers=auth, json={"text": TRANSCRIPT}
        )
        assert typed.status_code == 409

        voiced = await client.post(
            "/api/entries/voice",
            headers=auth,
            files={"audio": ("c.webm", b"x" * 2048, "audio/webm")},
        )
        assert voiced.status_code == 409

        # And it works the moment there is something to measure against.
        await make_goal(client, auth, "Improve English", ["Read"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )
        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        assert r.status_code == 202

    @pytest.mark.asyncio
    async def test_an_archived_goal_does_not_count(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read"])
        await client.patch(
            f"/api/goals/{goal['id']}", headers=auth, json={"is_active": False}
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        assert r.status_code == 409


class TestEntryAudio:
    @pytest.mark.asyncio
    async def test_a_recording_can_be_played_back_and_stays_private(self, client):
        """The transcript keeps the words and loses how someone sounded saying them."""
        auth = await register(client, "owner@example.com")
        await make_goal(client, auth, "Improve English", ["Read"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )

        r = await client.post(
            "/api/entries/voice",
            headers=auth,
            files={"audio": ("c.webm", b"x" * 2048, "audio/webm")},
        )
        entry_id = r.json()["id"]
        entry = (await client.get(f"/api/entries/{entry_id}", headers=auth)).json()
        assert entry["has_audio"] is True

        assert (
            await client.get(f"/api/entries/{entry_id}/audio", headers=auth)
        ).status_code == 200

        other = await register(client, "stranger@example.com")
        assert (
            await client.get(f"/api/entries/{entry_id}/audio", headers=other)
        ).status_code == 404

    @pytest.mark.asyncio
    async def test_a_typed_entry_has_nothing_to_play(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry_id = r.json()["id"]
        entry = (await client.get(f"/api/entries/{entry_id}", headers=auth)).json()
        assert entry["has_audio"] is False
        assert (
            await client.get(f"/api/entries/{entry_id}/audio", headers=auth)
        ).status_code == 404


class TestQuotas:
    """Without these, one hostile signup drains the API balance in an afternoon."""

    @pytest.mark.asyncio
    async def test_voice_check_ins_are_capped_per_day(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_voice_entries_per_day", 2)
        auth = await register(client)
        await make_goal(client, auth, "Learn programming", ["Write code alone"])

        audio = {"audio": ("c.webm", b"x" * 2048, "audio/webm")}
        for i in range(2):
            r = await client.post("/api/entries/voice", headers=auth, files=audio)
            assert r.status_code == 202, f"upload {i}: {r.text}"

        r = await client.post("/api/entries/voice", headers=auth, files=audio)
        assert r.status_code == 429
        assert "2" in r.json()["detail"]

    @pytest.mark.asyncio
    async def test_typed_check_ins_have_their_own_higher_cap(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_voice_entries_per_day", 1)
        monkeypatch.setattr(settings, "max_text_entries_per_day", 3)
        auth = await register(client)
        await make_goal(client, auth, "Learn programming", ["Write code alone"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        # Voice being exhausted must not block typing, which costs no speech-to-text.
        for _ in range(3):
            r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
            assert r.status_code == 202, r.text

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_one_users_quota_does_not_affect_another(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "max_voice_entries_per_day", 1)
        audio = {"audio": ("c.webm", b"x" * 2048, "audio/webm")}

        auth_a = await register(client, "a@example.com")
        await make_goal(client, auth_a, "Goal A", ["Something"])
        assert (await client.post("/api/entries/voice", headers=auth_a, files=audio)).status_code == 202
        assert (await client.post("/api/entries/voice", headers=auth_a, files=audio)).status_code == 429

        auth_b = await register(client, "b@example.com")
        await make_goal(client, auth_b, "Goal B", ["Something"])
        assert (await client.post("/api/entries/voice", headers=auth_b, files=audio)).status_code == 202


# --------------------------------------------------------------- statistics


class TestStatistics:
    """Numbers are computed here, never by the model. These tests are why."""

    @pytest.mark.asyncio
    async def test_totals_streaks_and_goal_isolation(self, client):
        auth = await register(client)
        prog = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        eng = await make_goal(client, auth, "Improve English", ["Understand videos"])

        async with SessionLocal() as db:
            user_id = uuid.UUID(
                (await client.get("/api/auth/me", headers=auth)).json()["id"]
            )
            today = date(2026, 8, 20)
            # Aug 14, 15, 16 then a gap then Aug 18, 19: longest streak is 3.
            for offset, minutes in [(6, 120), (5, 45), (4, 90), (2, 150), (1, 60)]:
                entry = Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=offset),
                    source="text",
                    raw_transcript=TRANSCRIPT,
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(prog["id"]),
                        local_date=entry.local_date,
                        category="Programming",
                        category_key="programming",
                        minutes=minutes,
                        minutes_explicit=True,
                        details=[],
                        quote="I coded for about two hours",
                    )
                )
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(eng["id"]),
                        local_date=entry.local_date,
                        category="English",
                        category_key="english",
                        minutes=30,
                        minutes_explicit=True,
                        details=[],
                        quote="I also listened to English for thirty minutes",
                    )
                )
            await db.commit()

            stats = await compute_stats(
                db, user_id, uuid.UUID(prog["id"]), today - timedelta(days=6), today
            )

        assert stats["total_minutes"] == 465
        assert stats["days_logged"] == 5
        assert stats["longest_streak"] == 3
        # English must not leak into a Programming report.
        assert [c["category"] for c in stats["categories"]] == ["Programming"]

    @pytest.mark.asyncio
    async def test_stated_quantities_sum_across_the_week(self, client):
        """Ten words a day for six days is sixty words - the point of storing them."""
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Understand videos"])

        async with SessionLocal() as db:
            user_id = uuid.UUID((await client.get("/api/auth/me", headers=auth)).json()["id"])
            today = date(2026, 8, 20)
            for offset in range(6):
                entry = Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=offset),
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=entry.local_date,
                        category="English",
                        category_key="english",
                        minutes=30,
                        minutes_explicit=True,
                        details=[],
                        metrics=[
                            {"name": "new words", "value": 10, "unit": "words", "quote": "q"}
                        ],
                        quote="q",
                    )
                )
            await db.commit()
            stats = await compute_stats(
                db, user_id, uuid.UUID(goal["id"]), today - timedelta(days=6), today
            )

        assert stats["metrics"] == [
            {"name": "new words", "unit": "words", "total": 60, "occasions": 6}
        ]

    @pytest.mark.asyncio
    async def test_time_coverage_flags_partly_unmeasured_totals(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])

        async with SessionLocal() as db:
            user_id = uuid.UUID(
                (await client.get("/api/auth/me", headers=auth)).json()["id"]
            )
            today = date(2026, 8, 20)
            entry = Entry(
                user_id=user_id,
                local_date=today,
                source="text",
                status=Status.done.value,
                wins=[],
                friction=[],
            )
            db.add(entry)
            await db.flush()
            for minutes in (60, None):
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=today,
                        category="Programming",
                        category_key="programming",
                        minutes=minutes,
                        minutes_explicit=minutes is not None,
                        details=[],
                        quote="q",
                    )
                )
            await db.commit()
            stats = await compute_stats(
                db, user_id, uuid.UUID(goal["id"]), today - timedelta(days=6), today
            )

        assert stats["categories"][0]["time_coverage"] == 0.5


# --------------------------------------------------------------- report validation


class TestReportValidation:
    @pytest.mark.asyncio
    async def test_invented_criterion_dropped_and_empty_evidence_downgraded(self, client):
        auth = await register(client)
        goal = await make_goal(
            client, auth, "Learn programming", ["Write code alone", "Solve hard problems"]
        )
        first, second = (c["id"] for c in goal["criteria"])

        REPORT_RESPONSE.clear()
        REPORT_RESPONSE.update(
            {
                "what_you_did": "Four sessions.",
                "what_changed": [{"text": "You shipped something.", "evidence": "Built the API."}],
                "pattern": {"text": "You do better on projects.", "confidence": "high"},
                "friction": "Focus slipped.",
                "recommendation": "Name one thing to build.",
                "closing": "You are not where you were.",
                "criteria_progress": [
                    {"criterion_id": first, "status": "clear_evidence", "evidence": "Built the API."},
                    # id that does not belong to this goal
                    {"criterion_id": str(uuid.uuid4()), "status": "clear_evidence", "evidence": "x"},
                    # claims evidence, supplies none
                    {"criterion_id": second, "status": "clear_evidence", "evidence": ""},
                ],
            }
        )

        async with SessionLocal() as db:
            user_id = uuid.UUID(
                (await client.get("/api/auth/me", headers=auth)).json()["id"]
            )
            today = date(2026, 8, 20)
            for offset in range(4):
                entry = Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=offset),
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=entry.local_date,
                        category="Programming",
                        category_key="programming",
                        minutes=60,
                        minutes_explicit=True,
                        details=[],
                        quote="q",
                    )
                )
            await db.commit()

        r = await client.post(
            "/api/reports",
            headers=auth,
            json={"goal_id": goal["id"], "period_end": "2026-08-20", "force": True},
        )
        report = await settle(client, f"/api/reports/{r.json()['id']}", auth)

        assert report["status"] == "done", report
        progress = {p["criterion_id"]: p["status"] for p in report["content"]["criteria_progress"]}
        assert progress == {first: "clear_evidence", second: "no_evidence"}

    @pytest.mark.asyncio
    async def test_evidence_that_denies_itself_is_downgraded(self, client):
        """"Some evidence" plus "there is no sign of this" is a contradiction the
        reader will notice immediately. Catch it rather than print it."""
        auth = await register(client)
        goal = await make_goal(
            client, auth, "Improve English", ["Speak in simple phrases", "Hold a chat"]
        )
        first, second = (c["id"] for c in goal["criteria"])
        await self._seed_minimum(client, auth, goal)

        REPORT_RESPONSE["criteria_progress"] = [
            {
                "criterion_id": first,
                "status": "some_evidence",
                "evidence": "This week you worked with texts, but there is no sign of speaking.",
            },
            {
                "criterion_id": second,
                "status": "some_evidence",
                "evidence": "На этой неделе нет фактов разговорной практики.",
            },
        ]

        r = await client.post(
            "/api/reports",
            headers=auth,
            json={"goal_id": goal["id"], "period_end": "2026-08-20", "force": True},
        )
        report = await settle(client, f"/api/reports/{r.json()['id']}", auth)

        progress = {p["criterion_id"]: p for p in report["content"]["criteria_progress"]}
        assert progress[first]["status"] == "no_evidence"
        assert progress[second]["status"] == "no_evidence", "denial in Russian must count too"
        assert progress[first]["evidence"] == ""

    @pytest.mark.asyncio
    async def test_report_is_cached_not_regenerated(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        await self._seed_minimum(client, auth, goal)

        body = {"goal_id": goal["id"], "period_end": "2026-08-20", "force": True}
        first = await client.post("/api/reports", headers=auth, json=body)
        settled = await settle(client, f"/api/reports/{first.json()['id']}", auth)

        again = await client.post(
            "/api/reports",
            headers=auth,
            json={"goal_id": goal["id"], "period_end": "2026-08-20"},
        )
        assert again.json()["id"] == settled["id"]
        assert again.json()["content"] == settled["content"]

    @pytest.mark.asyncio
    async def test_goal_title_is_snapshotted_against_later_renames(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        await self._seed_minimum(client, auth, goal)

        r = await client.post(
            "/api/reports",
            headers=auth,
            json={"goal_id": goal["id"], "period_end": "2026-08-20", "force": True},
        )
        report = await settle(client, f"/api/reports/{r.json()['id']}", auth)
        assert report["stats"]["goal_title"] == "Learn programming"

        await client.patch(
            f"/api/goals/{goal['id']}", headers=auth, json={"title": "Something else"}
        )
        after = (await client.get(f"/api/reports/{report['id']}", headers=auth)).json()
        # A rename must not rewrite the meaning of a report already read.
        assert after["stats"]["goal_title"] == "Learn programming"

    @pytest.mark.asyncio
    async def test_first_report_accepts_two_check_ins(self, client):
        """Three check-ins in a three-day window means perfect attendance. Two is
        enough to show the mechanism, and the mechanism is the point of report one."""
        from app.time_utils import local_today

        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        REPORT_RESPONSE.clear()
        REPORT_RESPONSE.update(
            {
                "what_you_did": "Two sessions to start with.",
                "what_changed": [],
                "pattern": {"text": "", "confidence": "low"},
                "friction": "",
                "recommendation": "Keep going for a few more days.",
                "closing": "The record has started.",
                "criteria_progress": [],
            }
        )

        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])
        today = local_today(me["timezone"])
        # Set two days ago: today is day three, so the first period has just closed.
        started = today - timedelta(days=2)

        async with SessionLocal() as db:
            from sqlalchemy import update as sa_update

            from app.models import Goal as GoalModel

            await db.execute(
                sa_update(GoalModel)
                .where(GoalModel.id == uuid.UUID(goal["id"]))
                .values(started_on=started)
            )
            for offset in range(2):
                entry = Entry(
                    user_id=user_id,
                    local_date=started + timedelta(days=offset),
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=entry.local_date,
                        category="Reading",
                        category_key="reading",
                        minutes=30,
                        minutes_explicit=True,
                        details=[],
                        quote="q",
                    )
                )
            await db.commit()

        # No period_end: the normal path picks the first three-day window.
        r = await client.post(
            "/api/reports", headers=auth, json={"goal_id": goal["id"], "force": True}
        )
        assert r.status_code == 202, r.text
        assert r.json()["period_start"] == started.isoformat()
        assert r.json()["period_end"] == (started + timedelta(days=1)).isoformat()

        report = await settle(client, f"/api/reports/{r.json()['id']}", auth)
        assert report["status"] == "done", report
        assert report["stats"]["entries"] == 2
        assert report["stats"]["is_first_report"] is True

    @pytest.mark.asyncio
    async def test_thin_week_refuses_rather_than_inventing(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Write code alone"])

        r = await client.post(
            "/api/reports",
            headers=auth,
            json={"goal_id": goal["id"], "period_end": "2026-08-20", "force": True},
        )
        report = await settle(client, f"/api/reports/{r.json()['id']}", auth)
        assert report["status"] == "failed"
        assert "check-in" in report["error"]

    async def _seed_minimum(self, client, auth, goal):
        REPORT_RESPONSE.clear()
        REPORT_RESPONSE.update(
            {
                "what_you_did": "Some sessions.",
                "what_changed": [],
                "pattern": {"text": "", "confidence": "low"},
                "friction": "",
                "recommendation": "Keep going.",
                "closing": "A start.",
                "criteria_progress": [],
            }
        )
        async with SessionLocal() as db:
            user_id = uuid.UUID(
                (await client.get("/api/auth/me", headers=auth)).json()["id"]
            )
            today = date(2026, 8, 20)
            for offset in range(4):
                entry = Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=offset),
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=entry.local_date,
                        category="Programming",
                        category_key="programming",
                        minutes=60,
                        minutes_explicit=True,
                        details=[],
                        quote="q",
                    )
                )
            await db.commit()


# --------------------------------------------------------------- auth and access


class TestAuth:
    @pytest.mark.asyncio
    async def test_wrong_password_is_rejected(self, client):
        await register(client)
        r = await client.post(
            "/api/auth/login", json={"email": "admin@example.com", "password": "nope"}
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_password_change_invalidates_existing_tokens(self, client):
        auth = await register(client)
        assert (await client.get("/api/auth/me", headers=auth)).status_code == 200

        await client.post(
            "/api/auth/change-password",
            headers=auth,
            json={"current_password": "supersecret1", "new_password": "anothersecret1"},
        )
        assert (await client.get("/api/auth/me", headers=auth)).status_code == 401

    @pytest.mark.asyncio
    async def test_one_user_cannot_read_another_users_entry(self, client):
        auth_a = await register(client, "a@example.com")
        await make_goal(client, auth_a, "Learn programming", ["Write code alone"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )
        created = await client.post(
            "/api/entries/text", headers=auth_a, json={"text": TRANSCRIPT}
        )
        entry_id = created.json()["id"]

        auth_b = await register(client, "b@example.com")
        r = await client.get(f"/api/entries/{entry_id}", headers=auth_b)
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_admin_routes_are_closed_to_ordinary_users(self, client):
        auth = await register(client, "someone@example.com")
        assert (await client.get("/api/admin/overview", headers=auth)).status_code == 403

    @pytest.mark.asyncio
    async def test_unknown_timezone_is_rejected(self, client):
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "tz@example.com",
                "password": "supersecret1",
                "timezone": "Mars/Olympus",
            },
        )
        assert r.status_code == 422


class TestBruteForce:
    """Guessing a password, or mailing a stranger, has to get slow fast."""

    @staticmethod
    async def login(client, email="admin@example.com", password="nope", ip="198.51.100.7", **headers):
        return await client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
            headers={"X-Real-IP": ip, **headers},
        )

    @pytest.mark.asyncio
    async def test_wrong_passwords_lock_the_address_even_for_the_right_one(self, client):
        await register(client)
        for _ in range(5):
            assert (await self.login(client)).status_code == 401

        r = await self.login(client, password="supersecret1")
        assert r.status_code == 429
        assert 1 <= int(r.headers["Retry-After"]) <= 15 * 60

        # From another address entirely, the account is still locked: that is the point.
        assert (await self.login(client, password="supersecret1", ip="203.0.113.9")).status_code == 429

    @pytest.mark.asyncio
    async def test_signing_in_clears_the_wrong_guesses(self, client):
        await register(client)
        for _ in range(4):
            assert (await self.login(client)).status_code == 401
        assert (await self.login(client, password="supersecret1")).status_code == 200
        for _ in range(4):
            assert (await self.login(client)).status_code == 401

    @pytest.mark.asyncio
    async def test_one_address_trying_many_accounts_is_stopped(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "login_limit_per_ip", "3/15m")
        for i in range(3):
            assert (await self.login(client, email=f"u{i}@example.com")).status_code == 401
        assert (await self.login(client, email="fresh@example.com")).status_code == 429
        assert (await self.login(client, email="fresh@example.com", ip="203.0.113.9")).status_code == 401

    @pytest.mark.asyncio
    async def test_parallel_guesses_cannot_slip_past_the_count(self, client):
        await register(client)
        results = await asyncio.gather(*(self.login(client) for _ in range(12)))
        codes = sorted(r.status_code for r in results)
        assert codes.count(401) == 5
        assert codes.count(429) == 7

    @pytest.mark.asyncio
    async def test_a_forwarded_for_header_written_by_the_caller_changes_nothing(
        self, client, monkeypatch
    ):
        from app.config import settings

        monkeypatch.setattr(settings, "login_limit_per_ip", "2/15m")
        for i in range(2):
            await self.login(client, email=f"u{i}@example.com", **{"X-Forwarded-For": f"10.0.0.{i}"})
        r = await self.login(client, email="u9@example.com", **{"X-Forwarded-For": "10.0.0.99"})
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_cloudflare_header_is_believed_only_from_cloudflare(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "login_limit_per_ip", "1/15m")
        cloudflare = "172.70.1.1"
        # Through Cloudflare: each visitor is counted as themselves.
        r1 = await self.login(client, email="a@example.com", ip=cloudflare, **{"CF-Connecting-IP": "192.0.2.1"})
        r2 = await self.login(client, email="b@example.com", ip=cloudflare, **{"CF-Connecting-IP": "192.0.2.2"})
        assert r1.status_code == r2.status_code == 401

        # Straight to the origin with a made-up header: counted as who really connected.
        r3 = await self.login(client, email="c@example.com", **{"CF-Connecting-IP": "192.0.2.3"})
        r4 = await self.login(client, email="d@example.com", **{"CF-Connecting-IP": "192.0.2.4"})
        assert (r3.status_code, r4.status_code) == (401, 429)

    @pytest.mark.asyncio
    async def test_one_ipv6_subscriber_cannot_rotate_through_their_block(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "login_limit_per_ip", "1/15m")
        assert (await self.login(client, email="a@example.com", ip="2001:db8:1:2::1")).status_code == 401
        assert (await self.login(client, email="b@example.com", ip="2001:db8:1:2::ffff")).status_code == 429
        assert (await self.login(client, email="c@example.com", ip="2001:db8:1:3::1")).status_code == 401

    @pytest.mark.asyncio
    async def test_registration_is_capped_per_address(self, client, monkeypatch):
        from app.config import settings

        monkeypatch.setattr(settings, "register_limit_per_ip", "2/1h")
        await register(client, "a@example.com")
        await register(client, "b@example.com")
        r = await client.post(
            "/api/auth/register",
            json={"email": "c@example.com", "password": "supersecret1", "timezone": "Asia/Almaty"},
        )
        assert r.status_code == 429

    @pytest.mark.asyncio
    async def test_resend_limit_does_not_reveal_who_is_registered(self, client):
        await register(client, "real@example.com")
        for email in ("real@example.com", "nobody@example.com"):
            first = await client.post("/api/auth/resend-verification", json={"email": email})
            second = await client.post("/api/auth/resend-verification", json={"email": email})
            assert (first.status_code, second.status_code) == (202, 429), email

    @pytest.mark.asyncio
    async def test_admin_sign_in_is_locked_after_three_wrong_passwords(self, client):
        await register(client)
        wrong = {"email": "admin@example.com", "password": "nope"}
        for _ in range(3):
            assert (await client.post("/admin/login", data=wrong)).status_code == 200
        r = await client.post(
            "/admin/login", data={"email": "admin@example.com", "password": "supersecret1"}
        )
        assert r.status_code == 429
        assert "Слишком много попыток" in r.text
        assert "Retry-After" in r.headers

    def test_a_malformed_limit_fails_at_startup(self):
        from pydantic import ValidationError

        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings(login_limit_per_ip="twenty a minute")
        assert Settings(resend_limit_per_email="1/1m, 5/1h").resend_limit_per_email


# --------------------------------------------------------------- goals


class TestGoals:
    @pytest.mark.asyncio
    async def test_active_goals_are_capped(self, client):
        auth = await register(client)
        for i in range(5):
            await make_goal(client, auth, f"Goal {i}", ["Something"])
        r = await client.post(
            "/api/goals",
            headers=auth,
            json={"title": "One too many", "criteria": [{"text": "xy"}]},
        )
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_replacing_criteria_deactivates_rather_than_deletes(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Learn programming", ["Old criterion"])
        r = await client.patch(
            f"/api/goals/{goal['id']}",
            headers=auth,
            json={"criteria": [{"text": "New criterion", "source": "user"}]},
        )
        assert r.status_code == 200
        # Old ids must survive, or past reports lose the labels they referenced.
        assert [c["text"] for c in r.json()["criteria"]] == ["New criterion"]

    @pytest.mark.asyncio
    async def test_the_why_recording_is_kept_and_private(self, client, monkeypatch):
        """Transcribing it and discarding the audio loses the part that carries:
        hearing yourself from the day you decided is not reading it."""
        from app.services import stt as stt_service
        from app.services.stt import STTResult

        async def fake(path, mime=None, locale=None):
            return STTResult("Чтобы через год сменить работу.", 12.0, "ru", 400, "mock")

        monkeypatch.setattr(stt_service, "transcribe", fake)

        auth = await register(client, "owner@example.com")
        goal = await make_goal(client, auth, "Improve English", ["Read"])

        r = await client.post(
            f"/api/goals/{goal['id']}/why-audio",
            headers=auth,
            files={"audio": ("why.webm", b"x" * 4096, "audio/webm")},
        )
        assert r.status_code == 200, r.text
        assert r.json()["why_source"] == "voice"
        assert r.json()["why_audio_seconds"] == 12.0
        assert "сменить работу" in r.json()["why_text"]

        assert (
            await client.get(f"/api/goals/{goal['id']}/why-audio", headers=auth)
        ).status_code == 200

        # Somebody else's motivation is not theirs to hear.
        other = await register(client, "stranger@example.com")
        assert (
            await client.get(f"/api/goals/{goal['id']}/why-audio", headers=other)
        ).status_code == 404

    @pytest.mark.asyncio
    async def test_misrouted_activity_can_be_reassigned(self, client):
        auth = await register(client)
        prog = await make_goal(client, auth, "Learn programming", ["Write code alone"])
        eng = await make_goal(client, auth, "Improve English", ["Understand videos"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": prog["id"],
                        "category": "English",
                        "minutes": 30,
                        "minutes_explicit": True,
                        "details": [],
                        "quote": "I also listened to English for thirty minutes",
                    }
                ],
                "wins": [],
                "friction": [],
                "mood": "neutral",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)
        activity_id = entry["activities"][0]["id"]

        fixed = await client.patch(
            f"/api/entries/activities/{activity_id}",
            headers=auth,
            json={"goal_id": eng["id"]},
        )
        assert fixed.status_code == 200
        assert fixed.json()["goal_id"] == eng["id"]


# --------------------------------------------------------------- localisation


class TestLocalisation:
    def test_russian_locale_adds_an_output_language_directive(self):
        assert "Russian" in prompts.report_system("ru")
        assert "Russian" in prompts.extraction_system("ru-RU")
        assert "Russian" in prompts.criteria_system("ru")

    def test_english_prompts_are_left_untouched(self):
        assert prompts.report_system("en") == prompts.REPORT_SYSTEM
        assert prompts.extraction_system(None) == prompts.EXTRACTION_SYSTEM

    def test_unsupported_locale_falls_back_to_english(self):
        assert prompts.language_of("de") == "English"
        assert prompts.language_of(None) == "English"

    def test_language_is_detected_rather_than_forced_by_default(self):
        """Forcing the wrong language yields fluent nonsense, which nobody notices.

        Detection degrades gracefully; a wrong pin does not. So detection is the default
        and STT_LANGUAGE is only an escape hatch.
        """
        from app.config import settings

        assert settings.stt_detect_language is True
        assert not settings.stt_language, "STT_LANGUAGE must be unset by default"

    @pytest.mark.asyncio
    async def test_locale_is_stored_on_the_profile(self, client):
        auth = await register(client, "ru@example.com", locale="ru-RU")
        me = (await client.get("/api/auth/me", headers=auth)).json()
        assert me["locale"] == "ru"


class TestConfig:
    def test_platform_database_urls_are_rewritten_for_the_async_driver(self):
        """Railway and friends inject postgresql://, which SQLAlchemy maps to psycopg -
        a sync driver that cannot run in an async engine. The resulting error names
        neither the platform nor the driver, so normalise the URL instead."""
        from app.config import Settings

        base = "u:p@host:5432/db"
        assert Settings(database_url=f"postgresql://{base}").database_url.startswith(
            "postgresql+asyncpg://"
        )
        assert Settings(database_url=f"postgres://{base}").database_url.startswith(
            "postgresql+asyncpg://"
        )
        # Already-correct URLs must survive untouched.
        explicit = f"postgresql+asyncpg://{base}"
        assert Settings(database_url=explicit).database_url == explicit


class TestReminders:
    """The two rules that keep a nudge from becoming spam."""

    @pytest.mark.asyncio
    async def test_nobody_is_reminded_on_a_day_they_checked_in(self, client, monkeypatch):
        from datetime import datetime as dt
        from datetime import timezone as dt_timezone

        from app.config import settings
        from app.models import PushSubscription
        from app.services import reminders

        monkeypatch.setattr(settings, "vapid_private_key", "x")
        sent: list = []

        async def fake_send(db, user_id, payload):
            sent.append(user_id)
            return 1

        monkeypatch.setattr(reminders.push, "send_to_user", fake_send)

        auth = await register(client)  # timezone America/Los_Angeles
        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])

        async with SessionLocal() as db:
            db.add(
                PushSubscription(
                    user_id=user_id, endpoint="https://push.example/1", p256dh="k", auth="a"
                )
            )
            await db.commit()

        # 20:00 in Los Angeles is 03:00 UTC the next day.
        evening = dt(2026, 8, 21, 3, 0, tzinfo=dt_timezone.utc)
        assert await reminders.run_once(evening) == 1
        assert len(sent) == 1

        # A second pass the same evening must stay silent.
        assert await reminders.run_once(evening) == 0
        assert len(sent) == 1

    @pytest.mark.asyncio
    async def test_a_check_in_today_suppresses_the_reminder(self, client, monkeypatch):
        from datetime import datetime as dt
        from datetime import timezone as dt_timezone

        from app.config import settings
        from app.models import PushSubscription
        from app.services import reminders
        from app.time_utils import local_today

        monkeypatch.setattr(settings, "vapid_private_key", "x")

        async def fake_send(db, user_id, payload):
            raise AssertionError("must not remind someone who already checked in")

        monkeypatch.setattr(reminders.push, "send_to_user", fake_send)

        auth = await register(client)
        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])
        evening = dt(2026, 8, 21, 3, 0, tzinfo=dt_timezone.utc)

        async with SessionLocal() as db:
            db.add(
                PushSubscription(
                    user_id=user_id, endpoint="https://push.example/2", p256dh="k", auth="a"
                )
            )
            db.add(
                Entry(
                    user_id=user_id,
                    local_date=local_today(me["timezone"], evening),
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
            )
            await db.commit()

        assert await reminders.run_once(evening) == 0

    @pytest.mark.asyncio
    async def test_the_hour_is_local_to_each_person(self, client, monkeypatch):
        """20:00 means 20:00 where they are. A shared UTC hour would nudge half the
        users in the middle of the night."""
        from datetime import datetime as dt
        from datetime import timezone as dt_timezone

        from app.config import settings
        from app.models import PushSubscription
        from app.services import reminders

        monkeypatch.setattr(settings, "vapid_private_key", "x")
        sent: list = []

        async def fake_send(db, user_id, payload):
            sent.append(user_id)
            return 1

        monkeypatch.setattr(reminders.push, "send_to_user", fake_send)

        auth = await register(client)
        me = (await client.get("/api/auth/me", headers=auth)).json()
        async with SessionLocal() as db:
            db.add(
                PushSubscription(
                    user_id=uuid.UUID(me["id"]),
                    endpoint="https://push.example/3",
                    p256dh="k",
                    auth="a",
                )
            )
            await db.commit()

        # 03:00 UTC is 20:00 in Los Angeles - due. 20:00 UTC is 13:00 there - not.
        assert await reminders.run_once(dt(2026, 8, 21, 20, 0, tzinfo=dt_timezone.utc)) == 0
        assert sent == []
        assert await reminders.run_once(dt(2026, 8, 21, 3, 0, tzinfo=dt_timezone.utc)) == 1

    @pytest.mark.asyncio
    async def test_subscribing_twice_from_one_browser_does_not_duplicate(self, client):
        from app.models import PushSubscription

        auth = await register(client)
        body = {
            "endpoint": "https://push.example/same",
            "keys": {"p256dh": "key", "auth": "auth"},
        }
        assert (await client.post("/api/push/subscribe", headers=auth, json=body)).status_code == 201
        assert (await client.post("/api/push/subscribe", headers=auth, json=body)).status_code == 201

        async with SessionLocal() as db:
            rows = (await db.execute(select(PushSubscription))).scalars().all()
        assert len(rows) == 1, "one browser must not receive two of every reminder"


class TestTasks:
    """Intentions, compared against what was actually said. Nothing here is ever
    marked done or failed - that judgement belongs to the person."""

    @pytest.mark.asyncio
    async def test_a_task_is_matched_to_what_the_entry_says(self, client, monkeypatch):
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        created = await client.post(
            "/api/tasks",
            headers=auth,
            json={"text": "Read a chapter without a translator", "goal_id": goal["id"], "days": 3},
        )
        assert created.status_code == 201, created.text
        task_id = created.json()["id"]
        assert created.json()["span_days"] == 3
        assert created.json()["days_touched"] == 0

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import tasks as task_service

        async def fake_match(system, user, schema):
            return LLMResult(
                data={
                    "matches": [
                        {
                            "task_id": task_id,
                            "quote": "I also listened to English for thirty minutes",
                        }
                    ]
                },
                model="mock",
                elapsed_ms=100,
            )

        monkeypatch.setattr(task_service, "complete_json", fake_match)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        await settle(client, f"/api/entries/{r.json()['id']}", auth)

        listed = (await client.get("/api/tasks", headers=auth)).json()
        assert listed[0]["days_touched"] == 1
        assert listed[0]["evidence"][0]["quote"].startswith("I also listened")
        # There is no completion flag to check, and that is the point.
        assert "completed" not in listed[0]

    @pytest.mark.asyncio
    async def test_a_match_without_a_traceable_quote_is_dropped(self, client, monkeypatch):
        """Telling someone they did a thing they never said is the one failure this
        feature must not have."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        created = await client.post(
            "/api/tasks", headers=auth, json={"text": "Read a chapter", "days": 1}
        )
        task_id = created.json()["id"]

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import tasks as task_service

        async def fake_match(system, user, schema):
            return LLMResult(
                data={
                    "matches": [
                        {"task_id": task_id, "quote": "I read the whole chapter tonight"}
                    ]
                },
                model="mock",
                elapsed_ms=100,
            )

        monkeypatch.setattr(task_service, "complete_json", fake_match)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        await settle(client, f"/api/entries/{r.json()['id']}", auth)

        listed = (await client.get("/api/tasks", headers=auth)).json()
        assert listed[0]["days_touched"] == 0

    @pytest.mark.asyncio
    async def test_active_tasks_are_capped(self, client):
        auth = await register(client)
        for i in range(5):
            r = await client.post(
                "/api/tasks", headers=auth, json={"text": f"Task number {i}", "days": 5}
            )
            assert r.status_code == 201, r.text

        r = await client.post("/api/tasks", headers=auth, json={"text": "One too many"})
        assert r.status_code == 409

    @pytest.mark.asyncio
    async def test_suggestions_only_when_nothing_is_on(self, client):
        """An intention already in play is reason enough to come back; a second prompt
        on top of it is noise."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        first = (await client.get("/api/tasks/suggestions", headers=auth)).json()
        assert first["should_ask"] is True

        await client.post("/api/tasks", headers=auth, json={"text": "Read a chapter", "days": 2})
        second = (await client.get("/api/tasks/suggestions", headers=auth)).json()
        assert second["should_ask"] is False

    @pytest.mark.asyncio
    async def test_suggestions_are_the_persons_own_words(self, client):
        """Nothing is invented. A model proposing plausible tasks is an AI coach
        prescribing a day it knows nothing about."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [],
                "wins": [],
                "friction": [],
                "intentions": [
                    {
                        "text": "Доделать авторизацию",
                        "quote": "I figured it out on my own without looking at a tutorial",
                    },
                    {
                        # never said - must not be offered back to them
                        "text": "Пробежать пять километров",
                        "quote": "завтра пробегу пять километров",
                    },
                ],
                "mood": "neutral",
            }
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)
        assert [i["text"] for i in entry["intentions"]] == ["Доделать авторизацию"]

        offered = (await client.get("/api/tasks/suggestions", headers=auth)).json()
        assert offered["should_ask"] is True
        assert offered["suggestions"] == ["Доделать авторизацию"]

    @pytest.mark.asyncio
    async def test_nothing_is_offered_when_nothing_was_said(self, client):
        """No stated intention means an empty field, not an invented idea."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        await settle(client, f"/api/entries/{r.json()['id']}", auth)

        offered = (await client.get("/api/tasks/suggestions", headers=auth)).json()
        assert offered["should_ask"] is True
        assert offered["suggestions"] == []

    @pytest.mark.asyncio
    async def test_declining_buys_a_few_days_of_quiet(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        assert (await client.get("/api/tasks/suggestions", headers=auth)).json()["should_ask"]
        assert (await client.post("/api/tasks/decline", headers=auth)).status_code == 204
        assert not (await client.get("/api/tasks/suggestions", headers=auth)).json()["should_ask"]

    @pytest.mark.asyncio
    async def test_closing_a_task_keeps_what_happened(self, client):
        """Closing is not failing: the record of the days it was touched survives."""
        auth = await register(client)
        created = await client.post(
            "/api/tasks", headers=auth, json={"text": "Read a chapter", "days": 3}
        )
        task_id = created.json()["id"]

        closed = await client.patch(
            f"/api/tasks/{task_id}", headers=auth, json={"close": True}
        )
        assert closed.status_code == 200
        assert closed.json()["status"] == "closed"
        assert closed.json()["span_days"] == 3

        assert (await client.get("/api/tasks", headers=auth)).json() == []
        kept = (await client.get("/api/tasks?include_closed=true", headers=auth)).json()
        assert len(kept) == 1


class TestDailySummary:
    """The Today screen's numbers. Two rules: nothing decreases, nothing reports
    absence."""

    async def _seed(self, client, auth, days: dict[int, list[dict]]):
        """days maps an offset-back-from-today to a list of metrics for that day."""
        from app.time_utils import local_today

        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])
        today = local_today(me["timezone"])
        goal = (await client.get("/api/goals", headers=auth)).json()[0]

        async with SessionLocal() as db:
            for offset, metrics in days.items():
                entry = Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=offset),
                    source="text",
                    raw_transcript="x" * 50,
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal["id"]),
                        local_date=entry.local_date,
                        category="Reading",
                        category_key="reading",
                        minutes=30,
                        minutes_explicit=True,
                        details=[],
                        metrics=metrics,
                        quote="q",
                    )
                )
            await db.commit()
        return today

    @pytest.mark.asyncio
    async def test_days_in_journey_counts_days_not_streaks(self, client):
        """A gap must cost nothing. Three days with a hole in the middle is still three."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(client, auth, {0: [], 1: [], 5: []})

        result = (await client.get("/api/entries/summary", headers=auth)).json()
        assert result["days_in_journey"] == 3
        assert result["checked_in_today"] is True

    @pytest.mark.asyncio
    async def test_horizon_covers_a_fortnight_without_marking_gaps(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(client, auth, {0: [], 3: []})

        horizon = (await client.get("/api/entries/summary", headers=auth)).json()["horizon"]
        assert len(horizon) == 14
        assert sum(1 for day in horizon if day["has_entry"]) == 2
        # Empty days carry no weight and no flag - nothing marks them as missed.
        empty = [day for day in horizon if not day["has_entry"]]
        assert all(day["weight"] == 0.0 for day in empty)

    @pytest.mark.asyncio
    async def test_accumulated_total_only_grows(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(
            client,
            auth,
            {
                2: [{"name": "новые слова", "value": 12, "unit": "слов", "quote": "q"}],
                1: [{"name": "новые слова", "value": 9, "unit": "слов", "quote": "q"}],
                0: [{"name": "новые слова", "value": 2, "unit": "слов", "quote": "q"}],
            },
        )

        result = (await client.get("/api/entries/summary", headers=auth)).json()
        # Today was the weakest day, and the number the person sees still went up.
        assert result["accumulated"]["total"] == 23
        assert result["accumulated"]["name"] == "новые слова"

    @pytest.mark.asyncio
    async def test_personal_record_appears_only_when_beaten(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(
            client,
            auth,
            {
                2: [{"name": "новые слова", "value": 8, "unit": "слов", "quote": "q"}],
                0: [{"name": "новые слова", "value": 14, "unit": "слов", "quote": "q"}],
            },
        )

        record = (await client.get("/api/entries/summary", headers=auth)).json()["personal_record"]
        assert record["value"] == 14
        assert record["previous_best"] == 8

    @pytest.mark.asyncio
    async def test_a_weaker_day_says_nothing_at_all(self, client):
        """Not "less than before" - nothing. Silence is the whole design here."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(
            client,
            auth,
            {
                2: [{"name": "новые слова", "value": 20, "unit": "слов", "quote": "q"}],
                0: [{"name": "новые слова", "value": 3, "unit": "слов", "quote": "q"}],
            },
        )

        result = (await client.get("/api/entries/summary", headers=auth)).json()
        assert result["personal_record"] is None
        # And the accumulated figure still rose.
        assert result["accumulated"]["total"] == 23

    @pytest.mark.asyncio
    async def test_first_ever_day_is_not_a_record(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._seed(
            client, auth, {0: [{"name": "слова", "value": 5, "unit": "слов", "quote": "q"}]}
        )

        result = (await client.get("/api/entries/summary", headers=auth)).json()
        assert result["personal_record"] is None, "nothing was beaten"

    @pytest.mark.asyncio
    async def test_a_ready_report_is_not_counted_down_to(self, client):
        """Once the first period closes, the report is ready. Counting down to the
        *next* one told someone their report was a week away while it sat there."""
        from sqlalchemy import update as sa_update

        from app.models import Goal as GoalModel
        from app.time_utils import local_today

        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read"])
        me = (await client.get("/api/auth/me", headers=auth)).json()
        today = local_today(me["timezone"])

        async def set_start(days_ago: int):
            async with SessionLocal() as db:
                await db.execute(
                    sa_update(GoalModel)
                    .where(GoalModel.id == uuid.UUID(goal["id"]))
                    .values(started_on=today - timedelta(days=days_ago))
                )
                await db.commit()

        # Day two: one to go.
        await set_start(1)
        result = (await client.get("/api/entries/summary", headers=auth)).json()
        assert result["days_until_report"] == 1

        # Day three: the first period has closed and nothing has been read yet.
        await set_start(2)
        result = (await client.get("/api/entries/summary", headers=auth)).json()
        assert result["days_until_report"] == 0, "the report is ready, not seven days off"
        assert result["has_completed_period"] is True

    @pytest.mark.asyncio
    async def test_summary_route_is_not_swallowed_by_the_entry_route(self, client):
        """/entries/summary must not be parsed as /entries/{uuid}."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])
        r = await client.get("/api/entries/summary", headers=auth)
        assert r.status_code == 200
        assert "days_in_journey" in r.json()


class TestReflection:
    """The answer after a check-in. Its whole value is that claims about the past are
    checked, so most of these tests are about what gets thrown away."""

    async def _with_history(self, client, auth):
        """Two earlier days with distinctive wording to quote from."""
        from app.time_utils import local_today

        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])
        today = local_today(me["timezone"])

        async with SessionLocal() as db:
            db.add(
                Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=5),
                    source="text",
                    raw_transcript="Я вообще не понимаю, куда мне двигаться дальше.",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
            )
            db.add(
                Entry(
                    user_id=user_id,
                    local_date=today - timedelta(days=1),
                    source="text",
                    raw_transcript="Сделал три дела и всё равно кажется, что мало.",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
            )
            await db.commit()
        return today

    @pytest.mark.asyncio
    async def test_a_verified_quote_from_the_past_survives(self, client, monkeypatch):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        today = await self._with_history(client, auth)

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import reflection

        async def fake(system, user, schema):
            return LLMResult(
                data={
                    "say_nothing": False,
                    "paragraphs": [
                        {
                            "text": "Пять дней назад ты не понимал, куда двигаться. Сегодня ты называешь конкретные дела.",
                            "reference_date": (today - timedelta(days=5)).isoformat(),
                            "reference_quote": "Я вообще не понимаю, куда мне двигаться дальше",
                        }
                    ],
                },
                model="mock",
                elapsed_ms=800,
            )

        monkeypatch.setattr(reflection, "complete_json", fake)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert len(entry["reflection"]) == 1
        assert entry["reflection"][0]["reference"]["quote"].startswith("Я вообще не понимаю")

    @pytest.mark.asyncio
    async def test_a_quote_the_person_never_said_is_dropped(self, client, monkeypatch):
        """Telling someone they said something they did not is the one failure this
        feature exists to avoid."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        today = await self._with_history(client, auth)

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import reflection

        async def fake(system, user, schema):
            return LLMResult(
                data={
                    "say_nothing": False,
                    "paragraphs": [
                        {
                            "text": "Ты говорил, что хочешь бросить.",
                            "reference_date": (today - timedelta(days=5)).isoformat(),
                            "reference_quote": "я хочу всё бросить и забыть про это",
                        }
                    ],
                },
                model="mock",
                elapsed_ms=800,
            )

        monkeypatch.setattr(reflection, "complete_json", fake)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["reflection"] == []

    @pytest.mark.asyncio
    async def test_a_date_the_person_never_wrote_on_is_dropped(self, client, monkeypatch):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._with_history(client, auth)

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import reflection

        async def fake(system, user, schema):
            return LLMResult(
                data={
                    "say_nothing": False,
                    "paragraphs": [
                        {
                            "text": "В прошлом месяце ты говорил иначе.",
                            "reference_date": "2020-01-01",
                            "reference_quote": "Я вообще не понимаю, куда мне двигаться дальше",
                        }
                    ],
                },
                model="mock",
                elapsed_ms=800,
            )

        monkeypatch.setattr(reflection, "complete_json", fake)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["reflection"] == []

    @pytest.mark.asyncio
    async def test_praise_is_thrown_away(self, client, monkeypatch):
        """A person praised for every day stops believing the praise, and then stops
        believing the rest of what the product tells them."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._with_history(client, auth)

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import reflection

        async def fake(system, user, schema):
            return LLMResult(
                data={
                    "say_nothing": False,
                    "paragraphs": [
                        {"text": "Молодец, так держать!", "reference_date": "", "reference_quote": ""},
                        {"text": "Great job, keep it up", "reference_date": "", "reference_quote": ""},
                        {"text": "Похоже, у тебя выгорание.", "reference_date": "", "reference_quote": ""},
                    ],
                },
                model="mock",
                elapsed_ms=800,
            )

        monkeypatch.setattr(reflection, "complete_json", fake)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["reflection"] == [], "flattery and diagnosis must not reach the person"

    @pytest.mark.asyncio
    async def test_saying_nothing_is_a_valid_answer(self, client, monkeypatch):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "mood": "neutral"}
        )

        from app.services import reflection

        async def fake(system, user, schema):
            return LLMResult(
                data={"say_nothing": True, "paragraphs": []}, model="mock", elapsed_ms=200
            )

        monkeypatch.setattr(reflection, "complete_json", fake)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["status"] == "done"
        assert entry["reflection"] == []

    @pytest.mark.asyncio
    async def test_a_failed_reflection_does_not_cost_the_check_in(self, client, monkeypatch):
        """It sits on top of the facts. If it breaks, the facts still land."""
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read without a dictionary"])

        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {
                "activities": [
                    {
                        "goal_id": goal["id"],
                        "category": "English",
                        "minutes": 30,
                        "minutes_explicit": True,
                        "details": [],
                        "metrics": [],
                        "quote": "I also listened to English for thirty minutes",
                    }
                ],
                "wins": [],
                "friction": [],
                "mood": "neutral",
            }
        )

        from app.services import reflection
        from app.services.llm import LLMError as _LLMError

        async def boom(system, user, schema):
            raise _LLMError("model is down")

        monkeypatch.setattr(reflection, "complete_json", boom)

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry = await settle(client, f"/api/entries/{r.json()['id']}", auth)

        assert entry["status"] == "done"
        assert len(entry["activities"]) == 1
        assert entry["reflection"] == []


class TestMonthlyDigest:
    """Computed, never written: the numbers come from SQL, the changes from weekly
    reports that already passed validation, and the quotes are simply the first and
    last thing said that month."""

    async def _month_of_entries(self, client, auth, goal_id: str):
        from app.models import Report as ReportModel

        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])

        async with SessionLocal() as db:
            for day, words, minutes, said in (
                (3, 5, 20, "Начал читать, пока тяжело и лезу в словарь"),
                (8, 10, 60, "Читал час, стало легче"),
                (14, 12, 90, "Полтора часа, почти не заглядывал в словарь"),
                (21, 8, 30, "Полчаса чтения"),
                (27, 9, 45, "Читаю без словаря, это уже привычно"),
            ):
                entry = Entry(
                    user_id=user_id,
                    local_date=date(2026, 6, day),
                    source="text",
                    raw_transcript=said,
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
                db.add(entry)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=entry.id,
                        user_id=user_id,
                        goal_id=uuid.UUID(goal_id),
                        local_date=entry.local_date,
                        category="Чтение",
                        category_key="чтение",
                        minutes=minutes,
                        minutes_explicit=True,
                        details=[],
                        metrics=[
                            {"name": "новые слова", "value": words, "unit": "слов", "quote": "q"}
                        ],
                        quote=said,
                    )
                )

            # A validated weekly report: its changes are what the digest reuses.
            db.add(
                ReportModel(
                    user_id=user_id,
                    goal_id=uuid.UUID(goal_id),
                    period_start=date(2026, 6, 8),
                    period_end=date(2026, 6, 14),
                    status=Status.done.value,
                    generated_by="ai",
                    stats={},
                    content={
                        "what_you_did": "Читал",
                        "what_changed": [
                            {"text": "Стал реже открывать словарь", "evidence": "почти не заглядывал"},
                            {"text": "Стал реже открывать словарь", "evidence": "дубль"},
                        ],
                        "pattern": {"text": "", "confidence": "low"},
                        "criteria_progress": [],
                        "criteria_labels": {},
                    },
                )
            )
            await db.commit()

    @pytest.mark.asyncio
    async def test_digest_counts_and_quotes_the_month(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._month_of_entries(client, auth, goal["id"])

        d = (
            await client.get("/api/reports/monthly?year=2026&month=6", headers=auth)
        ).json()

        assert d["days_logged"] == 5
        assert d["days_in_month"] == 30
        assert d["metrics"][0]["total"] == 44, "5+10+12+8+9 words"
        assert d["strongest_day"]["date"] == "2026-06-14"
        assert d["strongest_day"]["minutes"] == 90

        # Earliest and latest, chosen by date rather than by a model looking for a story.
        assert d["then"]["date"] == "2026-06-03"
        assert "лезу в словарь" in d["then"]["said"]
        assert d["now"]["date"] == "2026-06-27"
        assert "без словаря" in d["now"]["said"]

    @pytest.mark.asyncio
    async def test_changes_come_from_validated_reports_without_repeats(self, client):
        auth = await register(client)
        goal = await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        await self._month_of_entries(client, auth, goal["id"])

        d = (
            await client.get("/api/reports/monthly?year=2026&month=6", headers=auth)
        ).json()

        assert len(d["changes"]) == 1, "the duplicate must not appear twice"
        assert d["changes"][0]["text"] == "Стал реже открывать словарь"

    @pytest.mark.asyncio
    async def test_a_thin_month_says_so(self, client):
        """Two check-ins are not a retrospective, and dressing them up as one is how
        a person learns to distrust the rest."""
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])

        d = (
            await client.get("/api/reports/monthly?year=2026&month=6", headers=auth)
        ).json()
        assert d["thin"] is True
        assert d["days_logged"] == 0
        assert d["then"] is None

    @pytest.mark.asyncio
    async def test_monthly_route_is_not_read_as_a_report_id(self, client):
        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])
        r = await client.get("/api/reports/monthly", headers=auth)
        assert r.status_code == 200
        assert "days_logged" in r.json()


# --------------------------------------------------------------- timezones


class TestTimezones:
    def test_local_date_follows_the_user_not_the_server(self):
        from datetime import datetime, timezone as dt_timezone

        from app.time_utils import local_today

        # 06:40 UTC on Tuesday is 23:40 Monday in Los Angeles (UTC-7 in August).
        moment = datetime(2026, 8, 18, 6, 40, tzinfo=dt_timezone.utc)
        assert local_today("America/Los_Angeles", moment) == date(2026, 8, 17)
        assert local_today("Asia/Almaty", moment) == date(2026, 8, 18)

    def test_first_period_is_short_then_weekly_without_gaps(self):
        """The first report lands on day three - the plain reading of "day three" -
        and covers the two finished days before it. Reports never include today, or
        they would go stale the moment someone checked in again."""
        from app.time_utils import completed_period

        start = date(2026, 8, 1)

        # Days one and two: nothing has finished.
        for day in (0, 1):
            assert completed_period(start, start + timedelta(days=day)) is None

        first = (date(2026, 8, 1), date(2026, 8, 2))
        for day in (2, 5, 8):
            assert completed_period(start, start + timedelta(days=day)) == first

        second = (date(2026, 8, 3), date(2026, 8, 9))
        for day in (9, 12, 15):
            assert completed_period(start, start + timedelta(days=day)) == second

        third = (date(2026, 8, 10), date(2026, 8, 16))
        assert completed_period(start, start + timedelta(days=16)) == third

        # Periods must abut exactly: a gap would silently drop a day of someone's work.
        assert second[0] == first[1] + timedelta(days=1)
        assert third[0] == second[1] + timedelta(days=1)


# --------------------------------------------------------------- cost accounting


class TestCostAccounting:
    """Every check-in carries what it cost, summed over each provider call made for it."""

    USAGE = {
        "prompt_tokens": 1200,
        "completion_tokens": 300,
        "prompt_tokens_details": {"cached_tokens": 1000},
        "completion_tokens_details": {"reasoning_tokens": 100},
    }

    def test_prices_split_cached_and_fresh_input(self, monkeypatch):
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "llm_price_input_per_1m", 2.0)
        monkeypatch.setattr(settings, "llm_price_cached_input_per_1m", 0.5)
        monkeypatch.setattr(settings, "llm_price_output_per_1m", 8.0)
        # 200 fresh * 2 + 1000 cached * 0.5 + 300 out * 8, per million
        assert costs.llm_price(1200, 1000, 300) == pytest.approx(3300 / 1_000_000)

        # No cached price configured: cached tokens cost full input price.
        monkeypatch.setattr(settings, "llm_price_cached_input_per_1m", None)
        assert costs.llm_price(1200, 1000, 300) == pytest.approx(4800 / 1_000_000)

    def test_local_speech_to_text_is_free(self, monkeypatch):
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "stt_price_per_min", 0.0043)
        assert costs.stt_price("deepgram", 120.0) == pytest.approx(0.0086)
        assert costs.stt_price("local", 120.0) == 0.0
        assert costs.stt_price("deepgram", None) == 0.0

    def test_calls_outside_a_meter_are_not_lost_or_fatal(self):
        from app.services import costs

        costs.record_llm("m", self.USAGE)  # nothing open: logged only
        with costs.track() as usage:
            costs.record_llm("m", self.USAGE)
            costs.record_llm("m", None)  # a response without usage still counts as a call
            costs.record_stt("deepgram", 60.0)
        assert usage.llm_calls == 2
        assert usage.llm_input_tokens == 1200
        assert usage.llm_cached_tokens == 1000
        assert usage.llm_output_tokens == 300
        assert usage.stt_seconds == 60.0

    @pytest.mark.asyncio
    async def test_review_flow_adds_both_jobs_to_one_entry(self, client, monkeypatch):
        """Transcription and extraction run as separate jobs; the entry sums both."""
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "stt_price_per_min", 0.006)
        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "llm_price_cached_input_per_1m", None)
        monkeypatch.setattr(settings, "llm_price_output_per_1m", 4.0)

        async def paid_transcribe(path, mime=None, locale=None):
            costs.record_stt("deepgram", 30.0)
            return STTResult(TRANSCRIPT, 30.0, "en", 500, "deepgram")

        async def paid_complete_json(system, user, schema):
            costs.record_llm("mock", {"prompt_tokens": 1000, "completion_tokens": 250})
            return await fake_complete_json(system, user, schema)

        monkeypatch.setattr(extraction, "transcribe", paid_transcribe)
        monkeypatch.setattr(extraction, "complete_json", paid_complete_json)

        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )

        r = await client.post(
            "/api/entries/voice",
            headers=auth,
            files={"audio": ("c.webm", b"x" * 2048, "audio/webm")},
        )
        assert r.status_code == 202, r.text
        entry_id = r.json()["id"]
        assert (await settle(client, f"/api/entries/{entry_id}", auth))["status"] == "awaiting_review"

        r = await client.post(
            f"/api/entries/{entry_id}/confirm", headers=auth, json={"text": TRANSCRIPT}
        )
        assert r.status_code == 202, r.text
        assert (await settle(client, f"/api/entries/{entry_id}", auth))["status"] == "done"

        async with SessionLocal() as db:
            entry = await db.get(Entry, uuid.UUID(entry_id))
        assert entry.stt_cost_usd == pytest.approx(0.003)  # 30s at $0.006/min
        assert entry.llm_calls >= 1
        assert entry.llm_input_tokens == 1000 * entry.llm_calls
        assert entry.llm_output_tokens == 250 * entry.llm_calls
        assert entry.llm_cost_usd == pytest.approx(0.002 * entry.llm_calls)

    @pytest.mark.asyncio
    async def test_a_failed_attempt_is_still_charged(self, client, monkeypatch):
        from app.services import costs
        from app.services.llm import LLMError

        async def billed_then_broken(system, user, schema):
            costs.record_llm("mock", {"prompt_tokens": 500, "completion_tokens": 50})
            raise LLMError("model did not return JSON")

        monkeypatch.setattr(extraction, "complete_json", billed_then_broken)

        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])
        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        entry_id = r.json()["id"]
        assert (await settle(client, f"/api/entries/{entry_id}", auth))["status"] == "failed"

        async with SessionLocal() as db:
            entry = await db.get(Entry, uuid.UUID(entry_id))
        assert entry.llm_calls == 1
        assert entry.llm_input_tokens == 500


# --------------------------------------------------------------- provider retries


class TestProviderRetries:
    """Repeat what might pass a moment later; never repeat what is wrong with the request."""

    # The autouse fixture swaps llm.complete_json for a fake. The class body runs at
    # import, before any fixture, so this is the real one.
    real_complete_json = staticmethod(llm.complete_json)

    OK_BODY = {
        "model": "gpt-test",
        "choices": [{"message": {"content": '{"ok": true}'}}],
        "usage": {"prompt_tokens": 10, "completion_tokens": 2},
    }

    @pytest.fixture
    def waits(self, monkeypatch):
        from app.services import retry

        waited: list[float] = []

        async def no_wait(seconds):
            waited.append(seconds)

        monkeypatch.setattr(retry, "pause", no_wait)
        return waited

    def _openai(self, monkeypatch, responses):
        """Serve `responses` in order; each is an httpx.Response or an exception."""
        import httpx
        from app.config import settings

        calls: list[int] = []
        queue = list(responses)

        def handler(request):
            calls.append(1)
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(settings, "openai_api_key", "test-key")
        monkeypatch.setattr(settings, "llm_max_retries", 2)
        monkeypatch.setattr(llm, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        return calls

    async def _ask(self):
        return await self.real_complete_json("sys", "user", {"type": "object"})

    @pytest.mark.asyncio
    async def test_a_bad_request_is_not_repeated(self, monkeypatch, waits):
        import httpx

        calls = self._openai(monkeypatch, [httpx.Response(400, json={"error": "bad schema"})])
        with pytest.raises(llm.LLMError, match="400"):
            await self._ask()
        assert len(calls) == 1
        assert waits == []

    @pytest.mark.asyncio
    async def test_a_rate_limit_waits_as_long_as_the_server_asked(self, monkeypatch, waits):
        import httpx

        calls = self._openai(
            monkeypatch,
            [
                httpx.Response(429, headers={"retry-after": "2"}, json={"error": "slow down"}),
                httpx.Response(200, json=self.OK_BODY),
            ],
        )
        result = await self._ask()
        assert result.data == {"ok": True}
        assert len(calls) == 2
        assert waits == [2.0]

    @pytest.mark.asyncio
    async def test_an_empty_account_is_not_a_rate_limit(self, monkeypatch, waits):
        import httpx

        calls = self._openai(
            monkeypatch,
            [httpx.Response(429, json={"error": {"code": "insufficient_quota"}})],
        )
        with pytest.raises(llm.LLMError):
            await self._ask()
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_a_wait_longer_than_a_minute_is_not_worth_it(self, monkeypatch, waits):
        import httpx

        calls = self._openai(
            monkeypatch, [httpx.Response(503, headers={"retry-after": "600"})]
        )
        with pytest.raises(llm.LLMError):
            await self._ask()
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_server_errors_and_dropped_connections_are_repeated(self, monkeypatch, waits):
        import httpx

        calls = self._openai(
            monkeypatch,
            [
                httpx.Response(502),
                httpx.ConnectError("reset"),
                httpx.Response(200, json=self.OK_BODY),
            ],
        )
        assert (await self._ask()).data == {"ok": True}
        assert len(calls) == 3
        assert len(waits) == 2 and waits[1] > waits[0]  # backs off

    @pytest.mark.asyncio
    async def test_gives_up_after_the_configured_retries(self, monkeypatch, waits):
        import httpx

        calls = self._openai(monkeypatch, [httpx.Response(500)] * 3)
        with pytest.raises(llm.LLMError, match="500"):
            await self._ask()
        assert len(calls) == 3  # one call plus LLM_MAX_RETRIES=2

    @pytest.mark.asyncio
    async def test_one_client_is_reused(self):
        first = llm._http()
        assert llm._http() is first
        await llm.aclose()
        assert llm._http() is not first
        await llm.aclose()

    def test_retry_after_forms(self):
        from email.utils import format_datetime
        from datetime import datetime as dt, timezone as tz

        import httpx
        from app.services import retry

        assert retry.retry_after(httpx.Response(429, headers={"retry-after-ms": "1500"})) == 1.5
        assert retry.retry_after(httpx.Response(429, headers={"retry-after": "3"})) == 3.0
        later = format_datetime(dt.now(tz.utc) + timedelta(seconds=30), usegmt=True)
        assert 25 <= retry.retry_after(httpx.Response(429, headers={"retry-after": later})) <= 30
        assert retry.retry_after(httpx.Response(429)) is None

    def _deepgram(self, monkeypatch, tmp_path, responses):
        import httpx
        from app.config import settings
        from app.services import stt

        calls: list[int] = []
        queue = list(responses)

        def handler(request):
            calls.append(1)
            item = queue.pop(0)
            if isinstance(item, Exception):
                raise item
            return item

        monkeypatch.setattr(settings, "deepgram_api_key", "test-key")
        monkeypatch.setattr(settings, "stt_provider", "deepgram")
        monkeypatch.setattr(settings, "stt_max_retries", 2)
        monkeypatch.setattr(stt, "_client", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
        audio = tmp_path / "a.webm"
        audio.write_bytes(b"x" * 64)
        return calls, str(audio)

    DEEPGRAM_OK = {
        "results": {
            "channels": [
                {"alternatives": [{"transcript": "hello there"}], "detected_language": "en"}
            ]
        },
        "metadata": {"duration": 3.0},
    }

    @pytest.mark.asyncio
    async def test_speech_to_text_survives_a_hiccup(self, monkeypatch, tmp_path, waits):
        import httpx
        from app.services import stt

        calls, path = self._deepgram(
            monkeypatch,
            tmp_path,
            [httpx.ReadTimeout("slow"), httpx.Response(503), httpx.Response(200, json=self.DEEPGRAM_OK)],
        )
        result = await stt.transcribe(path, "audio/webm")
        assert result.text == "hello there"
        assert len(calls) == 3

    @pytest.mark.asyncio
    async def test_speech_to_text_does_not_resend_bad_audio(self, monkeypatch, tmp_path, waits):
        import httpx
        from app.services import stt

        calls, path = self._deepgram(
            monkeypatch, tmp_path, [httpx.Response(400, json={"err_msg": "corrupt"})]
        )
        with pytest.raises(stt.STTError, match="400"):
            await stt.transcribe(path, "audio/webm")
        assert len(calls) == 1
        assert waits == []


# --------------------------------------------------------------- health


class TestHealth:
    @pytest.mark.asyncio
    async def test_public_health_says_alive_and_nothing_else(self, client):
        r = await client.get("/health")
        assert r.status_code == 200
        assert r.json() == {"api": "ok", "database": "ok"}

    @pytest.mark.asyncio
    async def test_a_database_failure_does_not_leak_its_cause(self, client, monkeypatch):
        import app.main as main_module

        class Broken:
            def connect(self):
                raise ConnectionRefusedError("db host 10.0.0.5:5432")

        monkeypatch.setattr(main_module, "engine", Broken())
        r = await client.get("/health")
        assert r.json() == {"api": "ok", "database": "error"}

    @pytest.mark.asyncio
    async def test_admins_still_see_which_providers_are_configured(self, client):
        auth = await register(client)  # admin@example.com is in ADMIN_EMAILS
        body = (await client.get("/api/admin/overview", headers=auth)).json()
        assert body["stt_provider"]
        assert body["llm_model"]


# --------------------------------------------------------------- verification letter


class TestVerificationLetter:
    """The first thing a new person receives from us: formal, correct, and safe."""

    LINK = "https://app.example/verify?token=abc&x=1"

    def test_russian_letter_is_formal(self):
        from app.services.mail import _html

        body = _html(self.LINK, "ru", "Анна")
        assert "Здравствуйте, Анна!" in body
        assert "Благодарим вас" in body
        assert "С уважением" in body
        # No informal address anywhere - the reason this letter was rewritten.
        for informal in ("Ты ", " ты ", "Подтверди ", "не отвечай"):
            assert informal not in body

    def test_without_a_name_the_greeting_still_reads(self):
        from app.services.mail import _html

        assert "Здравствуйте!" in _html(self.LINK, "ru", None)
        assert "Hello!" in _html(self.LINK, "en", "   ")

    def test_a_name_cannot_inject_markup(self):
        from app.services.mail import _html

        body = _html(self.LINK, "en", '<a href="https://evil.example">Click</a>')
        assert "evil.example\">" not in body
        assert "&lt;a href=" in body

    def test_the_link_is_given_as_text_too(self):
        from app.services.mail import _html

        # For clients that strip buttons: the address itself is printed, escaped.
        # Button href, text-link href, and the visible text.
        assert _html(self.LINK, "en").count("token=abc&amp;x=1") == 3

    @pytest.mark.parametrize(
        "hours, expected",
        [(1, "1 часа"), (2, "2 часов"), (11, "11 часов"), (21, "21 часа"), (24, "24 часов"), (48, "48 часов")],
    )
    def test_hours_agree_with_the_number(self, hours, expected):
        from app.services.mail import _hours

        assert _hours(hours, "ru") == expected

    def test_unknown_locale_falls_back_to_english(self):
        from app.services.mail import _html

        assert "Hello!" in _html(self.LINK, "de")

    @pytest.mark.asyncio
    async def test_registration_passes_the_name_to_the_letter(self, client, monkeypatch):
        from app.config import settings
        from app.services import mail

        monkeypatch.setattr(settings, "resend_api_key", "test-key")
        seen: list[tuple] = []

        async def fake_send(to, link, locale="en", name=None):
            seen.append((to, locale, name))
            return True

        monkeypatch.setattr(mail, "send_verification", fake_send)
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "anna@example.com",
                "password": "supersecret1",
                "timezone": "Europe/Moscow",
                "locale": "ru",
                "display_name": "Анна",
            },
        )
        assert r.status_code == 201, r.text
        assert seen == [("anna@example.com", "ru", "Анна")]


class TestAccountDeletion:
    """Deleting locks the account at once and erases it only after the grace period.
    The two failures worth a test: an erasure that leaves something behind, and a
    deleted account that can still be reached."""

    LOGIN = {"email": "leaver@example.com", "password": "supersecret1"}

    @staticmethod
    def _capture_letters(monkeypatch) -> list[str]:
        from app.config import settings
        from app.services import mail

        monkeypatch.setattr(settings, "resend_api_key", "test-key")
        links: list[str] = []

        async def fake_send(to, link, erase_on, locale="en", name=None):
            links.append(link)
            return True

        monkeypatch.setattr(mail, "send_account_deleted", fake_send)
        return links

    @staticmethod
    async def _voice_entry(client, auth) -> str:
        await make_goal(client, auth, "Improve English", ["Read"])
        EXTRACTION_RESPONSE.clear()
        EXTRACTION_RESPONSE.update(
            {"activities": [], "wins": [], "friction": [], "intentions": [], "mood": "neutral"}
        )
        r = await client.post(
            "/api/entries/voice",
            headers=auth,
            files={"audio": ("c.webm", b"x" * 2048, "audio/webm")},
        )
        assert r.status_code == 202, r.text
        await settle(client, f"/api/entries/{r.json()['id']}", auth)
        return r.json()["id"]

    @pytest.mark.asyncio
    async def test_deleting_ends_every_session_and_the_letter_brings_it_back(
        self, client, monkeypatch
    ):
        auth = await register(client, "leaver@example.com")
        links = self._capture_letters(monkeypatch)

        r = await client.delete("/api/auth/me", headers=auth)
        assert r.status_code == 200, r.text
        assert r.json()["restore_days"] == 30
        assert r.json()["letter_sent"] is True
        assert len(links) == 1

        assert (await client.get("/api/auth/me", headers=auth)).status_code == 401
        refused = await client.post("/api/auth/login", json=self.LOGIN)
        assert refused.status_code == 410, "must be told apart from an unconfirmed address"

        token = links[0].split("token=")[1]
        restored = await client.post("/api/auth/restore", json={"token": token})
        assert restored.status_code == 200
        # Opening the link twice is not an error.
        again = await client.post("/api/auth/restore", json={"token": token})
        assert again.status_code == 200

        assert (await client.post("/api/auth/login", json=self.LOGIN)).status_code == 200

    @pytest.mark.asyncio
    async def test_signing_in_to_a_deleted_account_resends_the_letter_but_not_every_time(
        self, client, monkeypatch
    ):
        from app.models import User

        auth = await register(client, "leaver@example.com")
        links = self._capture_letters(monkeypatch)
        await client.delete("/api/auth/me", headers=auth)

        await client.post("/api/auth/login", json=self.LOGIN)
        assert len(links) == 1, "a second letter within the minute is not sent"

        async with SessionLocal() as db:
            user = (await db.execute(select(User))).scalar_one()
            user.restore_sent_at = user.restore_sent_at - timedelta(minutes=5)
            await db.commit()

        await client.post("/api/auth/login", json=self.LOGIN)
        assert len(links) == 2

        # A wrong password learns nothing about the account and triggers nothing.
        wrong = await client.post(
            "/api/auth/login", json={**self.LOGIN, "password": "not-the-password"}
        )
        assert wrong.status_code == 401
        assert len(links) == 2

    @pytest.mark.asyncio
    async def test_a_link_from_an_earlier_deletion_does_not_undo_a_later_one(
        self, client, monkeypatch
    ):
        auth = await register(client, "leaver@example.com")
        links = self._capture_letters(monkeypatch)

        await client.delete("/api/auth/me", headers=auth)
        first = links[-1].split("token=")[1]
        await client.post("/api/auth/restore", json={"token": first})

        tokens = (await client.post("/api/auth/login", json=self.LOGIN)).json()
        # The link carries the deletion time to the second.
        await asyncio.sleep(1.1)
        await client.delete(
            "/api/auth/me", headers={"Authorization": f"Bearer {tokens['access_token']}"}
        )

        stale = await client.post("/api/auth/restore", json={"token": first})
        assert stale.status_code == 400
        assert (await client.post("/api/auth/login", json=self.LOGIN)).status_code == 410

    @pytest.mark.asyncio
    async def test_after_the_grace_period_everything_is_erased_and_nothing_else(
        self, client, monkeypatch, tmp_path
    ):
        from pathlib import Path

        from app.config import settings
        from app.models import Event, Goal, PushSubscription, Task, User
        from app.services import accounts

        monkeypatch.setattr(settings, "audio_dir", str(tmp_path))

        auth = await register(client, "leaver@example.com")
        entry_id = await self._voice_entry(client, auth)
        r = await client.post("/api/tasks", headers=auth, json={"text": "Read daily", "days": 3})
        assert r.status_code in (200, 201), r.text
        async with SessionLocal() as db:
            leaver = (await db.execute(select(User))).scalar_one()
            db.add(
                PushSubscription(
                    user_id=leaver.id, endpoint="https://p/1", p256dh="k", auth="a"
                )
            )
            await db.commit()
            leaver_id = leaver.id
            recording = Path((await db.get(Entry, uuid.UUID(entry_id))).audio_path)
        assert recording.exists()

        stayer = await register(client, "stayer@example.com")
        await self._voice_entry(client, stayer)

        links = self._capture_letters(monkeypatch)
        await client.delete("/api/auth/me", headers=auth)

        # Inside the grace period nothing is touched.
        assert await accounts.purge_expired() == 0
        assert recording.exists()

        async with SessionLocal() as db:
            user = await db.get(User, leaver_id)
            user.deleted_at = user.deleted_at - timedelta(days=31)
            await db.commit()

        assert await accounts.purge_expired() == 1

        assert not recording.exists()
        assert not (tmp_path / str(leaver_id)).exists()
        async with SessionLocal() as db:
            for model in (Entry, Activity, Report, Goal, Task, PushSubscription, Event):
                left = (
                    await db.execute(select(model).where(model.user_id == leaver_id))
                ).scalars().all()
                assert left == [], f"{model.__tablename__} kept rows of an erased account"
            assert await db.get(User, leaver_id) is None
            others = (await db.execute(select(Entry))).scalars().all()
            assert len(others) == 1 and Path(others[0].audio_path).exists()

        # The old letter leads nowhere, and the address is free again.
        token = links[0].split("token=")[1]
        assert (await client.post("/api/auth/restore", json={"token": token})).status_code == 400
        monkeypatch.setattr(settings, "resend_api_key", None)
        await register(client, "leaver@example.com")

    @pytest.mark.asyncio
    async def test_a_deleted_account_gets_no_reminders(self, client, monkeypatch):
        from datetime import datetime, timezone

        from app.models import PushSubscription, User
        from app.services import reminders

        now = datetime.now(timezone.utc)
        auth = await register(client, "leaver@example.com")
        self._capture_letters(monkeypatch)
        async with SessionLocal() as db:
            user = (await db.execute(select(User))).scalar_one()
            user.reminder_hour = reminders._local_hour(user.timezone, now)
            db.add(
                PushSubscription(user_id=user.id, endpoint="https://p/1", p256dh="k", auth="a")
            )
            await db.commit()
            assert len(await reminders._due_users(db, now)) == 1

        await client.delete("/api/auth/me", headers=auth)

        async with SessionLocal() as db:
            assert await reminders._due_users(db, now) == []
