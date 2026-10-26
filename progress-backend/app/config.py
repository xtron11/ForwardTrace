import os
import re
from dataclasses import dataclass
from functools import lru_cache

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


# The placeholder shipped in code and .env.example. Tokens signed with it can be forged
# by anyone who has read this repository, so only the test suite may run with it.
DEFAULT_JWT_SECRET = "CHANGE-ME-openssl-rand-hex-32"


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

    # production | development | test. Only "test" may run with the default JWT_SECRET.
    app_env: str = "production"

    # --- database ---
    database_url: str = "postgresql+asyncpg://progress:progress@localhost:5432/progress"

    # --- auth ---
    jwt_secret: str = DEFAULT_JWT_SECRET
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

    # --- llm (replies, memory, safety, outreach, monthly summary), OpenAI only ---
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
    # none | low | medium | high | xhigh | max. Memory extraction is a copying task with
    # a grammar-constrained output, so deep reasoning buys nothing and costs latency.
    openai_reasoning_effort: str = "low"

    # --- v2 models ---
    # The conversation reply. Empty means OPENAI_MODEL.
    chat_model: str | None = None
    chat_reasoning_effort: str = "low"
    # safety_check on every message the person sends. Empty means OPENAI_MODEL.
    safety_model: str | None = None
    # OpenAI embeddings model for facts. Empty: facts are found by date, not by meaning.
    embedding_model: str | None = None

    # --- cost accounting ---
    # Prices are configured by hand because neither provider reports them in the
    # response. Token counts are logged as well, so a wrong price here can be corrected
    # after the fact. USD.
    # Deepgram Nova-3 pre-recorded, pay-as-you-go, billed per second.
    stt_price_per_min: float = 0.0043
    # OpenAI prices per million tokens for OPENAI_MODEL. Left at zero, the cost columns
    # stay zero and only tokens are counted - a warning at startup says so.
    llm_price_input_per_1m: float = 0.0
    # Cached prompt tokens are billed at a discount. Empty means the full input price.
    llm_price_cached_input_per_1m: float | None = None
    llm_price_output_per_1m: float = 0.0
    # Prices for CHAT_MODEL and SAFETY_MODEL when they differ from OPENAI_MODEL (when
    # they are the same model, the OPENAI_MODEL prices above apply). Zero until filled.
    chat_price_input_per_1m: float = 0.0
    chat_price_cached_input_per_1m: float | None = None
    chat_price_output_per_1m: float = 0.0
    safety_price_input_per_1m: float = 0.0
    safety_price_cached_input_per_1m: float | None = None
    safety_price_output_per_1m: float = 0.0
    # EMBEDDING_MODEL, per million input tokens. Zero until filled.
    embedding_price_per_1m: float = 0.0

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
    # 60 seconds of Opus is well under 1 MB. 10 MB is generous for a voice message and
    # still bounds what a single request can cost. Recordings are kept: quotes are
    # played back from them.
    max_audio_mb: int = 10

    # --- app ---
    cors_origins: str = "http://localhost:3000"

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
    # and model calls (403 email_not_verified). That is the whole reason this exists.
    require_verified_email: bool = True

    # --- account deletion ---
    # A deleted account is kept this long so it can be restored from the letter, then
    # erased with every row and recording it owns.
    account_restore_days: int = 30
    # How often the eraser looks for accounts whose grace period is over.
    account_purge_tick_minutes: int = 60

    # --- push (the AI's messages) ---
    # Generate a keypair once with: python -m app.vapid
    # Changing these invalidates every existing subscription, so keep them.
    vapid_public_key: str | None = None
    vapid_private_key: str | None = None
    # Contact address the push services can reach you at if your sends misbehave.
    vapid_subject_email: str = "admin@example.com"
    # A message about today is worthless tomorrow, so let it expire.
    push_ttl_seconds: int = 12 * 60 * 60
    # How often the outreach loop wakes (services/outreach.py). Fifteen minutes is close
    # enough to each person's hour and cheap enough to run forever.
    reminder_tick_minutes: int = 15
    # False turns off the AI writing first entirely.
    reminders_enabled: bool = True
    admin_emails: str = ""  # comma separated

    # --- v2: limit and the Plus door ---
    # Days without any limit after registration, counted in the person's local dates.
    free_trial_days: int = 7
    # Conversations per calendar week (Monday to Sunday, local time) after the trial.
    free_conversations_per_week: int = 3
    # What pressing "Continue with Plus" gives during the beta.
    plus_beta_days: int = 30

    # --- v2: conversation ---
    # Reply rules, checked after the stream (a streamed reply cannot be regenerated):
    # a violation is logged as reply_rule_violation for review.
    reply_max_words: int = 120
    # A longer reply is fine when the person wrote at length themselves.
    reply_max_words_long: int = 250
    reply_long_input_words: int = 150
    # Context passed to the model with each message.
    context_facts: int = 5
    context_threads: int = 5
    context_days: int = 3
    # A voice message whose transcript is shorter than this is "no speech".
    no_speech_min_chars: int = 10
    max_text_chars: int = 4000
    max_quick_replies: int = 5
    # Pairs from the first conversation's "where are you now and where did you start".
    first_baseline_max_pairs: int = 3
    # GET /api/calendar range limit.
    calendar_max_days: int = 62

    # --- v2: memory ---
    # A conversation is processed once it has been quiet this long.
    memory_idle_minutes: int = 30
    memory_tick_minutes: int = 5
    # Local hour at which the day is closed and any unprocessed conversation extracted.
    close_day_hour: int = 4
    # GET /api/memory: how many recent facts.
    memory_recent_facts: int = 50
    # A "then -> now" pair needs this many days between the two facts...
    pair_min_days: int = 7
    # ...and, when matched by meaning rather than by a thread, this cosine similarity.
    pair_min_similarity: float = 0.8

    # --- v2: monthly summary ---
    # Below both thresholds the summary is "thin" and no model is called.
    monthly_min_conversations: int = 8
    monthly_min_pairs: int = 2
    monthly_tick_minutes: int = 60

    # --- v2: the AI writes first (outreach) ---
    # Runs on reminder_tick_minutes, at each person's reminder_hour.
    outreach_max_words: int = 25
    # After this many unanswered messages in a row, write only every N days.
    outreach_pause_after: int = 3
    outreach_pause_every_days: int = 3
    # After this many days of silence, one farewell, then nothing until they write.
    outreach_farewell_days: int = 14
    # Topic order: a thread mentioned within N days, then the goal after N silent days.
    outreach_thread_recent_days: int = 3
    outreach_anchor_silence_days: int = 2

    # --- v2: safety ---
    # Help lines per country, filled in by the owner from official sources only:
    # {"KZ": [{"name": "...", "contact": "..."}], "default": [...]}. Never invent these.
    safety_resources: dict[str, list[dict[str, str]]] = {}
    # Suggest a doctor or psychologist once when level 1 was seen on at least MIN days of
    # the last WINDOW days, and not again for COOLDOWN days.
    safety_help_window_days: int = 14
    safety_help_min_days: int = 5
    safety_help_cooldown_days: int = 14

    # --- v2: Telegram ---
    # Without a token every Telegram endpoint answers 503 and the channel is hidden.
    telegram_bot_token: str | None = None
    telegram_bot_username: str | None = None
    # Compared with the X-Telegram-Bot-Api-Secret-Token header on the webhook.
    telegram_webhook_secret: str | None = None
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

    @model_validator(mode="after")
    def v2_defaults_and_secrets(self) -> "Settings":
        if self.app_env != "test" and self.jwt_secret == DEFAULT_JWT_SECRET:
            raise ValueError(
                "JWT_SECRET is still the placeholder from the code. Set JWT_SECRET in "
                ".env to a random value (openssl rand -hex 32). Only APP_ENV=test may "
                "run without one."
            )
        # Empty CHAT_MODEL / SAFETY_MODEL mean "the same model as OPENAI_MODEL".
        self.chat_model = self.chat_model or self.openai_model
        self.safety_model = self.safety_model or self.openai_model
        # An empty line in .env means "not set", not an empty value.
        self.embedding_model = self.embedding_model or None
        self.telegram_bot_token = self.telegram_bot_token or None
        self.telegram_bot_username = self.telegram_bot_username or None
        self.telegram_webhook_secret = self.telegram_webhook_secret or None
        return self

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
