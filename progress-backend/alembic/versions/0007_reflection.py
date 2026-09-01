"""The answer shown straight after a check-in.

Stored per entry rather than regenerated on view: the person should see the same words
when they come back, and a reflection that rewrites itself is not a record of anything.

Revision ID: 0007_reflection
Revises: 0006_tasks
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0007_reflection"
down_revision = "0006_tasks"
branch_labels = None
depends_on = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("entries", sa.Column("reflection", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "reflection")
