"""End-to-end smoke test. STT and LLM are mocked; everything else is real.

Run from progress-backend:

    python scripts/smoke_test.py
"""

import asyncio
import os
import sys
import uuid
from datetime import timedelta
from pathlib import Path

os.environ.setdefault("JWT_SECRET", "test-secret")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./smoke.db")
os.environ.setdefault("ADMIN_EMAILS", "admin@example.com")
os.environ.setdefault("AUDIO_DIR", "./data/audio")
os.environ.setdefault("AUTO_CREATE_TABLES", "true")

Path("smoke.db").unlink(missing_ok=True)

# Python puts scripts/ on the path, not the backend root, so `import app` needs the
# root added by hand.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from httpx import ASGITransport, AsyncClient  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402
from app.services import extraction, llm, reports as report_svc  # noqa: E402
from app.services.llm import LLMResult  # noqa: E402
from app.services.stt import STTResult  # noqa: E402

TRANSCRIPT = (
    "Today I coded for about two hours. I finished the API and I was stuck on "
    "authentication for a while, but I figured it out on my own without looking at a "
    "tutorial. I also listened to English for thirty minutes. I lost focus a couple of times."
)

GOAL_IDS: dict[str, str] = {}


async def fake_transcribe(path, mime=None):
    return STTResult(TRANSCRIPT, 58.0, "en", 640, "mock")


async def fake_complete_json(system, user, schema):
    if "extractor" in system:
        return LLMResult(
            data={
                "activities": [
                    {
                        "goal_id": GOAL_IDS.get("prog", ""),
                        "category": "Programming",
                        "minutes": 120,
                        "minutes_explicit": True,
                        "details": ["finished the API", "solved authentication alone"],
                        "quote": "I coded for about two hours",
                    },
                    {
                        "goal_id": GOAL_IDS.get("eng", ""),
                        "category": "English",
                        "minutes": 30,
                        "minutes_explicit": True,
                        "details": ["listening"],
                        "quote": "listened to English for thirty minutes",
                    },
                    {
                        # HALLUCINATION: nothing in the transcript says this.
                        "goal_id": GOAL_IDS.get("prog", ""),
                        "category": "Gym",
                        "minutes": 45,
                        "minutes_explicit": True,
                        "details": ["squats"],
                        "quote": "I went to the gym and did squats for 45 minutes",
                    },
                ],
                "wins": [
                    {
                        "goal_id": GOAL_IDS.get("prog", ""),
                        "text": "Solved an auth problem without a tutorial",
                        "quote": "figured it out on my own without looking at a tutorial",
                    }
                ],
                "friction": [
                    {
                        # invented goal id -> must land unrouted, not misfiled
                        "goal_id": "11111111-1111-1111-1111-111111111111",
                        "text": "Lost focus repeatedly",
                        "quote": "I lost focus a couple of times",
                    }
                ],
                "mood": "positive",
            },
            model="mock",
            elapsed_ms=900,
        )

    return LLMResult(
        data={
            "what_you_did": "Four sessions of programming across the week, plus regular listening practice.",
            "what_changed": [
                {
                    "text": "You solved an authentication problem without a tutorial.",
                    "evidence": "Reported figuring out auth independently.",
                }
            ],
            "pattern": {"text": "You go furthest on project work.", "confidence": "high"},
            "friction": "Focus dropped on several sessions.",
            "recommendation": "Start the next session by naming one thing you will build.",
            "closing": "A week ago you wanted to be less dependent on tutorials. This week you were.",
            "criteria_progress": [
                {"criterion_id": CRITERION_IDS[0], "status": "clear_evidence", "evidence": "Built the API alone."},
                # invented id -> must be discarded
                {"criterion_id": "00000000-0000-0000-0000-000000000000", "status": "clear_evidence", "evidence": "x"},
                # claims evidence but supplies none -> must be downgraded
                {"criterion_id": CRITERION_IDS[1], "status": "clear_evidence", "evidence": ""},
            ],
        },
        model="mock",
        elapsed_ms=3200,
    )


CRITERION_IDS: list[str] = []
CRITERION_GOAL_ID: list[str] = []


async def main() -> int:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    extraction.transcribe = fake_transcribe
    extraction.complete_json = fake_complete_json
    llm.complete_json = fake_complete_json
    report_svc.complete_json = fake_complete_json

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post(
            "/api/auth/register",
            json={
                "email": "admin@example.com",
                "password": "supersecret1",
                "display_name": "Tester",
                "timezone": "America/Los_Angeles",
            },
        )
        assert r.status_code == 201, r.text
        auth = {"Authorization": f"Bearer {r.json()['access_token']}"}
        print("register                 ok")

        r = await client.post("/api/auth/login", json={"email": "admin@example.com", "password": "wrong"})
        assert r.status_code == 401
        print("wrong password rejected  ok")

        r = await client.post(
            "/api/goals",
            headers=auth,
            json={
                "title": "Learn programming",
                "why_text": "So I can get a job in a year and stop quitting.",
                "criteria": [
                    {"text": "Build projects independently"},
                    {"text": "Understand code without tutorials"},
                ],
            },
        )
        assert r.status_code == 201, r.text
        goal = r.json()
        CRITERION_IDS.clear()
        CRITERION_IDS.extend(c["id"] for c in goal["criteria"])
        CRITERION_GOAL_ID.append(goal["id"])
        print("goal + criteria created   ok")

        r = await client.post(
            "/api/goals",
            headers=auth,
            json={
                "title": "Improve English",
                "why_text": "I want to speak without translating in my head.",
                "criteria": [{"text": "Understand videos without subtitles"}],
            },
        )
        assert r.status_code == 201, r.text
        GOAL_IDS["eng"] = r.json()["id"]
        GOAL_IDS["prog"] = goal["id"]
        print("second goal created        ok")

        r = await client.post("/api/entries/text", headers=auth, json={"text": TRANSCRIPT})
        assert r.status_code == 202, r.text
        entry_id = r.json()["id"]
        print("check-in accepted (202)   ok")

        for _ in range(50):
            r = await client.get(f"/api/entries/{entry_id}", headers=auth)
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)

        entry = r.json()
        assert entry["status"] == "done", entry
        cats = sorted(a["category"] for a in entry["activities"])
        assert cats == ["English", "Programming"], cats
        assert entry["dropped_facts"] == 1, entry["dropped_facts"]
        print(f"extraction               ok  -> {cats}")
        print("hallucinated 'Gym' fact rejected by quote check  ok")

        routed = {a["category"]: a["goal_id"] for a in entry["activities"]}
        assert routed["Programming"] == GOAL_IDS["prog"], routed
        assert routed["English"] == GOAL_IDS["eng"], routed
        print("one recording split across two goals             ok")

        assert entry["friction"][0]["goal_id"] is None, entry["friction"]
        print("invented goal id left unrouted, not misfiled     ok")

        # correcting a misroute
        eng_activity = next(a for a in entry["activities"] if a["category"] == "English")
        r = await client.patch(
            f"/api/entries/activities/{eng_activity['id']}",
            headers=auth,
            json={"goal_id": GOAL_IDS["prog"]},
        )
        assert r.status_code == 200 and r.json()["goal_id"] == GOAL_IDS["prog"]
        await client.patch(
            f"/api/entries/activities/{eng_activity['id']}",
            headers=auth,
            json={"goal_id": GOAL_IDS["eng"]},
        )
        print("misrouted activity can be reassigned             ok")

        # backfill more days so a report is possible
        from sqlalchemy import select
        from app.db import SessionLocal
        from app.models import Activity, Entry

        async with SessionLocal() as db:
            base = (await db.execute(select(Entry))).scalars().first()
            for offset in range(1, 4):
                clone = Entry(
                    user_id=base.user_id,
                    goal_id=None,  # unpinned, like a real multi-goal check-in
                    local_date=base.local_date - timedelta(days=offset),
                    source="text",
                    raw_transcript=TRANSCRIPT,
                    status="done",
                    mood="positive",
                    wins=base.wins,
                    friction=base.friction,
                )
                db.add(clone)
                await db.flush()
                db.add(
                    Activity(
                        entry_id=clone.id,
                        user_id=base.user_id,
                        goal_id=uuid.UUID(CRITERION_GOAL_ID[0]),
                        local_date=clone.local_date,
                        category="Programming",
                        category_key="programming",
                        minutes=120,
                        minutes_explicit=True,
                        details=["worked on the API"],
                        quote="I coded for about two hours",
                    )
                )
            await db.commit()

        r = await client.post("/api/reports", headers=auth, json={"period_end": entry["local_date"]})
        assert r.status_code == 202, r.text
        report_id = r.json()["id"]

        for _ in range(50):
            r = await client.get(f"/api/reports/{report_id}", headers=auth)
            if r.json()["status"] in ("done", "failed"):
                break
            await asyncio.sleep(0.05)

        report = r.json()
        assert report["status"] == "done", report
        stats = report["stats"]
        # 4 x 120 Programming. The 30 minutes of English belong to the other goal now
        # and must not leak into this report.
        assert stats["total_minutes"] == 480, stats["total_minutes"]
        assert [c["category"] for c in stats["categories"]] == ["Programming"], stats["categories"]
        print("English time excluded from the Programming report ok")
        assert stats["days_logged"] == 4, stats["days_logged"]
        assert stats["longest_streak"] == 4, stats["longest_streak"]
        print(f"report generated         ok  -> {stats['total_human']} over {stats['days_logged']} days")

        progress = report["content"]["criteria_progress"]
        assert len(progress) == 2, progress
        assert progress[0]["status"] == "clear_evidence"
        assert progress[1]["status"] == "no_evidence", progress[1]
        print("invented criterion id discarded                  ok")
        print("evidence-free claim downgraded to no_evidence    ok")

        r2 = await client.post("/api/reports", headers=auth, json={"period_end": entry["local_date"]})
        assert r2.json()["id"] == report_id, "report should be cached, not regenerated"
        assert r2.json()["content"] == report["content"]
        print("report cached, not regenerated                   ok")

        r = await client.post(
            f"/api/reports/{report_id}/feedback", headers=auth, json={"rating": 4, "text": "Useful."}
        )
        assert r.status_code == 200 and r.json()["feedback_rating"] == 4
        print("feedback recorded        ok")

        r = await client.get("/api/admin/overview", headers=auth)
        assert r.status_code == 200, r.text
        print(f"admin overview           ok  -> {r.json()['facts_rejected_by_verifier']} facts rejected total")

        r = await client.get("/health")
        assert r.json()["database"] == "ok"
        print("health                   ok")

    print("\nALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
