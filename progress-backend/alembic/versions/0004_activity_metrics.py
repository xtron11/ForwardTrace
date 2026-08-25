"""Store the countable quantities a person states.

"Learned 10 new words" is the only part of a check-in that can be added up across a week
and shown back as growth. Keeping it as free text loses that.

Revision ID: 0004_activity_metrics
Revises: 0003_detected_language
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0004_activity_metrics"
down_revision = "0003_detected_language"
branch_labels = None
depends_on = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("activities", sa.Column("metrics", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("activities", "metrics")
