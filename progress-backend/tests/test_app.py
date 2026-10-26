"""Accounts, sign-in protection, letters, push subscriptions, provider calls and health.

The v1 suite (check-ins, extraction, weekly reports, tasks, criteria, quotas) went with
v1 in stage 10; v2 behaviour lives in tests/test_v2_*.py. Shared fixtures (fresh_db,
client) and the provider fakes are in conftest.py. Runs on SQLite, needs no keys and no
database server.
"""

import asyncio
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest
from sqlalchemy import select

from app.db import SessionLocal
from app.services import llm, prompts, verify
from conftest import register as _register

TRANSCRIPT = (
    "Today I coded for about two hours. I finished the API and I was stuck on "
    "authentication for a while, but I figured it out on my own without looking at a "
    "tutorial. I also listened to English for thirty minutes."
)


async def register(client, email="admin@example.com", locale="en"):
    """admin@example.com by default: it is in ADMIN_EMAILS (conftest.py)."""
    return await _register(client, email, locale)


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


# --------------------------------------------------------------- email verification


class TestEmailVerification:
    """The gate is at the door, not at the first message: an unverified account cannot
    get a session at all."""

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


# --------------------------------------------------------------- auth


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


# --------------------------------------------------------------- localisation


class TestLocalisation:
    def test_russian_locale_adds_an_output_language_directive(self):
        assert "Russian" in prompts.pair_theme_system("ru")
        assert "Russian" in prompts.first_skill_system("ru-RU")
        assert "Russian" in prompts.safety_system("ru")

    def test_english_prompts_are_left_untouched(self):
        assert prompts.pair_theme_system("en") == prompts.PAIR_THEME_SYSTEM
        assert prompts.first_skill_system(None) == prompts.FIRST_SKILL_SYSTEM

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


# --------------------------------------------------------------- push subscriptions


class TestPushSubscriptions:
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
        assert len(rows) == 1, "one browser must not receive two of every message"


# --------------------------------------------------------------- timezones


class TestTimezones:
    def test_local_date_follows_the_user_not_the_server(self):
        from datetime import datetime, timezone as dt_timezone

        from app.time_utils import local_today

        # 06:40 UTC on Tuesday is 23:40 Monday in Los Angeles (UTC-7 in August).
        moment = datetime(2026, 8, 18, 6, 40, tzinfo=dt_timezone.utc)
        assert local_today("America/Los_Angeles", moment) == date(2026, 8, 17)
        assert local_today("Asia/Almaty", moment) == date(2026, 8, 18)


# --------------------------------------------------------------- cost accounting


class TestCostAccounting:
    """Every provider call is priced and counted, inside a meter or not."""

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

    @staticmethod
    async def _seed(user_id, audio_dir: Path) -> Path:
        """A goal, a day with a voice message (its recording on disk) and a push
        subscription; returns the recording."""
        from app.models import Conversation, Goal, Message, PushSubscription

        folder = audio_dir / str(user_id)
        folder.mkdir(parents=True, exist_ok=True)
        message_id = uuid.uuid4()
        recording = folder / f"{message_id}.webm"
        recording.write_bytes(b"x" * 64)
        async with SessionLocal() as db:
            conversation = Conversation(user_id=user_id, local_date=date(2026, 9, 17))
            db.add_all([Goal(user_id=user_id, title="Improve English"), conversation])
            await db.flush()
            db.add(Message(
                id=message_id, conversation_id=conversation.id, user_id=user_id, role="user",
                source="voice", content=[{"type": "text", "text": "Read a chapter"}],
                audio_path=str(recording), audio_mime="audio/webm",
            ))
            db.add(PushSubscription(
                user_id=user_id, endpoint=f"https://p/{user_id}", p256dh="k", auth="a"
            ))
            await db.commit()
        return recording

    @staticmethod
    async def _user_id(email: str):
        from app.models import User

        async with SessionLocal() as db:
            return (await db.execute(select(User.id).where(User.email == email))).scalar_one()

    @pytest.mark.asyncio
    async def test_after_the_grace_period_everything_is_erased_and_nothing_else(
        self, client, monkeypatch, tmp_path
    ):
        from app.config import settings
        from app.models import Conversation, Event, Goal, Message, PushSubscription, User
        from app.services import accounts

        monkeypatch.setattr(settings, "audio_dir", str(tmp_path))

        auth = await register(client, "leaver@example.com")
        leaver_id = await self._user_id("leaver@example.com")
        recording = await self._seed(leaver_id, tmp_path)

        await register(client, "stayer@example.com")
        kept = await self._seed(await self._user_id("stayer@example.com"), tmp_path)

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
            for model in (Conversation, Message, Goal, PushSubscription, Event):
                left = (
                    await db.execute(select(model).where(model.user_id == leaver_id))
                ).scalars().all()
                assert left == [], f"{model.__tablename__} kept rows of an erased account"
            assert await db.get(User, leaver_id) is None
            others = (await db.execute(select(Message))).scalars().all()
            assert len(others) == 1 and Path(others[0].audio_path).exists()
        assert kept.exists()

        # The old letter leads nowhere, and the address is free again.
        token = links[0].split("token=")[1]
        assert (await client.post("/api/auth/restore", json={"token": token})).status_code == 400
        monkeypatch.setattr(settings, "resend_api_key", None)
        await register(client, "leaver@example.com")

    @pytest.mark.asyncio
    async def test_a_deleted_account_is_not_written_to_first(self, client, monkeypatch):
        """The AI writing first (services/outreach.py) skips a deleted account; the same
        set-up without the deletion is written to."""
        from app.models import User
        from app.services import outreach

        sent: list = []

        async def fake_push(db, user_id, payload):
            sent.append(user_id)
            return 1

        monkeypatch.setattr(outreach.push, "send_to_user", fake_push)
        now = datetime(2026, 9, 17, 3, 0, tzinfo=timezone.utc)  # 20:00 in Los Angeles
        auth = await register(client, "leaver@example.com")
        await register(client, "stayer@example.com")
        self._capture_letters(monkeypatch)
        async with SessionLocal() as db:
            for user in (await db.execute(select(User))).scalars():
                user.first_conversation_done = True
                user.reminder_hour = 20
            await db.commit()

        await client.delete("/api/auth/me", headers=auth)

        assert await outreach.run_once(now) == 1
        assert sent == [await self._user_id("stayer@example.com")]
