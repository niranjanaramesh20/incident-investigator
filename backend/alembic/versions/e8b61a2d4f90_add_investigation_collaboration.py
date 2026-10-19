"""Add investigation assignments, comments, activities, and notifications.

Revision ID: e8b61a2d4f90
Revises: c62e17b4a903
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e8b61a2d4f90"
down_revision: Union[str, Sequence[str], None] = "c62e17b4a903"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _create_table(name: str, extra_columns: list, index_name: str) -> None:
    op.create_table(
        name,
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        *extra_columns,
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(f"ix_{name}_id", name, ["id"])
    op.create_index(index_name, name, ["investigation_id"])


def upgrade() -> None:
    op.add_column("investigations", sa.Column("assignee", sa.String(length=100), nullable=True))
    _create_table(
        "investigation_comments",
        [
            sa.Column("author", sa.String(length=100), nullable=False),
            sa.Column("body", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "ix_investigation_comments_investigation_id",
    )
    _create_table(
        "investigation_activities",
        [
            sa.Column("event_type", sa.String(length=30), nullable=False),
            sa.Column("actor", sa.String(length=100), nullable=True),
            sa.Column("details", sa.Text(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "ix_investigation_activities_investigation_id",
    )
    _create_table(
        "notifications",
        [
            sa.Column("message", sa.String(length=300), nullable=False),
            sa.Column("is_read", sa.Boolean(), server_default=sa.false(), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        ],
        "ix_notifications_investigation_id",
    )


def downgrade() -> None:
    for name in ("notifications", "investigation_activities", "investigation_comments"):
        op.drop_index(f"ix_{name}_investigation_id", table_name=name)
        op.drop_index(f"ix_{name}_id", table_name=name)
        op.drop_table(name)
    op.drop_column("investigations", "assignee")
