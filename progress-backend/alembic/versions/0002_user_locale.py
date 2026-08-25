"""Add users.locale.

The column the app is currently failing on. Existing rows default to English, which is
what they were implicitly getting anyway.

Revision ID: 0002_user_locale
Revises: 0001_baseline
"""

import sqlalchemy as sa
from alembic import op

revision = "0002_user_locale"
down_revision = "0001_baseline"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("locale", sa.String(8), nullable=False, server_default="en"),
    )


def downgrade() -> None:
    op.drop_column("users", "locale")
