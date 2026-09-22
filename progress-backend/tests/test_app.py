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
from app.services import extraction, llm, prompts, verify
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

        async def fake_send(to, link, locale="en"):
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

        async def fake_send(to, link, locale="en"):
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

        async def refuses(to, link, locale="en"):
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
        async def works(to, link, locale="en"):
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


class TestReminders:
    """The rules that separate a reminder from spam."""

    @pytest.mark.asyncio
    async def test_nobody_is_nudged_on_a_day_they_already_checked_in(self, client, monkeypatch):
        from app.models import PushSubscription
        from app.services import scheduler
        from app.time_utils import local_today

        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])
        today = local_today(me["timezone"])

        sent_to: list = []

        async def fake_send(db, uid, payload):
            sent_to.append(uid)
            return 1

        monkeypatch.setattr(scheduler, "send_to_user", fake_send)

        async with SessionLocal() as db:
            db.add(
                PushSubscription(
                    user_id=user_id, endpoint="https://push.example/abc", p256dh="k", auth="a"
                )
            )
            # Set the reminder hour to whatever it is for them right now, so the pass
            # considers them due.
            from datetime import datetime as dt
            from datetime import timezone as tzmod

            from sqlalchemy import update as sa_update

            from app.models import User as UserModel
            from app.time_utils import tz_of

            hour_now = dt.now(tzmod.utc).astimezone(tz_of(me["timezone"])).hour
            await db.execute(
                sa_update(UserModel).where(UserModel.id == user_id).values(reminder_hour=hour_now)
            )
            db.add(
                Entry(
                    user_id=user_id,
                    local_date=today,
                    source="text",
                    status=Status.done.value,
                    wins=[],
                    friction=[],
                )
            )
            await db.commit()

        assert await scheduler.run_due_reminders() == 0
        assert sent_to == [], "already checked in today; a nudge would be noise"

    @pytest.mark.asyncio
    async def test_a_user_with_no_check_in_is_nudged_once(self, client, monkeypatch):
        from datetime import datetime as dt
        from datetime import timezone as tzmod

        from sqlalchemy import update as sa_update

        from app.models import PushSubscription
        from app.models import User as UserModel
        from app.services import scheduler
        from app.time_utils import tz_of

        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read without a dictionary"])
        me = (await client.get("/api/auth/me", headers=auth)).json()
        user_id = uuid.UUID(me["id"])

        calls: list = []

        async def fake_send(db, uid, payload):
            calls.append(payload)
            return 1

        monkeypatch.setattr(scheduler, "send_to_user", fake_send)

        async with SessionLocal() as db:
            db.add(
                PushSubscription(
                    user_id=user_id, endpoint="https://push.example/xyz", p256dh="k", auth="a"
                )
            )
            hour_now = dt.now(tzmod.utc).astimezone(tz_of(me["timezone"])).hour
            await db.execute(
                sa_update(UserModel).where(UserModel.id == user_id).values(reminder_hour=hour_now)
            )
            await db.commit()

        assert await scheduler.run_due_reminders() == 1
        assert len(calls) == 1
        assert calls[0]["url"] == "/today"

        # A second pass in the same hour must not fire again.
        assert await scheduler.run_due_reminders() == 0
        assert len(calls) == 1

    @pytest.mark.asyncio
    async def test_users_without_a_device_are_skipped(self, client, monkeypatch):
        from app.services import scheduler

        auth = await register(client)
        await make_goal(client, auth, "Improve English", ["Read"])

        async def fake_send(db, uid, payload):
            raise AssertionError("unreachable user must not be pushed to")

        monkeypatch.setattr(scheduler, "send_to_user", fake_send)
        assert await scheduler.run_due_reminders() == 0


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
