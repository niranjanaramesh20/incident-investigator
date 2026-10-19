"""Store the complete investigation response.

Revision ID: 7c3a9d1e5f20
Revises: 31ebce855e97
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7c3a9d1e5f20"
down_revision: Union[str, Sequence[str], None] = "31ebce855e97"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("investigations", sa.Column("report", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("investigations", "report")
