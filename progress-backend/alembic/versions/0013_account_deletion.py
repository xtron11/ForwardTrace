"""Account deletion with a grace period.

Deleting an account marks it rather than erasing it at once: for a while the person
can change their mind through a link in a letter. Once the period runs out, everything
the account owned - rows and recordings - is erased for good.

Revision ID: 0013_account_deletion
Revises: 0012_entry_costs
"""

import sqlalchemy as sa
from alembic import op

revision = "0013_account_deletion"
down_revision = "0012_entry_costs"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True))
    # Signing in to a deleted account sends the restore letter again, and anyone who
    # knows the password can ask for that, so the letters need a gap between them.
    op.add_column(
        "users", sa.Column("restore_sent_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index("ix_users_deleted_at", "users", ["deleted_at"])


def downgrade() -> None:
    op.drop_index("ix_users_deleted_at", table_name="users")
    op.drop_column("users", "restore_sent_at")
    op.drop_column("users", "deleted_at")
