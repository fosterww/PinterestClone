"""add ai operations table

Revision ID: c4e9b8a7d6f1
Revises: b2d7f0a9c3e1
Create Date: 2026-05-04 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = "c4e9b8a7d6f1"
down_revision: Union[str, Sequence[str], None] = "b2d7f0a9c3e1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


ai_provider_create = postgresql.ENUM(
    "openai",
    "gemini",
    "clarifai",
    name="aiprovider",
)
ai_operation_type_create = postgresql.ENUM(
    "image_generation",
    "tag_generation",
    "description_generation",
    "image_indexing",
    "visual_search",
    name="aioperationtype",
)
ai_status_create = postgresql.ENUM(
    "pending",
    "in_progress",
    "completed",
    "failed",
    name="aistatus",
)

ai_provider = postgresql.ENUM(
    "openai",
    "gemini",
    "clarifai",
    name="aiprovider",
    create_type=False,
)
ai_operation_type = postgresql.ENUM(
    "image_generation",
    "tag_generation",
    "description_generation",
    "image_indexing",
    "visual_search",
    name="aioperationtype",
    create_type=False,
)
ai_status = postgresql.ENUM(
    "pending",
    "in_progress",
    "completed",
    "failed",
    name="aistatus",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    ai_provider_create.create(bind, checkfirst=True)
    ai_operation_type_create.create(bind, checkfirst=True)
    ai_status_create.create(bind, checkfirst=True)

    op.create_table(
        "ai_operations",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=True),
        sa.Column("related_pin_id", sa.Uuid(), nullable=True),
        sa.Column("generated_pin_id", sa.Uuid(), nullable=True),
        sa.Column("provider", ai_provider, nullable=False),
        sa.Column("model", sa.String(length=100), nullable=False),
        sa.Column("operation_type", ai_operation_type, nullable=False),
        sa.Column("prompt_version", sa.String(length=50), nullable=True),
        sa.Column("input_parameters", sa.JSON(), nullable=True),
        sa.Column("status", ai_status, server_default="pending", nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("error_message", sa.String(length=1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(
            ["generated_pin_id"],
            ["generated_pins.id"],
            name=op.f("fk_ai_operations_generated_pin_id_generated_pins"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["related_pin_id"],
            ["pins.id"],
            name=op.f("fk_ai_operations_related_pin_id_pins"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_ai_operations_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_ai_operations")),
    )
    op.create_index(
        op.f("ix_ai_operations_generated_pin_id"),
        "ai_operations",
        ["generated_pin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_operations_operation_type"),
        "ai_operations",
        ["operation_type"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_operations_provider"),
        "ai_operations",
        ["provider"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_operations_related_pin_id"),
        "ai_operations",
        ["related_pin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_operations_status"),
        "ai_operations",
        ["status"],
        unique=False,
    )
    op.create_index(
        op.f("ix_ai_operations_user_id"),
        "ai_operations",
        ["user_id"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_ai_operations_user_id"), table_name="ai_operations")
    op.drop_index(op.f("ix_ai_operations_status"), table_name="ai_operations")
    op.drop_index(op.f("ix_ai_operations_related_pin_id"), table_name="ai_operations")
    op.drop_index(op.f("ix_ai_operations_provider"), table_name="ai_operations")
    op.drop_index(op.f("ix_ai_operations_operation_type"), table_name="ai_operations")
    op.drop_index(op.f("ix_ai_operations_generated_pin_id"), table_name="ai_operations")
    op.drop_table("ai_operations")

    ai_status_create.drop(bind, checkfirst=True)
    ai_operation_type_create.drop(bind, checkfirst=True)
    ai_provider_create.drop(bind, checkfirst=True)
