"""Record the language the provider detected in each recording.

A mismatch between this and the user's profile locale is the cheapest signal that one
of the two is wrong - and getting it wrong produces fluent nonsense rather than an
error, so it is worth being able to see.

Revision ID: 0003_detected_language
Revises: 0002_user_locale
"""

import sqlalchemy as sa
from alembic import op

revision = "0003_detected_language"
down_revision = "0002_user_locale"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("entries", sa.Column("detected_language", sa.String(16), nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "detected_language")
