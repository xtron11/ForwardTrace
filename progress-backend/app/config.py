import os
import re
from dataclasses import dataclass
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


@dataclass(frozen=True)
class Limit:
    count: int
    window_sec: int


_LIMIT = re.compile(r"^\s*(\d+)\s*/\s*(\d*)\s*([smhd])\s*$")
_UNIT_SEC = {"s": 1, "m": 60, "h": 3600, "d": 86400}


@lru_cache
def parse_limits(spec: str) -> tuple[Limit, ...]:
    """"5/15m" is five in any fifteen minutes. Several rules, comma separated, must all
    hold: "1/1m,5/1h". Empty means no limit."""
    limits = []
    for part in spec.split(","):
        if not part.strip():
            continue
        match = _LIMIT.match(part)
        if not match or int(match[1]) < 1:
            raise ValueError(f"not a rate limit: {part.strip()!r} (expected e.g. 5/15m)")
        limits.append(Limit(int(match[1]), int(match[2] or 1) * _UNIT_SEC[match[3]]))
    return tuple(limits)


class Settings(BaseSettings):
    # APP_ENV_FILE="" disables the file entirely. The test suite does this so a
    # developer's real keys and limits never leak into the results.
    model_config = SettingsConfigDict(
        env_file=os.environ.get("APP_ENV_FILE", ".env") or None, extra="ignore"
    )

    # --- database ---
    database_url: str = "postgresql+asyncpg://progress:progress@localhost:5432/progress"

    # --- auth ---
    jwt_secret: str = "CHANGE-ME-openssl-rand-hex-32"
    jwt_algorithm: str = "HS256"
    access_token_ttl_min: int = 30
    refresh_token_ttl_days: int = 60
    password_min_length: int = 8

    # --- speech to text ---
    # deepgram -> Nova-3 batch. Purpose-built STT, per-second billing, $200 starting
    #             credit (~46k minutes). Sub-second on a 60s clip.
    # local    -> faster-whisper here. Free, private, 8-30s per audio minute on CPU.
    stt_provider: str = "deepgram"
    # Fallback only. The real language comes from the speaker's profile locale - a
    # shared setting would transcribe half your testers as if they spoke the other
    # half's language.
    # Pins the language for every user. Leave empty unless detection is failing on
    # your audio - a wrong value here produces confident nonsense, not an error.
    stt_language: str | None = None
    # Let the provider detect the language per recording. Preferred: it survives a user
    # whose browser language does not match the language they actually speak.
    stt_detect_language: bool = True
    stt_timeout_sec: int = 120
    # Extra attempts after a rate limit, a server error or a dropped connection.
    # Errors in the request itself (bad audio, bad key) are never repeated.
    stt_max_retries: int = 2
    # Code-switching: "сегодня час писал на Python, застрял на recursion". Set true to
    # send language=multi instead of a single language. Costs keyterm prompting.
    stt_multilingual: bool = False

    deepgram_api_key: str | None = None
    deepgram_base_url: str = "https://api.deepgram.com"
    deepgram_model: str = "nova-3"
    # Domain vocabulary Deepgram should listen for. Without this, "recursion" comes back
    # as "a course" and "LeetCode" as "leet code". Comma separated.
    stt_keyterms: str = "recursion,LeetCode,API,Python,TypeScript,refactor,debugging,endpoint"

    whisper_model: str = "base.en"  # base.en ~8-10s/min on 4 cores; small.en ~25s/min
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    stt_concurrency: int = 1  # CPU inference must not run in parallel

    # --- llm (extraction + report narration), OpenAI only ---
    llm_concurrency: int = 4
    llm_timeout_sec: int = 180
    # Extra attempts after a rate limit, a server error, a dropped connection or a
    # reply that is not valid JSON. A 400-class error is never repeated.
    llm_max_retries: int = 2

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    # Must be the explicit tier id. The bare "gpt-5.6" alias routes to Sol, the
    # flagship, at 25x the price for work that does not need it.
    openai_model: str = "gpt-5.6-luna"
    # none | low | medium | high | xhigh | max. Extraction is a copying task with a
    # grammar-constrained output, so deep reasoning buys nothing and costs latency.
    openai_reasoning_effort: str = "low"

    # --- cost accounting ---
    # Prices are configured by hand because neither provider reports them in the
    # response. Token counts are stored per entry as well, so a wrong price here can be
    # corrected after the fact. USD.
    # Deepgram Nova-3 pre-recorded, pay-as-you-go, billed per second.
    stt_price_per_min: float = 0.0043
    # OpenAI prices per million tokens for OPENAI_MODEL. Left at zero, the cost columns
    # stay zero and only tokens are counted - a warning at startup says so.
    llm_price_input_per_1m: float = 0.0
    # Cached prompt tokens are billed at a discount. Empty means the full input price.
    llm_price_cached_input_per_1m: float | None = None
    llm_price_output_per_1m: float = 0.0

    # --- error tracking (Sentry) ---
    # Empty DSN turns Sentry off entirely: local development and the tests send nothing.
    sentry_dsn: str | None = None
    sentry_environment: str = "production"
    # Share of requests and background jobs traced. The per-call LLM and STT spans,
    # with their token counts and cost, are only visible on sampled traces; errors are
    # always sent regardless of this.
    sentry_traces_sample_rate: float = 1.0

    # --- storage ---
    audio_dir: str = "./data/audio"
    # 60 seconds of Opus is well under 1 MB. 10 MB is generous for a check-in and
    # still bounds what a single request can cost.
    max_audio_mb: int = 10
    keep_audio: bool = True  # keep the raw file so you can listen back during research

    # --- app ---
    cors_origins: str = "http://localhost:3000"
    report_period_days: int = 7
    # The first report comes early on purpose. A week of input before any output is a
    # long time to trust a stranger's product, and most people who quit do it before
    # day seven - so they never see the thing the product exists for.
    first_report_after_days: int = 3
    # 1-5 keeps this a progress tool. Past that it becomes a life-management system,
    # which is a different product and a different hypothesis.
    max_active_goals: int = 5
    # The person decides how much they take on, but matching what they said against
    # what they intended stops being reliable past a handful - the model starts
    # stretching any mention to fit any intention.
    max_active_tasks: int = 5
    # Days of quiet after someone declines. Asking again the next evening is nagging.
    task_suggestion_cooldown_days: int = 3

    # --- per-user daily quotas ---
    # Every voice check-in costs money: speech-to-text plus a model call. Without a
    # ceiling, one hostile signup can drain the balance in an afternoon. Counted per
    # user per local day, and counted on upload rather than on success, because a
    # request that reached the provider has already been paid for.
    max_voice_entries_per_day: int = 3
    # Typed check-ins skip speech-to-text, so they are cheaper and get more headroom.
    max_text_entries_per_day: int = 10
    # The one-off transcription used for the "why does this matter" field at signup.
    max_onboarding_transcribes_per_day: int = 5

    # --- brute-force protection ---
    # For the endpoints anyone can call without a session, counted both per address and
    # per IP: per IP alone misses one account guessed at from a thousand addresses, per
    # address alone misses one address trying a thousand accounts. Format: see
    # parse_limits. Sign-in counts only wrong passwords; registration and the resend
    # count every request, because each of them sends a letter.
    login_limit_per_email: str = "5/15m"
    # Looser than per address: an office or a mobile carrier puts many people behind one.
    login_limit_per_ip: str = "20/15m"
    admin_login_limit_per_email: str = "3/15m"
    admin_login_limit_per_ip: str = "10/1h"
    register_limit_per_email: str = "3/1h"
    register_limit_per_ip: str = "5/1h"
    resend_limit_per_email: str = "1/1m,5/1h"
    resend_limit_per_ip: str = "10/1h"
    # The header the platform's edge writes the caller's address into, replacing
    # whatever the caller sent. Railway: X-Real-IP. Not X-Forwarded-For: Railway has no
    # stable contract for it, and uvicorn's --forwarded-allow-ips '*' takes its leftmost
    # entry, which the caller writes. Empty uses the connection, which behind a proxy is
    # the proxy - every user would then share one count.
    client_ip_header: str = "X-Real-IP"

    # --- email ---
    # Without a key nothing is sent and verification is skipped entirely, so local
    # development and the test suite need no mail server.
    resend_api_key: str | None = None
    email_from: str = "ForwardTrace <onboarding@resend.dev>"
    # Where the link in the letter points. Must be the frontend, not the API.
    app_url: str = "http://localhost:3000"
    email_verification_ttl_hours: int = 48
    # Unverified accounts can look around but cannot spend money on speech-to-text
    # and model calls. That is the whole reason this exists.
    require_verified_email: bool = True

    # --- account deletion ---
    # A deleted account is kept this long so it can be restored from the letter, then
    # erased with every row and recording it owns.
    account_restore_days: int = 30
    # How often the eraser looks for accounts whose grace period is over.
    account_purge_tick_minutes: int = 60

    # --- push reminders ---
    # Generate a keypair once with: python -m app.vapid
    # Changing these invalidates every existing subscription, so keep them.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    # Contact address the push services can reach you at if your sends misbehave.
    vapid_subject_email: str = "admin@example.com"
    # A reminder about today is worthless tomorrow, so let it expire.
    push_ttl_seconds: int = 12 * 60 * 60
    # Local hour, per user, when the nudge goes out. Evening: the day is over and there
    # is something to say about it.
    default_reminder_hour: int = 20
    # How often the scheduler wakes. Fifteen minutes is close enough for a reminder and
    # cheap enough to run forever.
    reminder_tick_minutes: int = 15
    reminders_enabled: bool = True
    min_entries_for_report: int = 3
    # Three check-ins in a three-day window means perfect attendance. Two is enough to
    # show the mechanism, which is all the first report needs to do.
    min_entries_first_report: int = 2
    admin_emails: str = ""  # comma separated
    # Alembic owns the schema now. create_all cannot alter an existing table, so
    # leaving this on would silently skip every column added after the first run.
    auto_create_tables: bool = False

    @field_validator("database_url")
    @classmethod
    def use_async_driver(cls, v: str) -> str:
        """Managed platforms hand out a sync URL; this app needs the async driver.

        Railway, Render and Heroku all inject DATABASE_URL as postgresql:// (or the
        older postgres://). SQLAlchemy would pick psycopg, which cannot run in an async
        engine, and the failure is a confusing InvalidRequestError at startup rather
        than anything mentioning the driver.
        """
        for prefix in ("postgresql+asyncpg://", "sqlite+aiosqlite://"):
            if v.startswith(prefix):
                return v
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+asyncpg://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+asyncpg://", 1)
        return v

    @field_validator(
        "login_limit_per_email",
        "login_limit_per_ip",
        "admin_login_limit_per_email",
        "admin_login_limit_per_ip",
        "register_limit_per_email",
        "register_limit_per_ip",
        "resend_limit_per_email",
        "resend_limit_per_ip",
    )
    @classmethod
    def valid_limit(cls, v: str) -> str:
        """A typo in a limit fails at startup, not as a 500 on the sign-in screen."""
        parse_limits(v)
        return v

    @property
    def keyterm_list(self) -> list[str]:
        return [k.strip() for k in self.stt_keyterms.split(",") if k.strip()]

    @property
    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def admin_email_list(self) -> list[str]:
        return [e.strip().lower() for e in self.admin_emails.split(",") if e.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
