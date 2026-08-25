"""Push subscriptions and reminder preferences.

Revision ID: 0005_push_reminders
Revises: 0004_activity_metrics
"""

import sqlalchemy as sa
from alembic import op

revision = "0005_push_reminders"
down_revision = "0004_activity_metrics"
branch_labels = None
depends_on = None

UUID = sa.Uuid(as_uuid=True)


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("reminder_hour", sa.Integer(), nullable=False, server_default="20"),
    )
    op.add_column(
        "users",
        sa.Column("reminders_on", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.add_column("users", sa.Column("last_reminded_on", sa.Date(), nullable=True))

    op.create_table(
        "push_subscriptions",
        sa.Column("id", UUID, primary_key=True),
        sa.Column("user_id", UUID, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        # Unique: the same browser re-subscribing returns the same endpoint, and a
        # duplicate row would mean the person gets every reminder twice.
        sa.Column("endpoint", sa.Text(), nullable=False, unique=True),
        sa.Column("p256dh", sa.String(255), nullable=False),
        sa.Column("auth", sa.String(255), nullable=False),
        sa.Column("user_agent", sa.String(255)),
        sa.Column("failure_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_success_at", sa.DateTime(timezone=True)),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.create_index("ix_push_subscriptions_user_id", "push_subscriptions", ["user_id"])


def downgrade() -> None:
    op.drop_table("push_subscriptions")
    op.drop_column("users", "last_reminded_on")
    op.drop_column("users", "reminders_on")
    op.drop_column("users", "reminder_hour")
