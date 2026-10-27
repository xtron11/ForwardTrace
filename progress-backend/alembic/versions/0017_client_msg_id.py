"""messages.client_msg_id: one message per id the client sent.

A double click or "Try again" after a dropped connection resends the same message with
the same id; the unique index keeps one row. NULL (Telegram, older clients) never
conflicts.

Revision ID: 0017_client_msg_id
Revises: 0016_pair_source_length
"""

import sqlalchemy as sa
from alembic import op

revision = "0017_client_msg_id"
down_revision = "0016_pair_source_length"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("messages", sa.Column("client_msg_id", sa.String(64), nullable=True))
    op.create_unique_constraint(
        "uq_messages_user_client_msg", "messages", ["user_id", "client_msg_id"]
    )


def downgrade() -> None:
    op.drop_constraint("uq_messages_user_client_msg", "messages", type_="unique")
    op.drop_column("messages", "client_msg_id")
