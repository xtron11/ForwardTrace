"""v2 core: conversations, messages, facts, threads, pairs, monthly summaries, outreach.

Each day of the person is one conversation. Facts carry verbatim quotes checked against
the message they came from; threads follow a difficulty until it is handled; pairs are
the "then -> now" cards. New fields on users (skill, country, outreach channel,
Telegram, beta Plus, onboarding done) and on goals (finish line, the messages the
motivation and the starting point came from).

The v1 tables stay until 0015; scripts/import_v1.py carries their data over.

Revision ID: 0014_v2_core
Revises: 0013_account_deletion
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0014_v2_core"
down_revision = "0013_account_deletion"
branch_labels = None
depends_on = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")
UUID = sa.Uuid(as_uuid=True)


def _fk(column: str, target: str, ondelete: str, nullable: bool = True) -> sa.Column:
    return sa.Column(column, UUID, sa.ForeignKey(target, ondelete=ondelete), nullable=nullable)


def _created() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now())


def upgrade() -> None:
    # ---- users ----
    op.add_column("users", sa.Column("skill", sa.String(120)))
    op.add_column("users", sa.Column("country", sa.String(2)))
    op.add_column(
        "users",
        sa.Column("outreach_channel", sa.String(16), nullable=False, server_default="push"),
    )
    op.add_column("users", sa.Column("telegram_chat_id", sa.BigInteger))
    op.add_column("users", sa.Column("telegram_link_token", sa.String(64)))
    op.create_unique_constraint(
        "uq_users_telegram_link_token", "users", ["telegram_link_token"]
    )
    op.add_column(
        "users",
        sa.Column("outreach_unanswered", sa.Integer, nullable=False, server_default="0"),
    )
    op.add_column("users", sa.Column("plus_until", sa.Date))
    op.add_column(
        "users",
        sa.Column(
            "first_conversation_done", sa.Boolean, nullable=False, server_default=sa.false()
        ),
    )

    # ---- conversations ----
    op.create_table(
        "conversations",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("started_by", sa.String(8), nullable=False),
        sa.Column("state", JSONB),
        sa.Column("summary", sa.String(200)),
        sa.Column("safety_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("counts_for_limit", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("memory_extracted_at", sa.DateTime(timezone=True)),
        _created(),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.UniqueConstraint("user_id", "local_date", name="uq_conversation_day"),
    )
    op.create_index("ix_conversations_user_id", "conversations", ["user_id"])

    # ---- messages ----
    op.create_table(
        "messages",
        sa.Column("id", UUID, primary_key=True),
        _fk("conversation_id", "conversations.id", "CASCADE", nullable=False),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        sa.Column("role", sa.String(16), nullable=False),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("content_raw", sa.Text, nullable=False, server_default=""),
        sa.Column("content", JSONB, nullable=False),
        sa.Column("words", JSONB),
        sa.Column("audio_path", sa.String(512)),
        sa.Column("audio_mime", sa.String(64)),
        sa.Column("audio_seconds", sa.Float),
        sa.Column("detected_language", sa.String(16)),
        sa.Column("quick_replies", JSONB),
        sa.Column("used_fact_ids", JSONB),
        sa.Column("intent", sa.String(16)),
        sa.Column("safety_level", sa.Integer, nullable=False, server_default="0"),
        sa.Column("rating", sa.String(16)),
        sa.Column("model_name", sa.String(80)),
        sa.Column("llm_ms", sa.Integer),
        sa.Column("stt_ms", sa.Integer),
        sa.Column("cost_usd", sa.Numeric(12, 6)),
        _created(),
    )
    op.create_index("ix_messages_user_id", "messages", ["user_id"])
    op.create_index(
        "ix_messages_conversation_created", "messages", ["conversation_id", "created_at"]
    )

    # ---- threads (before facts; the fact links are added once facts exist) ----
    op.create_table(
        "threads",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("opened_fact_id", UUID),
        sa.Column("closed_fact_id", UUID),
        sa.Column("opened_on", sa.Date, nullable=False),
        sa.Column("closed_on", sa.Date),
        sa.Column("last_mentioned_on", sa.Date),
        _created(),
    )
    op.create_index("ix_threads_user_status", "threads", ["user_id", "status"])

    # ---- facts ----
    op.create_table(
        "facts",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        _fk("message_id", "messages.id", "SET NULL"),
        sa.Column("origin", sa.String(16), nullable=False),
        sa.Column("local_date", sa.Date, nullable=False),
        sa.Column("type", sa.String(16), nullable=False),
        sa.Column("text", sa.String(300), nullable=False),
        sa.Column("quote", sa.Text, nullable=False),
        sa.Column("audio_start_ms", sa.Integer),
        sa.Column("audio_end_ms", sa.Integer),
        _fk("thread_id", "threads.id", "SET NULL"),
        sa.Column("embedding", JSONB),
        sa.Column("flagged_at", sa.DateTime(timezone=True)),
        _created(),
    )
    op.create_index("ix_facts_message_id", "facts", ["message_id"])
    op.create_index("ix_facts_thread_id", "facts", ["thread_id"])
    op.create_index("ix_facts_user_date", "facts", ["user_id", "local_date"])
    op.create_index("ix_facts_user_type", "facts", ["user_id", "type"])
    op.create_foreign_key(
        "fk_threads_opened_fact_id", "threads", "facts",
        ["opened_fact_id"], ["id"], ondelete="SET NULL",
    )
    op.create_foreign_key(
        "fk_threads_closed_fact_id", "threads", "facts",
        ["closed_fact_id"], ["id"], ondelete="SET NULL",
    )

    # ---- pairs ----
    op.create_table(
        "pairs",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        _fk("then_fact_id", "facts.id", "CASCADE", nullable=False),
        _fk("now_fact_id", "facts.id", "CASCADE", nullable=False),
        sa.Column("theme", sa.String(120), nullable=False),
        sa.Column("recalled", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("source", sa.String(16), nullable=False),
        sa.Column("hidden_at", sa.DateTime(timezone=True)),
        _created(),
        sa.UniqueConstraint("then_fact_id", "now_fact_id", name="uq_pair_facts"),
    )
    op.create_index("ix_pairs_user_id", "pairs", ["user_id"])
    op.create_index("ix_pairs_now_fact_id", "pairs", ["now_fact_id"])

    # ---- monthly_summaries ----
    op.create_table(
        "monthly_summaries",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        sa.Column("month", sa.Date, nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("stats", JSONB),
        sa.Column("content", JSONB),
        sa.Column("viewed_at", sa.DateTime(timezone=True)),
        _created(),
        sa.UniqueConstraint("user_id", "month", name="uq_monthly_summary"),
    )

    # ---- outreach ----
    op.create_table(
        "outreach",
        sa.Column("id", UUID, primary_key=True),
        _fk("user_id", "users.id", "CASCADE", nullable=False),
        _fk("conversation_id", "conversations.id", "SET NULL"),
        _fk("message_id", "messages.id", "SET NULL"),
        sa.Column("topic", sa.String(16), nullable=False),
        _fk("thread_id", "threads.id", "SET NULL"),
        sa.Column("channel", sa.String(16), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("delivered", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("opened_at", sa.DateTime(timezone=True)),
        sa.Column("replied_at", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_outreach_user_id", "outreach", ["user_id"])
    op.create_index("ix_outreach_conversation_id", "outreach", ["conversation_id"])
    op.create_index("ix_outreach_message_id", "outreach", ["message_id"])

    # ---- goals: the anchor goal with a finish line ----
    op.add_column(
        "goals",
        sa.Column(
            "why_message_id", UUID,
            sa.ForeignKey("messages.id", ondelete="SET NULL", name="fk_goals_why_message_id"),
        ),
    )
    op.add_column("goals", sa.Column("finish_line", sa.String(300)))
    op.add_column("goals", sa.Column("finish_set_on", sa.Date))
    op.add_column(
        "goals",
        sa.Column(
            "baseline_message_id", UUID,
            sa.ForeignKey(
                "messages.id", ondelete="SET NULL", name="fk_goals_baseline_message_id"
            ),
        ),
    )


def downgrade() -> None:
    op.drop_column("goals", "baseline_message_id")
    op.drop_column("goals", "finish_set_on")
    op.drop_column("goals", "finish_line")
    op.drop_column("goals", "why_message_id")

    op.drop_table("outreach")
    op.drop_table("monthly_summaries")
    op.drop_table("pairs")
    op.drop_constraint("fk_threads_closed_fact_id", "threads", type_="foreignkey")
    op.drop_constraint("fk_threads_opened_fact_id", "threads", type_="foreignkey")
    op.drop_table("facts")
    op.drop_table("threads")
    op.drop_table("messages")
    op.drop_table("conversations")

    op.drop_column("users", "first_conversation_done")
    op.drop_column("users", "plus_until")
    op.drop_column("users", "outreach_unanswered")
    op.drop_constraint("uq_users_telegram_link_token", "users", type_="unique")
    op.drop_column("users", "telegram_link_token")
    op.drop_column("users", "telegram_chat_id")
    op.drop_column("users", "outreach_channel")
    op.drop_column("users", "country")
    op.drop_column("users", "skill")
