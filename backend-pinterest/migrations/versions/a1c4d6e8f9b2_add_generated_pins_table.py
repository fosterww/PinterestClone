"""add generated pins table

Revision ID: a1c4d6e8f9b2
Revises: 8f3c2a1d9b7e
Create Date: 2026-04-23 20:30:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a1c4d6e8f9b2"
down_revision: Union[str, Sequence[str], None] = "8f3c2a1d9b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "generated_pins",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("image_url", sa.String(length=255), nullable=False),
        sa.Column("prompt", sa.String(length=1000), nullable=False),
        sa.Column("style", sa.String(length=100), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["user_id"], ["users.id"], name=op.f("fk_generated_pins_user_id_users")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_generated_pins")),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("generated_pins")
