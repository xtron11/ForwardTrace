"""Drop v1: check-ins, activities, weekly reports, criteria, tasks.

v2 keeps a person's days as conversations (0014). The v1 tables and the one v1 column
left on users go: `task_mentions`, `tasks`, `activities`, `entries`, `reports`,
`criteria`, `users.tasks_declined_on`. Their rows are deleted with them; the owner
confirmed there are no users whose v1 data must be carried over (brief, «Дополнения»).

The downgrade recreates the schema exactly as it stood after 0013 (empty tables, same
columns, defaults, indexes and constraints), so `alembic downgrade 0014_v2_core` gives
back a database the v1 code could start on. The data itself does not come back.

Revision ID: 0015_drop_v1
Revises: 0014_v2_core
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0015_drop_v1"
down_revision = "0014_v2_core"
branch_labels = None
depends_on = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
UUID = sa.Uuid(as_uuid=True)

# Children before parents.
TABLES = ("task_mentions", "tasks", "activities", "entries", "reports", "criteria")


def upgrade() -> None:
    for table in TABLES:
        op.drop_table(table)
    op.drop_column("users", "tasks_declined_on")


def downgrade() -> None:
    op.add_column("users", sa.Column("tasks_declined_on", sa.Date(), nullable=True))

    # 0001_baseline
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

    # 0001_baseline + 0003 (detected_language), 0007 (reflection), 0008 (intentions),
    # 0012 (costs).
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
        sa.Column("detected_language", sa.String(16), nullable=True),
        sa.Column("reflection", JSONB, nullable=True),
        sa.Column("intentions", JSONB, nullable=True),
        sa.Column("stt_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("llm_cost_usd", sa.Float(), nullable=False, server_default="0"),
        sa.Column("llm_calls", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_input_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_cached_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("llm_output_tokens", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_entries_user_id", "entries", ["user_id"])
    op.create_index("ix_entries_status", "entries", ["status"])
    op.create_index("ix_entries_user_local_date", "entries", ["user_id", "local_date"])

    # 0001_baseline + 0004 (metrics)
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
        sa.Column("metrics", JSONB, nullable=True),
    )
    op.create_index("ix_activities_entry_id", "activities", ["entry_id"])
    op.create_index("ix_activities_user_id", "activities", ["user_id"])
    op.create_index("ix_activities_goal_id", "activities", ["goal_id"])
    op.create_index("ix_activities_user_date", "activities", ["user_id", "local_date"])
    op.create_index("ix_activities_user_category", "activities", ["user_id", "category_key"])

    # 0001_baseline
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

    # 0006_tasks
    op.create_table(
        "tasks",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("goal_id", UUID, sa.ForeignKey("goals.id", ondelete="SET NULL")),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("source", sa.String(8), nullable=False, server_default="user"),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("ends_on", sa.Date(), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="active"),
        sa.Column("closed_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_tasks_user_id", "tasks", ["user_id"])
    op.create_index("ix_tasks_goal_id", "tasks", ["goal_id"])
    op.create_index("ix_tasks_status", "tasks", ["status"])
    op.create_index("ix_tasks_user_status", "tasks", ["user_id", "status"])

    op.create_table(
        "task_mentions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("task_id", UUID, sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("entry_id", UUID, sa.ForeignKey("entries.id", ondelete="CASCADE"), nullable=False),
        sa.Column("local_date", sa.Date(), nullable=False),
        sa.Column("evidence", sa.Text()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("task_id", "entry_id", name="uq_task_mention"),
    )
    op.create_index("ix_task_mentions_task_id", "task_mentions", ["task_id"])
    op.create_index("ix_task_mentions_entry_id", "task_mentions", ["entry_id"])
