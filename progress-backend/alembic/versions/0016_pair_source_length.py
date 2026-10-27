"""Widen pairs.source to 32: "first_conversation" is 18 characters.

0014 made the column VARCHAR(16), so on Postgres the first conversation could not save
its "then -> now" pairs and the reply failed. SQLite ignores the length, which is why
the tests did not notice.

Revision ID: 0016_pair_source_length
Revises: 0015_drop_v1
"""

import sqlalchemy as sa
from alembic import op

revision = "0016_pair_source_length"
down_revision = "0015_drop_v1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column(
        "pairs", "source", type_=sa.String(32), existing_type=sa.String(16), existing_nullable=False
    )


def downgrade() -> None:
    op.alter_column(
        "pairs", "source", type_=sa.String(16), existing_type=sa.String(32), existing_nullable=False
    )
