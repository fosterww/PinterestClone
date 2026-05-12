"""add generated pin moderation

Revision ID: d9a4b7c2e6f3
Revises: c4e9b8a7d6f1
Create Date: 2026-05-09 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "d9a4b7c2e6f3"
down_revision: Union[str, Sequence[str], None] = "c4e9b8a7d6f1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


generated_pin_moderation_status_create = postgresql.ENUM(
    "pending",
    "approved",
    "hidden",
    "failed",
    name="generatedpinmoderationstatus",
)
generated_pin_moderation_status = postgresql.ENUM(
    "pending",
    "approved",
    "hidden",
    "failed",
    name="generatedpinmoderationstatus",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    generated_pin_moderation_status_create.create(bind, checkfirst=True)
    op.add_column(
        "generated_pins",
        sa.Column(
            "moderation_status",
            generated_pin_moderation_status,
            server_default="approved",
            nullable=False,
        ),
    )
    op.add_column(
        "generated_pins",
        sa.Column("moderation_reason", sa.String(length=500), nullable=True),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column("generated_pins", "moderation_reason")
    op.drop_column("generated_pins", "moderation_status")
    bind = op.get_bind()
    generated_pin_moderation_status_create.drop(bind, checkfirst=True)
