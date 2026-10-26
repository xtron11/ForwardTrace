"""Stage 0 and stage 1 of v2: configuration, the data model, shared helpers, account
erasure, and the migrations on Postgres (0014 and 0015, which drops v1)."""

import pytest
from pydantic import ValidationError

from conftest import register

DEFAULT_JWT_SECRET = "CHANGE-ME-openssl-rand-hex-32"


# ------------------------------------------------------------------ stage 0


class TestStartupGuard:
    def test_default_jwt_secret_is_refused_outside_tests(self):
        from app.config import Settings

        with pytest.raises(ValidationError) as caught:
            Settings(_env_file=None, jwt_secret=DEFAULT_JWT_SECRET, app_env="production")
        message = str(caught.value)
        assert "JWT_SECRET" in message
        # The error names the variable, never a value.
        assert DEFAULT_JWT_SECRET not in message

    def test_default_jwt_secret_is_refused_when_app_env_is_unset(self, monkeypatch):
        from app.config import Settings

        monkeypatch.delenv("APP_ENV", raising=False)
        with pytest.raises(ValidationError):
            Settings(_env_file=None, jwt_secret=DEFAULT_JWT_SECRET)

    def test_test_environment_may_run_with_the_default(self):
        from app.config import Settings

        assert Settings(_env_file=None, jwt_secret=DEFAULT_JWT_SECRET, app_env="test")

    def test_the_env_example_placeholder_is_refused_outside_tests(self):
        """Whoever copies .env.example to .env and forgets the secret must not start."""
        import re
        from pathlib import Path

        from app.config import Settings

        example = (Path(__file__).resolve().parents[1] / ".env.example").read_text("utf-8")
        found = re.search(r"^JWT_SECRET=(.*)$", example, re.M)
        assert found, "JWT_SECRET line missing from .env.example"
        placeholder = found[1].strip()
        with pytest.raises(ValidationError) as caught:
            Settings(_env_file=None, jwt_secret=placeholder, app_env="production")
        assert "JWT_SECRET" in str(caught.value)

    @pytest.mark.parametrize("secret", ["", "   ", "replace-me", "a" * 31])
    def test_empty_short_and_known_placeholders_are_refused(self, secret):
        from app.config import Settings

        with pytest.raises(ValidationError):
            Settings(_env_file=None, jwt_secret=secret, app_env="development")

    def test_a_32_character_secret_is_enough(self):
        from app.config import Settings

        assert Settings(_env_file=None, jwt_secret="b" * 32, app_env="production")

    def test_a_real_secret_starts_anywhere(self):
        from app.config import Settings

        assert Settings(_env_file=None, jwt_secret="a" * 64, app_env="production")


class TestChangePassword:
    @pytest.mark.asyncio
    async def test_new_password_over_72_bytes_is_rejected_like_registration(self, client):
        auth = await register(client)
        # 40 Cyrillic letters: 40 characters, 80 bytes.
        long_password = "ж" * 40
        r = await client.post(
            "/api/auth/change-password",
            headers=auth,
            json={"current_password": "supersecret1", "new_password": long_password},
        )
        assert r.status_code == 422, r.text
        # The old password still works: nothing was changed.
        login = await client.post(
            "/api/auth/login", json={"email": "person@example.com", "password": "supersecret1"}
        )
        assert login.status_code == 200

    @pytest.mark.asyncio
    async def test_72_bytes_exactly_is_accepted(self, client):
        auth = await register(client)
        r = await client.post(
            "/api/auth/change-password",
            headers=auth,
            json={"current_password": "supersecret1", "new_password": "ж" * 36},
        )
        assert r.status_code == 200, r.text


# ------------------------------------------------------------------ shared helpers


class TestApiError:
    def test_detail_carries_a_machine_code_and_a_message(self):
        from fastapi import HTTPException

        from app.services.errors import api_error

        exc = api_error(402, "limit_reached", "Free conversations for this week are used up.")
        assert isinstance(exc, HTTPException)
        assert exc.status_code == 402
        assert exc.detail == {
            "code": "limit_reached",
            "message": "Free conversations for this week are used up.",
        }


class TestTexts:
    def test_russian_greeting_uses_formal_address(self):
        from app.services.texts import t

        greeting = t("ru", "first.greeting")
        # spec §6, word for word
        assert greeting == (
            "Здравствуйте! Я помогу вам замечать, как вы растёте, — вашими же словами. "
            "Что вы сейчас развиваете?"
        )

    def test_placeholders_are_filled(self):
        from app.services.texts import t

        assert t("ru", "monthly.thin", month="октябрь") == "Мало данных за октябрь — вот что есть"
        assert "October" in t("en", "monthly.ready", month="October")

    def test_quick_replies_for_the_first_question(self):
        from app.services.texts import quick

        assert quick("ru", "first.skills") == [
            "Программирование", "Геймдев", "Иностранный язык", "Спорт", "Музыка",
        ]
        assert len(quick("en", "first.skills")) == 5
        assert quick("ru", "first.schedule") == ["После занятия", "Вечером", "Выберу время"]

    def test_unknown_or_regional_locale_falls_back(self):
        from app.services.texts import t

        assert t("ru-RU", "outreach.general") == "Что сегодня получилось, что раньше не получалось?"
        assert t("de", "outreach.general") == t("en", "outreach.general")
        assert t(None, "outreach.general") == t("en", "outreach.general")

    def test_both_languages_have_the_same_keys(self):
        from app.services.texts import EN, RU

        assert set(RU) == set(EN)
        for key in RU:
            assert type(RU[key]) is type(EN[key]), key

    def test_russian_texts_never_use_informal_address(self):
        """«вы» everywhere (spec §1.1): no «ты» forms and no gendered past tense of the
        person («прошёл», «начинал», «сам»)."""
        import re

        from app.services.texts import RU

        informal = re.compile(
            r"\b(ты|тебе|тебя|тобой|твой|твоя|твоё|твои|твоими|твоих|сам|сама"
            r"|начинал|прошёл|рассказывал|захочешь|хочешь|скажешь)\b",
            re.IGNORECASE,
        )
        for key, value in RU.items():
            for line in value if isinstance(value, list) else [value]:
                assert not informal.search(line), f"{key}: {line}"


class TestLogEvent:
    @pytest.mark.asyncio
    async def test_event_gets_day_number_language_and_channel(self, client):
        from datetime import datetime, timedelta, timezone

        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import Event, User
        from app.services.events import log_event

        await register(client, "ru@example.com", locale="ru", timezone="Asia/Almaty")
        async with SessionLocal() as db:
            user = (await db.execute(select(User))).scalar_one()
            # Registered two days ago (local dates in Almaty) -> today is day 3.
            user.created_at = datetime.now(timezone.utc) - timedelta(days=2)
            user.outreach_channel = "telegram"
            await db.commit()

            await log_event(db, user, "message_sent", {"source": "voice"})
            await db.commit()
            event = (
                await db.execute(select(Event).where(Event.type == "message_sent"))
            ).scalar_one()

        assert event.user_id == user.id
        assert event.payload == {
            "source": "voice",
            "day_number": 3,
            "language": "ru",
            "channel": "telegram",
        }

    @pytest.mark.asyncio
    async def test_event_without_a_user(self):
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import Event
        from app.services.events import log_event

        async with SessionLocal() as db:
            await log_event(db, None, "telegram_unknown_token")
            await db.commit()
            event = (await db.execute(select(Event))).scalar_one()
        assert event.user_id is None
        assert event.type == "telegram_unknown_token"


# ------------------------------------------------------------------ profile fields


class TestProfileV2:
    @pytest.mark.asyncio
    async def test_me_has_the_v2_fields(self, client):
        auth = await register(client, timezone="Asia/Almaty")
        me = (await client.get("/api/auth/me", headers=auth)).json()
        assert me["skill"] is None
        assert me["country"] == "KZ"  # from the timezone
        assert me["outreach_channel"] == "push"
        assert me["telegram_linked"] is False
        assert me["plus_until"] is None
        assert me["first_conversation_done"] is False
        assert "telegram_chat_id" not in me
        assert "telegram_link_token" not in me

    @pytest.mark.asyncio
    async def test_unknown_timezone_leaves_country_empty(self, client):
        auth = await register(client, timezone="UTC")
        assert (await client.get("/api/auth/me", headers=auth)).json()["country"] is None

    @pytest.mark.asyncio
    async def test_patch_accepts_skill_country_and_channel(self, client):
        auth = await register(client)
        r = await client.patch(
            "/api/auth/me",
            headers=auth,
            json={"skill": "английский", "country": "de", "outreach_channel": "none"},
        )
        assert r.status_code == 200, r.text
        body = r.json()
        assert (body["skill"], body["country"], body["outreach_channel"]) == (
            "английский", "DE", "none",
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "payload",
        [
            {"outreach_channel": "email"},
            {"country": "Kazakhstan"},
            {"country": "k1"},
            {"skill": "x" * 121},
        ],
    )
    async def test_patch_rejects_bad_values(self, client, payload):
        auth = await register(client)
        r = await client.patch("/api/auth/me", headers=auth, json=payload)
        assert r.status_code == 422, r.text

    @pytest.mark.asyncio
    async def test_timezone_change_moves_a_default_country(self, client):
        auth = await register(client, timezone="Asia/Almaty")
        r = await client.patch("/api/auth/me", headers=auth, json={"timezone": "Europe/Berlin"})
        assert r.json()["country"] == "DE"

    @pytest.mark.asyncio
    async def test_timezone_change_keeps_a_country_chosen_explicitly(self, client):
        auth = await register(client, timezone="Asia/Almaty")
        await client.patch("/api/auth/me", headers=auth, json={"country": "UZ"})
        r = await client.patch("/api/auth/me", headers=auth, json={"timezone": "Europe/Berlin"})
        assert r.json()["country"] == "UZ"

    @pytest.mark.asyncio
    async def test_country_in_the_same_patch_as_timezone_wins(self, client):
        auth = await register(client, timezone="Asia/Almaty")
        r = await client.patch(
            "/api/auth/me", headers=auth, json={"timezone": "Europe/Berlin", "country": "KZ"}
        )
        assert r.json()["country"] == "KZ"


# ------------------------------------------------------------------ data model


async def _seed_v2(user_id, audio_dir) -> dict:
    """One of every v2 row for a user, with a recording on disk."""
    import uuid
    from datetime import date
    from pathlib import Path

    from app.db import SessionLocal
    from app.models import (
        Conversation, Fact, Goal, Message, MonthlySummary, Outreach, Pair, Thread,
    )

    day = date(2026, 9, 17)
    async with SessionLocal() as db:
        conversation = Conversation(user_id=user_id, local_date=day, kind="first", state={})
        db.add(conversation)
        await db.flush()
        message_id = uuid.uuid4()
        audio = Path(audio_dir) / str(user_id) / f"{message_id}.webm"
        audio.parent.mkdir(parents=True, exist_ok=True)
        audio.write_bytes(b"x" * 64)
        message = Message(
            id=message_id, conversation_id=conversation.id, user_id=user_id, role="user",
            source="voice", content_raw="персонаж проваливался сквозь пол",
            content=[{"type": "text", "text": "персонаж проваливался сквозь пол"}],
            audio_path=str(audio), words=[{"w": "персонаж", "start": 0.1, "end": 0.6}],
        )
        db.add(message)
        await db.flush()
        then = Fact(user_id=user_id, message_id=message.id, local_date=day, type="struggle",
                    text="Падение сквозь пол", quote="персонаж проваливался сквозь пол")
        now = Fact(user_id=user_id, message_id=message.id, local_date=day, type="achievement",
                   text="Починил коллизии", quote="проваливался сквозь пол")
        db.add_all([then, now])
        await db.flush()
        thread = Thread(user_id=user_id, title="Коллизии", opened_fact_id=then.id, opened_on=day)
        db.add(thread)
        await db.flush()
        then.thread_id = thread.id
        db.add_all([
            Pair(user_id=user_id, then_fact_id=then.id, now_fact_id=now.id, theme="Коллизии",
                 recalled=True, source="first_conversation"),
            MonthlySummary(user_id=user_id, month=date(2026, 9, 1), status="thin", stats={}),
            Outreach(user_id=user_id, conversation_id=conversation.id, message_id=message.id,
                     topic="thread", thread_id=thread.id, channel="push", delivered=True),
            Goal(user_id=user_id, title="Геймдев", why_message_id=message.id,
                 baseline_message_id=message.id, finish_line="Выпустить демо",
                 finish_set_on=day),
        ])
        await db.commit()
    return {"message_id": message_id, "audio": audio}


class TestSchemasV2:
    @pytest.mark.asyncio
    async def test_message_out_renders_segments_from_the_row(self, client, tmp_path):
        from sqlalchemy import select

        from app.db import SessionLocal
        from app.models import Message, User
        from app.schemas import MessageOut

        await register(client)
        async with SessionLocal() as db:
            user = (await db.execute(select(User))).scalar_one()
        seeded = await _seed_v2(user.id, tmp_path)
        async with SessionLocal() as db:
            message = await db.get(Message, seeded["message_id"])
            message.content = [
                {"type": "text", "text": "Смотрите: "},
                {"type": "quote", "fact_id": str(seeded["message_id"]),
                 "quote": "проваливался сквозь пол", "local_date": "2026-09-17",
                 "recalled": True},
            ]
            out = MessageOut.model_validate(message).model_dump(mode="json")
        assert out["has_audio"] is True
        assert out["content"][0] == {"type": "text", "text": "Смотрите: "}
        assert out["content"][1]["type"] == "quote"
        assert out["content"][1]["recalled"] is True
        assert out["content"][1]["audio_start_ms"] is None


class TestErasureV2:
    @pytest.mark.asyncio
    async def test_erase_leaves_no_v2_rows_and_no_message_audio(self, client, tmp_path, monkeypatch):
        from sqlalchemy import func, select

        from app.config import settings
        from app.db import SessionLocal
        from app.models import (
            Conversation, Fact, Goal, Message, MonthlySummary, Outreach, Pair, Thread, User,
        )
        from app.services import accounts

        monkeypatch.setattr(settings, "audio_dir", str(tmp_path))
        await register(client, "leaver@example.com")
        await register(client, "stayer@example.com")
        async with SessionLocal() as db:
            users = {u.email: u.id for u in (await db.execute(select(User))).scalars()}
        leaver = await _seed_v2(users["leaver@example.com"], tmp_path)
        stayer = await _seed_v2(users["stayer@example.com"], tmp_path)

        async with SessionLocal() as db:
            await accounts.erase(db, users["leaver@example.com"])

        tables = (Conversation, Message, Fact, Thread, Pair, MonthlySummary, Outreach, Goal)
        async with SessionLocal() as db:
            for model in tables:
                left = (await db.execute(
                    select(func.count()).select_from(model)
                    .where(model.user_id == users["leaver@example.com"])
                )).scalar_one()
                assert left == 0, model.__tablename__
                kept = (await db.execute(
                    select(func.count()).select_from(model)
                    .where(model.user_id == users["stayer@example.com"])
                )).scalar_one()
                assert kept == (2 if model is Fact else 1), model.__tablename__
        assert not leaver["audio"].exists()
        assert stayer["audio"].exists()


class TestCostsV2:
    USAGE = {"prompt_tokens": 1_000_000, "completion_tokens": 1_000_000}

    def test_chat_and_safety_models_have_their_own_price_slots(self, monkeypatch):
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "openai_model", "base-model")
        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "llm_price_output_per_1m", 2.0)
        monkeypatch.setattr(settings, "chat_model", "chat-model")
        monkeypatch.setattr(settings, "chat_price_input_per_1m", 10.0)
        monkeypatch.setattr(settings, "chat_price_output_per_1m", 20.0)
        monkeypatch.setattr(settings, "safety_model", "safety-model")
        monkeypatch.setattr(settings, "safety_price_input_per_1m", 100.0)
        monkeypatch.setattr(settings, "safety_price_output_per_1m", 200.0)

        assert costs.record_llm("base-model", self.USAGE) == pytest.approx(3.0)
        assert costs.record_llm("chat-model", self.USAGE) == pytest.approx(30.0)
        # Providers answer with a dated snapshot name.
        assert costs.record_llm("safety-model-2026-09-01", self.USAGE) == pytest.approx(300.0)

    def test_embedding_price(self, monkeypatch):
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "embedding_model", "embed-model")
        monkeypatch.setattr(settings, "embedding_price_per_1m", 0.5)
        with costs.track() as usage:
            assert costs.record_embedding("embed-model", {"prompt_tokens": 2_000_000}) == (
                pytest.approx(1.0)
            )
        assert usage.llm_usd == pytest.approx(1.0)

    def test_unpriced_models_are_listed_for_the_startup_warning(self, monkeypatch):
        from app.config import settings
        from app.services import costs

        monkeypatch.setattr(settings, "openai_model", "base-model")
        monkeypatch.setattr(settings, "llm_price_input_per_1m", 1.0)
        monkeypatch.setattr(settings, "chat_model", "chat-model")
        monkeypatch.setattr(settings, "chat_price_input_per_1m", 0.0)
        monkeypatch.setattr(settings, "chat_price_output_per_1m", 0.0)
        monkeypatch.setattr(settings, "safety_model", "base-model")
        monkeypatch.setattr(settings, "embedding_model", "embed-model")
        monkeypatch.setattr(settings, "embedding_price_per_1m", 0.0)
        assert costs.missing_prices() == ["CHAT_MODEL", "EMBEDDING_MODEL"]

    def test_charge_message_adds_stt_and_llm(self):
        from app.models import Message
        from app.services import costs

        message = Message(role="user", cost_usd=None)
        costs.charge_message(message, costs.Usage(stt_seconds=60, stt_usd=0.25, llm_calls=1,
                                                  llm_usd=0.5))
        costs.charge_message(message, costs.Usage(llm_calls=1, llm_usd=0.25))
        assert message.cost_usd == pytest.approx(1.0)


# ------------------------------------------------------------------ migrations on Postgres


def _postgres_url() -> str:
    import os

    url = os.environ.get("TEST_POSTGRES_URL")
    if not url:
        pytest.skip("TEST_POSTGRES_URL is not set (a throwaway Postgres 16 database)")
    from app.config import Settings

    return Settings.use_async_driver(url)


def _alembic(url: str, *args: str) -> None:
    import os
    import subprocess
    import sys
    from pathlib import Path

    env = {
        **os.environ,
        "DATABASE_URL": url,
        "APP_ENV": "test",
        "APP_ENV_FILE": "",
        "JWT_SECRET": "test-secret-not-used-anywhere-real",
    }
    done = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        cwd=Path(__file__).resolve().parents[1], env=env, capture_output=True, text=True,
    )
    assert done.returncode == 0, done.stderr[-2000:]


async def _reset_schema(url: str) -> None:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    async with engine.begin() as conn:
        await conn.execute(text("DROP SCHEMA public CASCADE"))
        await conn.execute(text("CREATE SCHEMA public"))
    await engine.dispose()


V1_TABLES = ("criteria", "entries", "activities", "reports", "tasks", "task_mentions")


async def _schema(url: str, tables) -> dict:
    """Columns (type, nullability, default), indexes, unique constraints and foreign
    keys of the given tables, plus the users columns - comparable across revisions."""
    from sqlalchemy import inspect
    from sqlalchemy.ext.asyncio import create_async_engine

    def read(sync_conn) -> dict:
        insp = inspect(sync_conn)
        present = set(insp.get_table_names())
        out = {"users": sorted(c["name"] for c in insp.get_columns("users"))}
        for table in tables:
            if table not in present:
                out[table] = None
                continue
            out[table] = {
                "columns": sorted(
                    (c["name"], str(c["type"]), c["nullable"], str(c.get("default")))
                    for c in insp.get_columns(table)
                ),
                "indexes": sorted(
                    (i["name"], tuple(i["column_names"]), bool(i["unique"]))
                    for i in insp.get_indexes(table)
                ),
                "unique": sorted(
                    (u["name"], tuple(u["column_names"]))
                    for u in insp.get_unique_constraints(table)
                ),
                "foreign_keys": sorted(
                    (tuple(f["constrained_columns"]), f["referred_table"],
                     (f.get("options") or {}).get("ondelete"))
                    for f in insp.get_foreign_keys(table)
                ),
            }
        return out

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return await conn.run_sync(read)
    finally:
        await engine.dispose()


async def _count(url: str, table: str) -> int:
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(url)
    try:
        async with engine.connect() as conn:
            return (await conn.execute(text(f"SELECT count(*) FROM {table}"))).scalar_one()
    finally:
        await engine.dispose()


@pytest.mark.postgres
class TestMigrationsOnPostgres:
    @pytest.mark.asyncio
    async def test_clean_database_upgrades_to_head_and_passes_the_schema_check(
        self, monkeypatch
    ):
        from sqlalchemy.ext.asyncio import create_async_engine

        from app import main

        url = _postgres_url()
        await _reset_schema(url)
        _alembic(url, "upgrade", "head")
        _alembic(url, "downgrade", "0013_account_deletion")
        _alembic(url, "upgrade", "head")

        schema = await _schema(url, V1_TABLES)
        assert all(schema[table] is None for table in V1_TABLES)
        assert "tasks_declined_on" not in schema["users"]

        engine = create_async_engine(url)
        monkeypatch.setattr(main, "engine", engine)
        try:
            await main._check_schema()  # raises listing anything a model has and the DB lacks
        finally:
            await engine.dispose()

    @pytest.mark.asyncio
    async def test_0015_drops_v1_keeps_v2_and_its_downgrade_restores_the_schema(self):
        import uuid

        from sqlalchemy import text
        from sqlalchemy.ext.asyncio import create_async_engine

        url = _postgres_url()
        await _reset_schema(url)
        _alembic(url, "upgrade", "0014_v2_core")
        before = await _schema(url, V1_TABLES)
        assert all(before[table] is not None for table in V1_TABLES)
        assert "tasks_declined_on" in before["users"]

        ids = {name: uuid.uuid4() for name in (
            "user", "goal", "criterion", "entry", "activity", "report", "task", "mention",
            "conversation",
        )}
        engine = create_async_engine(url)
        async with engine.begin() as conn:
            for sql in (
                "INSERT INTO users (id, email, password_hash, tasks_declined_on)"
                " VALUES (:user, 'v1@x.io', 'h', DATE '2026-09-01')",
                "INSERT INTO goals (id, user_id, title, why_source)"
                " VALUES (:goal, :user, 'Game dev', 'text')",
                "INSERT INTO criteria (id, goal_id, text, source, position)"
                " VALUES (:criterion, :goal, 'Ship a demo', 'user', 0)",
                "INSERT INTO entries (id, user_id, goal_id, local_date, source, status)"
                " VALUES (:entry, :user, :goal, DATE '2026-09-17', 'text', 'done')",
                "INSERT INTO activities (id, entry_id, user_id, local_date, category,"
                " category_key, minutes_explicit)"
                " VALUES (:activity, :entry, :user, DATE '2026-09-17', 'Gamedev', 'gamedev', false)",
                "INSERT INTO reports (id, user_id, period_start, period_end, status, generated_by)"
                " VALUES (:report, :user, DATE '2026-09-11', DATE '2026-09-17', 'done', 'ai')",
                "INSERT INTO tasks (id, user_id, text, starts_on, ends_on)"
                " VALUES (:task, :user, 'Save system', DATE '2026-09-17', DATE '2026-09-18')",
                "INSERT INTO task_mentions (id, task_id, entry_id, local_date)"
                " VALUES (:mention, :task, :entry, DATE '2026-09-17')",
                "INSERT INTO conversations (id, user_id, local_date, kind, started_by)"
                " VALUES (:conversation, :user, DATE '2026-09-18', 'daily', 'user')",
            ):
                await conn.execute(text(sql), ids)
        await engine.dispose()

        _alembic(url, "upgrade", "head")
        after = await _schema(url, V1_TABLES)
        assert all(after[table] is None for table in V1_TABLES)
        assert "tasks_declined_on" not in after["users"]
        # v2 rows and the shared tables are untouched.
        for table in ("users", "goals", "conversations"):
            assert await _count(url, table) == 1

        _alembic(url, "downgrade", "0014_v2_core")
        assert await _schema(url, V1_TABLES) == before
        for table in V1_TABLES:
            assert await _count(url, table) == 0  # the schema comes back, the rows do not

        _alembic(url, "upgrade", "head")
