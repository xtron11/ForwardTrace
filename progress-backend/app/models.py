import enum
import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    Uuid,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base

# Postgres is the production target, so JSONB and native uuid are what actually ship.
# The SQLite variants exist purely so the test suite runs without a database server.
JsonB = JSON().with_variant(JSONB(), "postgresql")
PgUUID = Uuid(as_uuid=True)


class Status(str, enum.Enum):
    pending = "pending"
    processing = "processing"
    # Speech-to-text finished; waiting for the person to confirm or correct the text
    # before anything is extracted from it.
    awaiting_review = "awaiting_review"
    done = "done"
    failed = "failed"


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID, primary_key=True, default=uuid.uuid4)


def fk(target: str, ondelete: str = "CASCADE", index: bool = True, nullable: bool = False):
    return mapped_column(
        PgUUID,
        ForeignKey(target, ondelete=ondelete),
        index=index,
        nullable=nullable,
    )


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True)  # stored lowercase
    password_hash: Mapped[str] = mapped_column(String(255))
    display_name: Mapped[str | None] = mapped_column(String(120))
    # IANA name, e.g. "America/Los_Angeles". Drives every "day" and "week" boundary.
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", server_default="UTC")
    # BCP-47 language tag from the browser. Reports and extraction are written in this
    # language: a report the person has to translate is not evidence they will feel.
    locale: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    # bumped on password change / logout-everywhere; old JWTs stop validating
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # raw answers to the 5 intake questions, kept for research
    intake: Mapped[dict | None] = mapped_column(JsonB)
    cohort: Mapped[str | None] = mapped_column(String(64))
    # Local hour for the daily nudge, and the last local date one was sent, so a
    # scheduler that wakes every fifteen minutes cannot send four in an hour.
    reminder_hour: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    reminders_on: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_reminded_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    title: Mapped[str] = mapped_column(String(200))
    why_text: Mapped[str | None] = mapped_column(Text)
    why_source: Mapped[str] = mapped_column(String(16), default="text")  # text | voice
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    started_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    user: Mapped[User] = relationship(back_populates="goals")
    criteria: Mapped[list["Criterion"]] = relationship(
        back_populates="goal", cascade="all, delete-orphan", order_by="Criterion.position"
    )


class Criterion(Base):
    """User-owned definition of what progress looks like. The report is graded against these."""

    __tablename__ = "criteria"

    id: Mapped[uuid.UUID] = pk()
    goal_id: Mapped[uuid.UUID] = fk("goals.id")
    text: Mapped[str] = mapped_column(String(300))
    source: Mapped[str] = mapped_column(String(8), default="user")  # ai | user
    position: Mapped[int] = mapped_column(Integer, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    goal: Mapped[Goal] = relationship(back_populates="criteria")


class Entry(Base):
    """One check-in. Audio lands first, transcript and extraction are filled in by the worker."""

    __tablename__ = "entries"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    goal_id: Mapped[uuid.UUID | None] = fk("goals.id", ondelete="SET NULL", nullable=True)

    local_date: Mapped[date] = mapped_column(Date)  # computed from the user's timezone
    source: Mapped[str] = mapped_column(String(16), default="voice")  # voice | text

    audio_path: Mapped[str | None] = mapped_column(String(512))
    audio_mime: Mapped[str | None] = mapped_column(String(64))
    audio_seconds: Mapped[float | None] = mapped_column(Float)

    raw_transcript: Mapped[str | None] = mapped_column(Text)
    # What the provider decided it heard. Worth keeping: a mismatch against the user's
    # profile locale is the signal that one of the two is wrong.
    detected_language: Mapped[str | None] = mapped_column(String(16))
    # What speech-to-text originally heard, kept when the person corrects it. The gap
    # between the two is the honest measure of transcription quality.
    stt_transcript: Mapped[str | None] = mapped_column(Text)
    transcript_edited: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    mood: Mapped[str | None] = mapped_column(String(32))
    wins: Mapped[list | None] = mapped_column(JsonB)      # [{"text":..., "quote":...}]
    friction: Mapped[list | None] = mapped_column(JsonB)  # [{"text":..., "quote":...}]

    status: Mapped[str] = mapped_column(String(16), default=Status.pending.value, index=True)
    error: Mapped[str | None] = mapped_column(Text)
    # observability: we care about latency, so measure it instead of guessing
    stt_ms: Mapped[int | None] = mapped_column(Integer)
    llm_ms: Mapped[int | None] = mapped_column(Integer)
    dropped_facts: Mapped[int] = mapped_column(Integer, default=0, server_default="0")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    activities: Mapped[list["Activity"]] = relationship(
        back_populates="entry", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_entries_user_local_date", "user_id", "local_date"),)


class Activity(Base):
    """Extracted, quote-verified facts. Normalised into rows so stats are plain SQL."""

    __tablename__ = "activities"

    id: Mapped[uuid.UUID] = pk()
    entry_id: Mapped[uuid.UUID] = fk("entries.id")
    user_id: Mapped[uuid.UUID] = fk("users.id")
    goal_id: Mapped[uuid.UUID | None] = fk("goals.id", ondelete="SET NULL", nullable=True)
    local_date: Mapped[date] = mapped_column(Date)

    category: Mapped[str] = mapped_column(String(80))       # display form, e.g. "Programming"
    category_key: Mapped[str] = mapped_column(String(80))   # normalised, e.g. "programming"
    minutes: Mapped[int | None] = mapped_column(Integer)    # NULL when not stated by the user
    minutes_explicit: Mapped[bool] = mapped_column(Boolean, default=False)
    details: Mapped[list | None] = mapped_column(JsonB)     # ["finished the API", ...]
    # Countable quantities the person stated: [{"name": "new words", "value": 10,
    # "unit": "words", "quote": "..."}]. Summed across the week to show growth.
    metrics: Mapped[list | None] = mapped_column(JsonB)
    quote: Mapped[str | None] = mapped_column(Text)         # verbatim span from the transcript

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    entry: Mapped[Entry] = relationship(back_populates="activities")

    __table_args__ = (
        Index("ix_activities_user_date", "user_id", "local_date"),
        Index("ix_activities_user_category", "user_id", "category_key"),
    )


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    goal_id: Mapped[uuid.UUID | None] = fk("goals.id", ondelete="SET NULL", nullable=True)

    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)  # inclusive

    status: Mapped[str] = mapped_column(String(16), default=Status.pending.value)
    stats: Mapped[dict | None] = mapped_column(JsonB)    # computed in Python, never by the LLM
    content: Mapped[dict | None] = mapped_column(JsonB)  # narrative blocks
    generated_by: Mapped[str] = mapped_column(String(16), default="ai")  # ai | human
    model_name: Mapped[str | None] = mapped_column(String(80))
    generation_ms: Mapped[int | None] = mapped_column(Integer)
    error: Mapped[str | None] = mapped_column(Text)

    feedback_rating: Mapped[int | None] = mapped_column(Integer)  # 4 love .. 1 useless
    feedback_text: Mapped[str | None] = mapped_column(Text)
    feedback_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        UniqueConstraint("user_id", "goal_id", "period_start", name="uq_report_period"),
    )


class PushSubscription(Base):
    """One browser on one device. A person with a laptop and a phone has two."""

    __tablename__ = "push_subscriptions"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    # The push service URL. Unique because re-subscribing the same browser returns the
    # same endpoint, and duplicates would mean duplicate notifications.
    endpoint: Mapped[str] = mapped_column(Text, unique=True)
    p256dh: Mapped[str] = mapped_column(String(255))
    auth: Mapped[str] = mapped_column(String(255))
    user_agent: Mapped[str | None] = mapped_column(String(255))
    failure_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Event(Base):
    """Append-only research log: opened_report, started_recording, abandoned_checkin, ..."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict | None] = mapped_column(JsonB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
