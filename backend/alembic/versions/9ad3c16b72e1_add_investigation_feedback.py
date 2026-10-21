"""Add per-user investigation feedback."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "9ad3c16b72e1"
down_revision: Union[str, Sequence[str], None] = "f31a9d6c2e84"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "investigation_feedback",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("investigation_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("rating", sa.String(length=20), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["investigation_id"], ["investigations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("investigation_id", "user_id", name="uq_feedback_investigation_user"),
    )
    op.create_index("ix_investigation_feedback_investigation_id", "investigation_feedback", ["investigation_id"])
    op.create_index("ix_investigation_feedback_user_id", "investigation_feedback", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_investigation_feedback_user_id", table_name="investigation_feedback")
    op.drop_index("ix_investigation_feedback_investigation_id", table_name="investigation_feedback")
    op.drop_table("investigation_feedback")
