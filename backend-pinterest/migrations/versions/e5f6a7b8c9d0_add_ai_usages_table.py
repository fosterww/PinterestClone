"""add ai usages table

Revision ID: e5f6a7b8c9d0
Revises: d9a4b7c2e6f3
Create Date: 2026-05-11 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "e5f6a7b8c9d0"
down_revision: Union[str, Sequence[str], None] = "d9a4b7c2e6f3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ai_operation_type = postgresql.ENUM(
    "image_generation",
    "tag_generation",
    "retries",
    "description_generation",
    "image_indexing",
    "visual_search",
    name="aioperationtype",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("ALTER TYPE aioperationtype ADD VALUE IF NOT EXISTS 'retries'")
    op.create_table(
        "ai_usages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("operation_id", sa.Uuid(), nullable=True),
        sa.Column("action_type", ai_operation_type, nullable=False),
        sa.Column("units_used", sa.Integer(), server_default="1", nullable=False),
        sa.Column("tokens_used", sa.Integer(), nullable=True),
        sa.Column(
            "cost_usd",
            sa.Numeric(precision=10, scale=6),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["operation_id"],
            ["ai_operations.id"],
            name=op.f("fk_ai_usages_operation_id_ai_operations"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_usages_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_usages")),
    )
    op.create_index(
        op.f("ix_ai_usages_action_type"),
        "ai_usages",
        ["action_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_usages_created_at"),
        "ai_usages",
        ["created_at"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_usages_operation_id"),
        "ai_usages",
        ["operation_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_usages_user_id"),
        "ai_usages",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f("ix_ai_usages_user_id"), table_name="ai_usages")
    op.drop_index(op.f("ix_ai_usages_operation_id"), table_name="ai_usages")
    op.drop_index(op.f("ix_ai_usages_created_at"), table_name="ai_usages")
    op.drop_index(op.f("ix_ai_usages_action_type"), table_name="ai_usages")
    op.drop_table("ai_usages")
