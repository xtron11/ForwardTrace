"""Tasks and their mentions.

Note what is absent: no completed flag, no failed state. A task is compared against
what the person said and they judge it themselves, so there is nothing for the schema
to record beyond the intention and the days it was touched.

Revision ID: 0006_tasks
Revises: 0005_push_reminders
"""

import sqlalchemy as sa
from alembic import op

revision = "0006_tasks"
down_revision = "0005_push_reminders"
branch_labels = None
depends_on = None

UUID = sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.add_column("users", sa.Column("tasks_declined_on", sa.Date(), nullable=True))

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


def downgrade() -> None:
    op.drop_table("task_mentions")
    op.drop_table("tasks")
    op.drop_column("users", "tasks_declined_on")
