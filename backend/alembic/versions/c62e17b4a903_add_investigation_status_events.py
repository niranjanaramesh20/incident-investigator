"""Record investigation status changes.

Revision ID: c62e17b4a903
Revises: a41d2c8e9b70
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c62e17b4a903"
down_revision: Union[str, Sequence[str], None] = "a41d2c8e9b70"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "investigation_status_events",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("previous_status", sa.String(length=30), nullable=False),
        sa.Column("new_status", sa.String(length=30), nullable=False),
        sa.Column("changed_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_investigation_status_events_id",
        "investigation_status_events",
        ["id"],
    )
    op.create_index(
        "ix_investigation_status_events_investigation_id",
        "investigation_status_events",
        ["investigation_id"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_investigation_status_events_investigation_id",
        table_name="investigation_status_events",
    )
    op.drop_index(
        "ix_investigation_status_events_id",
        table_name="investigation_status_events",
    )
    op.drop_table("investigation_status_events")
