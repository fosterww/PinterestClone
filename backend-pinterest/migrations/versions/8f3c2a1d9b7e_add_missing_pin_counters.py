"""add missing pin counters

Revision ID: 8f3c2a1d9b7e
Revises: 6b08e7f5d8df
Create Date: 2026-04-23 12:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "8f3c2a1d9b7e"
down_revision: Union[str, Sequence[str], None] = "6b08e7f5d8df"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column(
        "pins",
        sa.Column("views_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pins",
        sa.Column("saves_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("pins", "saves_count")
    op.drop_column("pins", "views_count")
