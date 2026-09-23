"""What each check-in cost in speech-to-text and model calls.

Summed per entry across every provider call made for it, retries included. Tokens are
kept next to dollars so a wrong configured price can be recomputed later.

Revision ID: 0012_entry_costs
Revises: 0011_verification_sent_at
"""

import sqlalchemy as sa
from alembic import op

revision = "0012_entry_costs"
down_revision = "0011_verification_sent_at"
branch_labels = None
depends_on = None

FLOATS = ("stt_cost_usd", "llm_cost_usd")
INTS = ("llm_calls", "llm_input_tokens", "llm_cached_tokens", "llm_output_tokens")


def upgrade() -> None:
    for name in FLOATS:
        op.add_column(
            "entries", sa.Column(name, sa.Float(), nullable=False, server_default="0")
        )
    for name in INTS:
        op.add_column(
            "entries", sa.Column(name, sa.Integer(), nullable=False, server_default="0")
        )


def downgrade() -> None:
    for name in (*FLOATS, *INTS):
        op.drop_column("entries", name)
