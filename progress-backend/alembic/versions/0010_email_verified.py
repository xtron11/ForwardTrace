"""Confirmed email addresses.

Existing accounts are marked verified: they were invited by hand, and locking them out
of a product they already use to enforce a rule introduced after the fact would be
punishing the wrong people.

Revision ID: 0010_email_verified
Revises: 0009_why_audio
"""

import sqlalchemy as sa
from alembic import op

revision = "0010_email_verified"
down_revision = "0009_why_audio"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("email_verified", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    op.execute("UPDATE users SET email_verified = true")


def downgrade() -> None:
    op.drop_column("users", "email_verified")
