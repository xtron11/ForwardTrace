import uuid
from datetime import date, datetime

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    Numeric,
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


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(PgUUID, primary_key=True, default=uuid.uuid4)


def fk(
    target: str,
    ondelete: str = "CASCADE",
    index: bool = True,
    nullable: bool = False,
    use_alter: bool = False,
):
    # use_alter is for the one cycle in the schema (facts.thread_id and
    # threads.opened_fact_id / closed_fact_id), so create_all and drop_all can order it.
    return mapped_column(
        PgUUID,
        ForeignKey(target, ondelete=ondelete, use_alter=use_alter),
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
    # en | ru. Replies, memory and every server text are written in this language.
    locale: Mapped[str] = mapped_column(String(8), default="en", server_default="en")
    email_verified: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    # Resending is possible without a session, so it needs a floor of its own.
    verification_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # bumped on password change / logout-everywhere; old JWTs stop validating
    token_version: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    # raw answers to the 5 intake questions, kept for research
    intake: Mapped[dict | None] = mapped_column(JsonB)
    cohort: Mapped[str | None] = mapped_column(String(64))
    # Local hour at which the AI writes first, and the last local date it did, so a
    # loop that wakes every fifteen minutes cannot write four times in an hour.
    reminder_hour: Mapped[int] = mapped_column(Integer, default=20, server_default="20")
    reminders_on: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    last_reminded_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Set when the person deletes the account. Nothing is erased yet: until the grace
    # period runs out the account can be restored from the letter, and after that
    # services/accounts.py erases it with everything it owns.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    # The restore letter is resent on every sign-in attempt, so it needs a floor.
    restore_sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    # --- v2 ---
    # What they are developing, from the first conversation ("английский").
    skill: Mapped[str | None] = mapped_column(String(120))
    # ISO 3166 alpha-2 for help-line contacts. Defaults from the timezone; null = unknown.
    country: Mapped[str | None] = mapped_column(String(2))
    # How the AI writes first: push | telegram | none.
    outreach_channel: Mapped[str] = mapped_column(
        String(16), default="push", server_default="push"
    )
    telegram_chat_id: Mapped[int | None] = mapped_column(BigInteger)
    # One-time token in the t.me/<bot>?start=<token> link; cleared once used.
    telegram_link_token: Mapped[str | None] = mapped_column(String(64), unique=True)
    # AI-initiated messages in a row without a reply; drives the outreach pauses.
    outreach_unanswered: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # Beta Plus after the fake door: no weekly limit while plus_until >= today (local).
    plus_until: Mapped[date | None] = mapped_column(Date)
    first_conversation_done: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )

    goals: Mapped[list["Goal"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Goal(Base):
    __tablename__ = "goals"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    title: Mapped[str] = mapped_column(String(200))
    why_text: Mapped[str | None] = mapped_column(Text)
    why_source: Mapped[str] = mapped_column(String(16), default="text")  # text | voice
    # The recording itself, kept rather than transcribed and thrown away. Hearing
    # yourself from the day you decided this carries something the transcript does not.
    why_audio_path: Mapped[str | None] = mapped_column(String(512))
    why_audio_mime: Mapped[str | None] = mapped_column(String(64))
    why_audio_seconds: Mapped[float | None] = mapped_column(Float)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
    started_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    # --- v2: the anchor goal with a finish line ---
    # The message the motivation quote (why_text) was taken from.
    why_message_id: Mapped[uuid.UUID | None] = fk(
        "messages.id", ondelete="SET NULL", nullable=True, index=False
    )
    # "Level B2"; null means no finish line ("I just want to grow").
    finish_line: Mapped[str | None] = mapped_column(String(300))
    finish_set_on: Mapped[date | None] = mapped_column(Date)
    # "Where I am now and where I started", from the first conversation.
    baseline_message_id: Mapped[uuid.UUID | None] = fk(
        "messages.id", ondelete="SET NULL", nullable=True, index=False
    )

    user: Mapped[User] = relationship(back_populates="goals")


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
    """Append-only research log: message_sent, ai_reply, outreach_opened, ... (services/events.py)."""

    __tablename__ = "events"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID | None] = fk("users.id", nullable=True)
    type: Mapped[str] = mapped_column(String(64), index=True)
    payload: Mapped[dict | None] = mapped_column(JsonB)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


# ====================================================================== v2


class Conversation(Base):
    """Everything said on one local day of the person. kind: first | daily."""

    __tablename__ = "conversations"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    local_date: Mapped[date] = mapped_column(Date)
    kind: Mapped[str] = mapped_column(String(16), default="daily")  # first | daily
    started_by: Mapped[str] = mapped_column(String(8), default="user")  # user | ai
    # First-conversation step and any other per-day state.
    state: Mapped[dict | None] = mapped_column(JsonB)
    # The day in one line, written by memory extraction.
    summary: Mapped[str | None] = mapped_column(String(200))
    # Highest safety level seen today.
    safety_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    # True once the person sent a message: counts toward the weekly limit and paints
    # the day green on the week strip. An unanswered AI message does not count.
    counts_for_limit: Mapped[bool] = mapped_column(
        Boolean, default=False, server_default="false"
    )
    memory_extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    __table_args__ = (UniqueConstraint("user_id", "local_date", name="uq_conversation_day"),)


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = pk()
    conversation_id: Mapped[uuid.UUID] = fk("conversations.id", index=False)
    user_id: Mapped[uuid.UUID] = fk("users.id")
    role: Mapped[str] = mapped_column(String(16))  # user | assistant
    source: Mapped[str] = mapped_column(String(16), default="text")  # text | voice | outreach
    # For the assistant: the text with {{quote:<fact_id>}} placeholders.
    content_raw: Mapped[str] = mapped_column(Text, default="", server_default="")
    # Rendered segments: [{type: "text", text}, {type: "quote", fact_id, quote, ...}].
    content: Mapped[list] = mapped_column(JsonB, default=list)
    # Word timings from speech-to-text: [{"w", "start", "end"}], seconds.
    words: Mapped[list | None] = mapped_column(JsonB)
    audio_path: Mapped[str | None] = mapped_column(String(512))
    audio_mime: Mapped[str | None] = mapped_column(String(64))
    audio_seconds: Mapped[float | None] = mapped_column(Float)
    detected_language: Mapped[str | None] = mapped_column(String(16))
    quick_replies: Mapped[list | None] = mapped_column(JsonB)
    used_fact_ids: Mapped[list | None] = mapped_column(JsonB)
    intent: Mapped[str | None] = mapped_column(String(16))  # normal | plateau
    safety_level: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    rating: Mapped[str | None] = mapped_column(String(16))  # helped | not_it
    model_name: Mapped[str | None] = mapped_column(String(80))
    llm_ms: Mapped[int | None] = mapped_column(Integer)
    stt_ms: Mapped[int | None] = mapped_column(Integer)
    # Speech-to-text plus every model call for this message, USD (services/costs.py).
    cost_usd: Mapped[float | None] = mapped_column(Numeric(12, 6, asdecimal=False))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    @property
    def has_audio(self) -> bool:
        """Whether the recording is still on disk (a deploy without a volume loses it)."""
        from pathlib import Path as _Path

        return bool(self.audio_path) and _Path(self.audio_path).exists()

    __table_args__ = (Index("ix_messages_conversation_created", "conversation_id", "created_at"),)


class Fact(Base):
    """Something the person said, with a verbatim quote that passed services/verify.py."""

    __tablename__ = "facts"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", index=False)
    # Null for facts imported from v1 (they came from entries, not messages).
    message_id: Mapped[uuid.UUID | None] = fk("messages.id", ondelete="SET NULL", nullable=True)
    origin: Mapped[str] = mapped_column(String(16), default="conversation")  # | import_v1
    local_date: Mapped[date] = mapped_column(Date)
    # achievement | struggle | learned | level (where they are relative to the finish)
    type: Mapped[str] = mapped_column(String(16))
    text: Mapped[str] = mapped_column(String(300))
    quote: Mapped[str] = mapped_column(Text)
    audio_start_ms: Mapped[int | None] = mapped_column(Integer)
    audio_end_ms: Mapped[int | None] = mapped_column(Integer)
    thread_id: Mapped[uuid.UUID | None] = fk("threads.id", ondelete="SET NULL", nullable=True)
    embedding: Mapped[list | None] = mapped_column(JsonB)  # list of floats
    # "This is not accurate": never used in replies again.
    flagged_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index("ix_facts_user_date", "user_id", "local_date"),
        Index("ix_facts_user_type", "user_id", "type"),
    )


class Thread(Base):
    """A difficulty followed until the person says they have handled it."""

    __tablename__ = "threads"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", index=False)
    title: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(16), default="open")  # open | closed | deleted
    opened_fact_id: Mapped[uuid.UUID | None] = fk(
        "facts.id", ondelete="SET NULL", nullable=True, index=False, use_alter=True
    )
    closed_fact_id: Mapped[uuid.UUID | None] = fk(
        "facts.id", ondelete="SET NULL", nullable=True, index=False, use_alter=True
    )
    opened_on: Mapped[date] = mapped_column(Date)
    closed_on: Mapped[date | None] = mapped_column(Date)
    last_mentioned_on: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (Index("ix_threads_user_status", "user_id", "status"),)


class Pair(Base):
    """A "then -> now" card: an earlier struggle and a later achievement."""

    __tablename__ = "pairs"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    then_fact_id: Mapped[uuid.UUID] = fk("facts.id", index=False)
    now_fact_id: Mapped[uuid.UUID] = fk("facts.id")
    theme: Mapped[str] = mapped_column(String(120))
    # From the first conversation: shown as "from your recollection".
    recalled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    # first_conversation | thread_closed | similarity
    source: Mapped[str] = mapped_column(String(16))
    hidden_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("then_fact_id", "now_fact_id", name="uq_pair_facts"),)


class MonthlySummary(Base):
    __tablename__ = "monthly_summaries"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", index=False)
    month: Mapped[date] = mapped_column(Date)  # the first day of the month
    status: Mapped[str] = mapped_column(String(16))  # done | thin | failed
    # Counted by code: days, conversations, closed threads, pair ids.
    stats: Mapped[dict | None] = mapped_column(JsonB)
    # Written by the model: intro, open_struggle, next_step, with quote placeholders.
    content: Mapped[dict | None] = mapped_column(JsonB)
    viewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (UniqueConstraint("user_id", "month", name="uq_monthly_summary"),)


class Outreach(Base):
    """One message the AI started: what it was about, where it went, what came of it."""

    __tablename__ = "outreach"

    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id")
    # Kept when the day's conversation is deleted: the row is research data.
    conversation_id: Mapped[uuid.UUID | None] = fk(
        "conversations.id", ondelete="SET NULL", nullable=True
    )
    message_id: Mapped[uuid.UUID | None] = fk("messages.id", ondelete="SET NULL", nullable=True)
    # thread | anchor | yesterday | farewell | monthly
    topic: Mapped[str] = mapped_column(String(16))
    thread_id: Mapped[uuid.UUID | None] = fk(
        "threads.id", ondelete="SET NULL", nullable=True, index=False
    )
    channel: Mapped[str] = mapped_column(String(16))  # push | telegram
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    delivered: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    opened_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    replied_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
