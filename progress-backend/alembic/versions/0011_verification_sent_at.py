"""When the last verification letter went out.

Resending works without a session - there is none until the address is confirmed - so
the interval between letters has to be recorded somewhere.

Revision ID: 0011_verification_sent_at
Revises: 0010_email_verified
"""

import sqlalchemy as sa
from alembic import op

revision = "0011_verification_sent_at"
down_revision = "0010_email_verified"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users", sa.Column("verification_sent_at", sa.DateTime(timezone=True), nullable=True)
    )


def downgrade() -> None:
    op.drop_column("users", "verification_sent_at")
