import uuid
from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field, field_validator

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


class UserOut(ORM):
    id: uuid.UUID
    email: str
    display_name: str | None
    timezone: str
    locale: str
    cohort: str | None
    intake: dict | None
    created_at: datetime


class UserUpdate(BaseModel):
    display_name: str | None = Field(default=None, max_length=120)
    timezone: str | None = None
    locale: str | None = None
    cohort: str | None = Field(default=None, max_length=64)
    intake: dict | None = None

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


# ---------------- goals ----------------

class CriterionIn(BaseModel):
    text: str = Field(min_length=2, max_length=300)
    source: str = "user"


class CriterionOut(ORM):
    id: uuid.UUID
    text: str
    source: str
    position: int


class GoalCreate(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    why_text: str | None = Field(default=None, max_length=4000)
    why_source: str = "text"
    criteria: list[CriterionIn] = Field(default_factory=list, max_length=10)


class GoalUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=200)
    why_text: str | None = Field(default=None, max_length=4000)
    is_active: bool | None = None
    criteria: list[CriterionIn] | None = Field(default=None, max_length=10)


class GoalOut(ORM):
    id: uuid.UUID
    title: str
    why_text: str | None
    why_source: str
    is_active: bool
    started_on: date | None
    created_at: datetime
    criteria: list[CriterionOut] = []


class SuggestCriteriaIn(BaseModel):
    title: str = Field(min_length=2, max_length=200)
    why_text: str | None = Field(default=None, max_length=2000)


class SuggestCriteriaOut(BaseModel):
    criteria: list[str]


# ---------------- entries ----------------

class TextEntryIn(BaseModel):
    text: str = Field(min_length=1, max_length=8000)
    goal_id: uuid.UUID | None = None


class ConfirmTranscriptIn(BaseModel):
    """The transcript as the person approved it, corrections included."""

    text: str = Field(min_length=1, max_length=8000)


class ReassignActivityIn(BaseModel):
    """Move a misrouted activity to the right goal, or to none."""

    goal_id: uuid.UUID | None = None


class ActivityOut(ORM):
    id: uuid.UUID
    goal_id: uuid.UUID | None
    category: str
    minutes: int | None
    minutes_explicit: bool
    details: list | None
    metrics: list | None
    quote: str | None


class EntryOut(ORM):
    id: uuid.UUID
    goal_id: uuid.UUID | None
    local_date: date
    source: str
    status: str
    audio_seconds: float | None
    raw_transcript: str | None
    detected_language: str | None
    stt_transcript: str | None
    transcript_edited: bool
    mood: str | None
    wins: list | None
    friction: list | None
    error: str | None
    stt_ms: int | None
    llm_ms: int | None
    dropped_facts: int
    created_at: datetime
    activities: list[ActivityOut] = []


class EntryAccepted(BaseModel):
    id: uuid.UUID
    status: str
    local_date: date
    poll_url: str


class TranscribeOut(BaseModel):
    text: str
    seconds: float | None
    stt_ms: int


# ---------------- reports ----------------

class ReportOut(ORM):
    id: uuid.UUID
    goal_id: uuid.UUID | None
    period_start: date
    period_end: date
    status: str
    stats: dict | None
    content: dict | None
    generated_by: str
    error: str | None
    feedback_rating: int | None
    feedback_text: str | None
    created_at: datetime


class ReportGenerateIn(BaseModel):
    goal_id: uuid.UUID | None = None
    period_end: date | None = None  # defaults to the last completed period
    force: bool = False


class FeedbackIn(BaseModel):
    rating: int = Field(ge=1, le=4)  # 4 love it, 3 useful, 2 meh, 1 useless
    text: str | None = Field(default=None, max_length=4000)


class EventIn(BaseModel):
    type: str = Field(max_length=64)
    payload: dict | None = None
