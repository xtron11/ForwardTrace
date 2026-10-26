"""Stage 10: nothing of v1 is left. No module, endpoint, table, column or setting of the
weekly reports, criteria, tasks, transcript review, old check-ins or per-day quotas, and
nothing that still imports them. The migration that drops the tables (0015_drop_v1) is
tested on Postgres in test_v2_foundation.py.
"""

import importlib.util
import re
from pathlib import Path

import pytest

from conftest import register

pytestmark = pytest.mark.asyncio

BACKEND = Path(__file__).resolve().parent.parent

REMOVED_MODULES = (
    "app.routers.entries",
    "app.routers.reports",
    "app.routers.tasks",
    "app.routers.goals",
    "app.services.reports",
    "app.services.aggregate",
    "app.services.summary",
    "app.services.monthly",
    "app.services.tasks",
    "app.services.extraction",
    "app.services.reflection",
    "app.services.reminders",
)
REMOVED_MODELS = ("Entry", "Activity", "Report", "Criterion", "Task", "TaskMention", "Status")
REMOVED_TABLES = ("entries", "activities", "reports", "criteria", "tasks", "task_mentions")
REMOVED_SETTINGS = (
    "max_voice_entries_per_day",
    "max_text_entries_per_day",
    "max_onboarding_transcribes_per_day",
    "report_period_days",
    "first_report_after_days",
    "min_entries_for_report",
    "min_entries_first_report",
    "max_active_goals",
    "max_active_tasks",
    "task_suggestion_cooldown_days",
    "default_reminder_hour",
    "keep_audio",
)
REMOVED_PREFIXES = ("/api/entries", "/api/reports", "/api/tasks", "/api/goals")


def _sources():
    for folder in ("app", "scripts", "alembic", "tests"):
        for path in (BACKEND / folder).rglob("*.py"):
            if "versions" in path.parts or path.name == Path(__file__).name:
                continue  # migrations describe history; this file names what is gone
            yield path, path.read_text(encoding="utf-8")


async def test_removed_modules_are_gone_and_nothing_imports_them():
    for name in REMOVED_MODULES:
        assert importlib.util.find_spec(name) is None, f"{name} still exists"
    short = [name.rsplit(".", 1)[1] for name in REMOVED_MODULES]
    for path, source in _sources():
        for line in source.splitlines():
            if not re.match(r"\s*(from|import)\s", line):
                continue
            for module in REMOVED_MODULES:
                assert module not in line, f"{path.name}: {line.strip()}"
            if re.search(r"from\s+\.+(services|routers)\s+import", line) or re.search(
                r"from\s+app\.(services|routers)\s+import", line
            ):
                imported = {n.strip().split(" ")[0] for n in line.split("import", 1)[1].split(",")}
                assert not imported & set(short), f"{path.name}: {line.strip()}"


async def test_v1_models_tables_and_column_are_gone():
    from app import models
    from app.db import Base

    for name in REMOVED_MODELS:
        assert not hasattr(models, name), name
    for table in REMOVED_TABLES:
        assert table not in Base.metadata.tables, table
    assert "tasks_declined_on" not in Base.metadata.tables["users"].columns
    for path, source in _sources():
        for name in REMOVED_MODELS:
            assert not re.search(rf"\bmodels import\b[^\n]*\b{name}\b", source), (path.name, name)


async def test_v1_settings_are_gone_from_config_and_env_example():
    from app.config import Settings

    env_example = (BACKEND / ".env.example").read_text(encoding="utf-8")
    for name in REMOVED_SETTINGS:
        assert name not in Settings.model_fields, name
        assert f"\n{name.upper()}=" not in env_example, name


async def test_v1_endpoints_answer_404(client):
    from app.main import app

    paths = {getattr(route, "path", "") for route in app.routes}
    for prefix in REMOVED_PREFIXES:
        assert not any(p == prefix or p.startswith(prefix + "/") for p in paths), prefix

    auth = await register(client)
    for method, path in (
        ("post", "/api/entries/text"),
        ("get", "/api/entries"),
        ("post", "/api/goals/suggest-criteria"),
        ("get", "/api/goals"),
        ("get", "/api/reports/latest"),
        ("get", "/api/tasks"),
    ):
        r = await getattr(client, method)(path, headers=auth)
        assert r.status_code in (404, 405), (path, r.status_code)


async def test_goal_has_no_criteria():
    from app.schemas import GoalOut

    assert "criteria" not in GoalOut.model_fields


async def test_push_test_notification_is_in_the_persons_language(client, monkeypatch):
    """The text moved from services/reminders.py; the Russian one is formal and has no
    gendered verb ("Над чем работал" was v1)."""
    from app.routers import push as push_router

    sent = []

    async def fake_send(db, user_id, payload):
        sent.append(payload)
        return 1

    monkeypatch.setattr(push_router.push_service, "send_to_user", fake_send)
    ru = await register(client, "ru@example.com", locale="ru")
    en = await register(client, "en@example.com", locale="en")
    assert (await client.post("/api/push/test", headers=ru)).json() == {"delivered": 1}
    assert (await client.post("/api/push/test", headers=en)).status_code == 200

    assert sent[0]["title"] == "Уведомления работают"
    assert sent[1]["title"] == "Notifications work"
    assert all(p["url"] == "/today" and p["body"] for p in sent)
    assert not re.search(r"\b(ты|тебя|твой|работал)\b", sent[0]["body"].lower())
