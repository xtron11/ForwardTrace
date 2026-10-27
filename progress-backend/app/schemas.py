import uuid
from datetime import date, datetime
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, computed_field, field_validator

from .config import settings
from .security import MAX_PASSWORD_BYTES
from .time_utils import valid_timezone


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ---------------- auth ----------------

SUPPORTED_LOCALES = {"en", "ru"}


def _normalize_locale(value: str) -> str:
    """'ru-RU' -> 'ru'. Anything unsupported falls back to English."""
    base = (value or "").split("-")[0].lower()
    return base if base in SUPPORTED_LOCALES else "en"


class RegisterIn(BaseModel):
    email: EmailStr
    password: str
    display_name: str | None = Field(default=None, max_length=120)
    timezone: str = "UTC"
    locale: str = "en"

    @field_validator("locale")
    @classmethod
    def check_locale(cls, v: str) -> str:
        return _normalize_locale(v)

    @field_validator("password")
    @classmethod
    def check_password(cls, v: str) -> str:
        if len(v) < settings.password_min_length:
            raise ValueError(f"password must be at least {settings.password_min_length} characters")
        if len(v.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("password is too long")
        return v

    @field_validator("timezone")
    @classmethod
    def check_tz(cls, v: str) -> str:
        if not valid_timezone(v):
            raise ValueError("unknown IANA timezone")
        return v


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class RefreshIn(BaseModel):
    refresh_token: str


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class ChangePasswordIn(BaseModel):
    current_password: str
    new_password: str = Field(min_length=settings.password_min_length)

    @field_validator("new_password")
    @classmethod
    def check_length_in_bytes(cls, v: str) -> str:
        # bcrypt reads at most 72 bytes; registration refuses longer ones, so must this.
        if len(v.encode()) > MAX_PASSWORD_BYTES:
            raise ValueError("password is too long")
        return v


class UserOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str | None
    timezone: str
    locale: str
    email_verified: bool
    reminder_hour: int
    reminders_on: bool
    cohort: str | None
    intake: dict | None
    created_at: datetime
    # v2
    skill: str | None = None
    country: str | None = None
    outreach_channel: str = "push"
    plus_until: date | None = None
    first_conversation_done: bool = False
    # Read from the row, never sent: the client only needs to know whether it is set.
    telegram_chat_id: int | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def telegram_linked(self) -> bool:
        return self.telegram_chat_id is not None

    @computed_field
    @property
    def telegram_available(self) -> bool:
        """Whether the server runs the bot at all (services/telegram.enabled): the
        profile offers the channel only then, without creating a link to find out."""
        return bool(settings.telegram_bot_token and settings.telegram_bot_username)


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    timezone: str | None = None
    locale: str | None = None
    reminder_hour: int | None = Field(default=None, ge=0, le=23)
    reminders_on: bool | None = None
    cohort: str | None = Field(default=None, max_length=64)
    intake: dict | None = None
    # v2
    skill: str | None = Field(default=None, max_length=120)
    # ISO 3166 alpha-2, any case; null clears it (help lines fall back to "default").
    country: str | None = None
    outreach_channel: Literal["push", "telegram", "none"] | None = None

    @field_validator("country")
    @classmethod
    def check_country(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip().upper()
        if len(v) != 2 or not v.isascii() or not v.isalpha():
            raise ValueError("country must be a two-letter ISO 3166 code")
        return v

    @field_validator("skill")
    @classmethod
    def strip_skill(cls, v: str | None) -> str | None:
        return (v.strip() or None) if v is not None else None

    @field_validator("timezone")
    @classmethod
    def check_tz(cls, v: str | None) -> str | None:
        if v is not None and not valid_timezone(v):
            raise ValueError("unknown IANA timezone")
        return v

    @field_validator("locale")
    @classmethod
    def check_locale(cls, v: str | None) -> str | None:
        return None if v is None else _normalize_locale(v)


# ---------------- goal ----------------

class GoalOut(ORM):
    """The anchor goal. Created in the first conversation, edited with PATCH /api/goal."""

    id: uuid.UUID
    title: str
    why_text: str | None
    why_source: str
    why_audio_seconds: float | None
    is_active: bool
    started_on: date | None
    created_at: datetime
    # null = "no finish line, just grow".
    finish_line: str | None = None
    finish_set_on: date | None = None


# ---------------- account ----------------

class VerifyIn(BaseModel):
    token: str


class ResendIn(BaseModel):
    email: EmailStr


class RegisteredOut(BaseModel):
    """No tokens: the account is not usable until the address is confirmed."""

    verification_required: bool
    email: str


class EventIn(BaseModel):
    type: str = Field(max_length=64)
    payload: dict | None = None


class RestoreIn(BaseModel):
    token: str


class AccountDeletedOut(BaseModel):
    """What the person needs to hear straight after deleting: until when it can be
    undone, and where the way back was sent."""

    email: str
    erase_on: date
    restore_days: int
    letter_sent: bool


# ====================================================================== v2
# Conversations, memory and progress. Errors of these endpoints are
# {"detail": {"code", "message"}} (services/errors.py).


class TextSegment(BaseModel):
    type: Literal["text"] = "text"
    text: str


class QuoteSegment(BaseModel):
    """A verified quote, filled in by code from `facts`; the model only names the id."""

    type: Literal["quote"] = "quote"
    fact_id: uuid.UUID
    quote: str
    local_date: date
    # From the first conversation: "from your recollection".
    recalled: bool = False
    # The quote's place in the recording of message_id, when aligned.
    audio_start_ms: int | None = None
    audio_end_ms: int | None = None
    message_id: uuid.UUID | None = None


Segment = Annotated[TextSegment | QuoteSegment, Field(discriminator="type")]


class MessageOut(ORM):
    id: uuid.UUID
    role: str
    source: str
    content: list[Segment]
    quick_replies: list[str] | None
    intent: str | None
    rating: str | None
    has_audio: bool
    audio_seconds: float | None
    detected_language: str | None
    created_at: datetime


class LimitOut(BaseModel):
    """Conversations counted this week, the free allowance, and whether Plus or the
    trial lifts the limit right now."""

    used: int
    free: int
    plus: bool
    trial: bool


class ConversationOut(BaseModel):
    id: uuid.UUID
    local_date: date
    kind: str
    started_by: str
    state: dict | None
    messages: list[MessageOut]
    limit: LimitOut


class ThreadBrief(BaseModel):
    id: uuid.UUID
    title: str
    status: str


class DayOut(BaseModel):
    local_date: date
    summary: str | None
    started_by: str
    threads: list[ThreadBrief]
    message_count: int


class ThreadOut(ORM):
    id: uuid.UUID
    title: str
    kind: str = "struggle"  # struggle | topic
    status: str
    opened_on: date
    closed_on: date | None
    last_mentioned_on: date | None


class ThreadUpdate(BaseModel):
    status: Literal["closed", "deleted"] | None = None
    title: str | None = Field(default=None, min_length=1, max_length=200)


class FactOut(ORM):
    id: uuid.UUID
    type: str
    text: str
    quote: str
    local_date: date
    message_id: uuid.UUID | None
    audio_start_ms: int | None
    audio_end_ms: int | None
    flagged_at: datetime | None = Field(default=None, exclude=True)

    @computed_field
    @property
    def flagged(self) -> bool:
        return self.flagged_at is not None


class PairOut(BaseModel):
    id: uuid.UUID
    theme: str
    recalled: bool
    source: str
    then: FactOut
    now: FactOut


class GoalPatch(BaseModel):
    """PATCH /api/goal. finish_line: null means "no finish line"."""

    title: str | None = Field(default=None, min_length=1, max_length=200)
    why_text: str | None = Field(default=None, max_length=4000)
    finish_line: str | None = Field(default=None, max_length=300)


class MemoryOut(BaseModel):
    goal: GoalOut | None
    open_threads: list[ThreadOut]
    closed_threads: list[ThreadOut]
    facts: list[FactOut]


class MonthlyContentOut(BaseModel):
    intro: list[Segment]
    open_struggle: list[Segment]
    next_step: list[Segment]


class MonthlySummaryOut(BaseModel):
    month: str  # "YYYY-MM"
    status: str  # done | thin | failed
    stats: dict | None
    content: MonthlyContentOut | None
    viewed_at: datetime | None


class ProgressOut(BaseModel):
    goal: GoalOut | None
    level_facts: list[FactOut]
    pairs: list[PairOut]
    open_threads: list[ThreadOut]
    closed_threads: list[ThreadOut]
    monthly: MonthlySummaryOut | None


class RatingIn(BaseModel):
    rating: Literal["helped", "not_it"]


class SearchHitOut(BaseModel):
    local_date: date
    message_id: uuid.UUID
    snippet: str


class CalendarDayOut(BaseModel):
    local_date: date
    active: bool


class PaywallClickOut(BaseModel):
    plus_until: date


class TelegramLinkOut(BaseModel):
    url: str
