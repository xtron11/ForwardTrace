"""Intentions the person stated themselves.

Offered back as a task rather than replaced by something a model thought up: it does
not know whether tomorrow holds university, a deadline, or an errand.

Revision ID: 0008_intentions
Revises: 0007_reflection
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision = "0008_intentions"
down_revision = "0007_reflection"
branch_labels = None
depends_on = None

JSONB = sa.JSON().with_variant(postgresql.JSONB(), "postgresql")


def upgrade() -> None:
    op.add_column("entries", sa.Column("intentions", JSONB, nullable=True))


def downgrade() -> None:
    op.drop_column("entries", "intentions")
