"""Baseline schema.

This describes the database as it stood before the locale column was added, which is
exactly what an existing installation already has. That is deliberate: an existing
database can be marked as already at this revision (`alembic stamp 0001_baseline`)
without running anything, and then upgraded normally from here.

Revision ID: 0001_baseline
Revises:
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0001_baseline"
down_revision = None
branch_labels = None
depends_on = None

# JSONB on Postgres, plain JSON elsewhere, so the suite can run on SQLite.
JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
UUID = sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(120)),
        sa.Column("timezone", sa.String(64), nullable=False, server_default="UTC"),
        sa.Column("token_version", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("intake", JSONB),
        sa.Column("cohort", sa.String(64)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)

    op.create_table(
        "goals",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("why_text", sa.Text),
        sa.Column("why_source", sa.String(16), nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("started_on", sa.Date),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_goals_user_id", "goals", ["user_id"])

    op.create_table(
        "criteria",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="CASCADE"), nullable=False),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("source", sa.String(8), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_criteria_goal_id", "criteria", ["goal_id"])

    op.create_table(
        "entries",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="SET NULL")),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("audio_path", sa.String(512)),
        sa.Column("audio_mime", sa.String(64)),
        sa.Column("audio_seconds", sa.Float),
        sa.Column("raw_transcript", sa.Text),
        sa.Column("stt_transcript", sa.Text),
        sa.Column("transcript_edited", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("mood", sa.String(32)),
        sa.Column("wins", JSONB),
        sa.Column("friction", JSONB),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("error", sa.Text),
        sa.Column("stt_ms", sa.Integer),
        sa.Column("llm_ms", sa.Integer),
        sa.Column("dropped_facts", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_entries_user_id", "entries", ["user_id"])
    op.create_index("ix_entries_status", "entries", ["status"])
    op.create_index("ix_entries_user_local_date", "entries", ["user_id", "local_date"])

    op.create_table(
        "activities",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("entry_id", UUID, sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="SET NULL")),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("category_key", sa.String(80), nullable=False),
        sa.Column("minutes", sa.Integer),
        sa.Column("minutes_explicit", sa.Boolean, nullable=False),
        sa.Column("details", JSONB),
        sa.Column("quote", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_activities_entry_id", "activities", ["entry_id"])
    op.create_index("ix_activities_user_id", "activities", ["user_id"])
    op.create_index("ix_activities_goal_id", "activities", ["goal_id"])
    op.create_index("ix_activities_user_date", "activities", ["user_id", "local_date"])
    op.create_index("ix_activities_user_category", "activities", ["user_id", "category_key"])

    op.create_table(
        "reports",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="SET NULL")),
        sa.Column("period_start", sa.Date, nullable=False),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stats", JSONB),
        sa.Column("content", JSONB),
        sa.Column("generated_by", sa.String(16), nullable=False),
        sa.Column("model_name", sa.String(80)),
        sa.Column("generation_ms", sa.Integer),
        sa.Column("error", sa.Text),
        sa.Column("feedback_rating", sa.Integer),
        sa.Column("feedback_text", sa.Text),
        sa.Column("feedback_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "goal_id", "period_start", name="uq_report_period"),
    )
    op.create_index("ix_reports_user_id", "reports", ["user_id"])

    op.create_table(
        "events",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE")),
        sa.Column("type", sa.String(64), nullable=False),
        sa.Column("payload", JSONB),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_events_user_id", "events", ["user_id"])
    op.create_index("ix_events_type", "events", ["type"])


def downgrade() -> None:
    for table in ("events", "reports", "activities", "entries", "criteria", "goals", "users"):
        op.drop_table(table)
