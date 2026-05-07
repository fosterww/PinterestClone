"""add email notifications enabled to users

Revision ID: 6b08e7f5d8df
Revises: 0ea1e15f839e
Create Date: 2026-04-22 19:40:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "6b08e7f5d8df"
down_revision: Union[str, Sequence[str], None] = "0ea1e15f839e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "users",
        sa.Column(
            "email_notifications_enabled",
            sa.Boolean(),
            nullable=False,
            server_default=sa.true(),
        ),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("users", "email_notifications_enabled")
