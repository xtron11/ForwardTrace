"""Test suite.

Runs on SQLite with both AI providers mocked, so it needs no keys and no database
server:  pytest -q

What is tested is deliberately narrow: the invariants that, if they broke, would make
the product quietly lie rather than visibly fail. A misrouted activity or an invented
statistic does not raise an exception - it produces a confident, wrong report. Those
are the failures worth a test.
"""

import asyncio
import os
import uuid
from datetime import date, timedelta

import pytest
import pytest_asyncio

os.environ.setdefault("JWT_SECRET", "test-secret-not-used-anywhere-real")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./test_suite.db")
os.environ.setdefault("ADMIN_EMAILS", "admin@example.com")
# The suite creates tables directly from the models; no migration run is involved.
os.environ.setdefault("AUTO_CREATE_TABLES", "true")

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import Base, SessionLocal, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Activity, Entry, Report, Status  # noqa: E402
from app.services import extraction, llm, prompts, verify  # noqa: E402
from app.services import reports as report_svc  # noqa: E402
from app.services.aggregate import compute_stats  # noqa: E402
from app.services.llm import LLMResult  # noqa: E402
from app.services.stt import STTResult  # noqa: E402

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


# --------------------------------------------------------------- timezones


class TestTimezones:
    def test_local_date_follows_the_user_not_the_server(self):
        from datetime import datetime, timezone as dt_timezone

        from app.time_utils import local_today

        # 06:40 UTC on Tuesday is 23:40 Monday in Los Angeles (UTC-7 in August).
        moment = datetime(2026, 8, 18, 6, 40, tzinfo=dt_timezone.utc)
        assert local_today("America/Los_Angeles", moment) == date(2026, 8, 17)
        assert local_today("Asia/Almaty", moment) == date(2026, 8, 18)

    def test_completed_period_excludes_the_day_in_progress(self):
        from app.time_utils import completed_period

        started = date(2026, 8, 13)
        assert completed_period(started, date(2026, 8, 20)) == (date(2026, 8, 13), date(2026, 8, 19))
        # Fewer than seven days elapsed: nothing to report on yet.
        assert completed_period(started, date(2026, 8, 17)) is None
