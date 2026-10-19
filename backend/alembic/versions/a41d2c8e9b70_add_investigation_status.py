"""Add status tracking to saved investigations.

Revision ID: a41d2c8e9b70
Revises: 7c3a9d1e5f20
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a41d2c8e9b70"
down_revision: Union[str, Sequence[str], None] = "7c3a9d1e5f20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "investigations",
        sa.Column("status", sa.String(length=30), server_default="open", nullable=False),
    )


def downgrade() -> None:
    op.drop_column("investigations", "status")
