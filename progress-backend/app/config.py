from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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

    # --- llm (extraction + report narration) ---
    # ollama -> local, free, 5-20s per call on CPU
    # openai -> gpt-5-mini or similar; pennies per month at this volume
    llm_provider: str = "ollama"
    llm_concurrency: int = 4
    llm_timeout_sec: int = 180
    llm_max_retries: int = 2

    ollama_url: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b-instruct"

    openai_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    # Must be the explicit tier id. The bare "gpt-5.6" alias routes to Sol, the
    # flagship, at 25x the price for work that does not need it.
    openai_model: str = "gpt-5.6-luna"
    # none | low | medium | high | xhigh | max. Extraction is a copying task with a
    # grammar-constrained output, so deep reasoning buys nothing and costs latency.
    openai_reasoning_effort: str = "low"

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
