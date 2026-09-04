"""Keep the recording of why the goal matters.

Transcribing it and throwing the audio away loses the part that carries: hearing
yourself from the day you decided is not the same as reading it.

Revision ID: 0009_why_audio
Revises: 0008_intentions
"""

import sqlalchemy as sa
from alembic import op

revision = "0009_why_audio"
down_revision = "0008_intentions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("goals", sa.Column("why_audio_path", sa.String(512), nullable=True))
    op.add_column("goals", sa.Column("why_audio_mime", sa.String(64), nullable=True))
    op.add_column("goals", sa.Column("why_audio_seconds", sa.Float(), nullable=True))


def downgrade() -> None:
    op.drop_column("goals", "why_audio_seconds")
    op.drop_column("goals", "why_audio_mime")
    op.drop_column("goals", "why_audio_path")
