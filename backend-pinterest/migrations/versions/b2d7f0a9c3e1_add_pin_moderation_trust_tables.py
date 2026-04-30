"""add pin moderation trust tables

Revision ID: b2d7f0a9c3e1
Revises: a1c4d6e8f9b2
Create Date: 2026-04-28 00:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = "b2d7f0a9c3e1"
down_revision: Union[str, Sequence[str], None] = "a1c4d6e8f9b2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


pin_processing_state_create = postgresql.ENUM(
    "uploaded",
    "tagged",
    "indexed",
    "failed",
    name="pinprocessingstate",
)
pin_moderation_status_create = postgresql.ENUM(
    "pending",
    "approved",
    "hidden",
    "failed",
    name="pinmoderationstatus",
)
pin_edit_source_create = postgresql.ENUM("user", "system", name="pineditsource")

pin_processing_state = postgresql.ENUM(
    "uploaded",
    "tagged",
    "indexed",
    "failed",
    name="pinprocessingstate",
    create_type=False,
)
pin_moderation_status = postgresql.ENUM(
    "pending",
    "approved",
    "hidden",
    "failed",
    name="pinmoderationstatus",
    create_type=False,
)
pin_edit_source = postgresql.ENUM(
    "user",
    "system",
    name="pineditsource",
    create_type=False,
)


def upgrade() -> None:
    """Upgrade schema."""
    bind = op.get_bind()
    pin_processing_state_create.create(bind, checkfirst=True)
    pin_moderation_status_create.create(bind, checkfirst=True)
    pin_edit_source_create.create(bind, checkfirst=True)

    op.add_column(
        "pins",
        sa.Column(
            "processing_state",
            pin_processing_state,
            nullable=False,
            server_default="uploaded",
        ),
    )
    op.add_column(
        "pins",
        sa.Column(
            "moderation_status",
            pin_moderation_status,
            nullable=False,
            server_default="pending",
        ),
    )
    op.add_column(
        "pins",
        sa.Column("tagging_attempts", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "pins",
        sa.Column(
            "indexing_attempts", sa.Integer(), nullable=False, server_default="0"
        ),
    )
    op.add_column("pins", sa.Column("last_processing_error", sa.String(length=1000)))
    op.add_column(
        "pins", sa.Column("tagged_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "pins", sa.Column("indexed_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column("pins", sa.Column("image_width", sa.Integer(), nullable=True))
    op.add_column("pins", sa.Column("image_height", sa.Integer(), nullable=True))
    op.add_column("pins", sa.Column("dominant_colors", sa.JSON(), nullable=True))
    op.add_column(
        "pins", sa.Column("file_hash_sha256", sa.String(length=64), nullable=True)
    )
    op.add_column(
        "pins",
        sa.Column(
            "is_duplicate", sa.Boolean(), nullable=False, server_default=sa.false()
        ),
    )
    op.add_column("pins", sa.Column("duplicate_of_pin_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        op.f("fk_pins_duplicate_of_pin_id_pins"),
        "pins",
        "pins",
        ["duplicate_of_pin_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.execute(
        "UPDATE pins SET processing_state = 'indexed', moderation_status = 'approved'"
    )

    op.create_index(
        op.f("ix_pins_processing_state"), "pins", ["processing_state"], unique=False
    )
    op.create_index(
        op.f("ix_pins_moderation_status"), "pins", ["moderation_status"], unique=False
    )
    op.create_index(
        op.f("ix_pins_file_hash_sha256"), "pins", ["file_hash_sha256"], unique=False
    )
    op.create_index(
        op.f("ix_pins_duplicate_of_pin_id"),
        "pins",
        ["duplicate_of_pin_id"],
        unique=False,
    )

    op.create_table(
        "pin_edit_history",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("pin_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("source", pin_edit_source, nullable=False, server_default="system"),
        sa.Column("changed_fields", sa.JSON(), nullable=True),
        sa.Column("before", sa.JSON(), nullable=True),
        sa.Column("after", sa.JSON(), nullable=True),
        sa.Column("reason", sa.String(length=255), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(), server_default=sa.text("now()"), nullable=False
        ),
        sa.ForeignKeyConstraint(
            ["actor_user_id"],
            ["users.id"],
            name=op.f("fk_pin_edit_history_actor_user_id_users"),
            ondelete="SET NULL",
        ),
        sa.ForeignKeyConstraint(
            ["pin_id"],
            ["pins.id"],
            name=op.f("fk_pin_edit_history_pin_id_pins"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_pin_edit_history")),
    )
    op.create_index(
        op.f("ix_pin_edit_history_pin_id"),
        "pin_edit_history",
        ["pin_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pin_edit_history_actor_user_id"),
        "pin_edit_history",
        ["actor_user_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_pin_edit_history_created_at"),
        "pin_edit_history",
        ["created_at"],
        unique=False,
    )


def downgrade() -> None:
    """Downgrade schema."""
    bind = op.get_bind()

    op.drop_index(op.f("ix_pin_edit_history_created_at"), table_name="pin_edit_history")
    op.drop_index(
        op.f("ix_pin_edit_history_actor_user_id"), table_name="pin_edit_history"
    )
    op.drop_index(op.f("ix_pin_edit_history_pin_id"), table_name="pin_edit_history")
    op.drop_table("pin_edit_history")

    op.drop_index(op.f("ix_pins_duplicate_of_pin_id"), table_name="pins")
    op.drop_index(op.f("ix_pins_file_hash_sha256"), table_name="pins")
    op.drop_index(op.f("ix_pins_moderation_status"), table_name="pins")
    op.drop_index(op.f("ix_pins_processing_state"), table_name="pins")
    op.drop_constraint(
        op.f("fk_pins_duplicate_of_pin_id_pins"), "pins", type_="foreignkey"
    )
    op.drop_column("pins", "duplicate_of_pin_id")
    op.drop_column("pins", "is_duplicate")
    op.drop_column("pins", "file_hash_sha256")
    op.drop_column("pins", "dominant_colors")
    op.drop_column("pins", "image_height")
    op.drop_column("pins", "image_width")
    op.drop_column("pins", "indexed_at")
    op.drop_column("pins", "tagged_at")
    op.drop_column("pins", "last_processing_error")
    op.drop_column("pins", "indexing_attempts")
    op.drop_column("pins", "tagging_attempts")
    op.drop_column("pins", "moderation_status")
    op.drop_column("pins", "processing_state")

    pin_edit_source_create.drop(bind, checkfirst=True)
    pin_moderation_status_create.drop(bind, checkfirst=True)
    pin_processing_state_create.drop(bind, checkfirst=True)
