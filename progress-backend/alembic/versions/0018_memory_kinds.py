"""Memory of a life, not only a skill: threads get a kind, outreach topics are renamed.

- threads.kind String(16) NOT NULL, server default 'struggle': every existing thread
  was a difficulty, so it stays one; new ones may be 'topic' (an ongoing theme of life).
- outreach.topic: thread -> follow_up, yesterday -> day, general -> day (the new set is
  follow_up | day | anchor | farewell | monthly; 'general' has no counterpart).
- facts.type is an unconstrained string: event and decision need no schema change.

Downgrade: follow_up -> thread, day -> yesterday, the column goes. Rows that were
'general' come back as 'yesterday' - the two were merged on the way up.

Revision ID: 0018_memory_kinds
Revises: 0017_client_msg_id
"""

import sqlalchemy as sa
from alembic import op

revision = "0018_memory_kinds"
down_revision = "0017_client_msg_id"
branch_labels = None
depends_on = None

_outreach = sa.table("outreach", sa.column("topic", sa.String(16)))


def _rename(old: str, new: str) -> None:
    op.execute(_outreach.update().where(_outreach.c.topic == old).values(topic=new))


def upgrade() -> None:
    op.add_column(
        "threads",
        sa.Column("kind", sa.String(16), nullable=False, server_default="struggle"),
    )
    _rename("thread", "follow_up")
    _rename("yesterday", "day")
    _rename("general", "day")


def downgrade() -> None:
    _rename("follow_up", "thread")
    _rename("day", "yesterday")
    op.drop_column("threads", "kind")
