"""Track evaluation progress and reviewed dataset snapshots."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "c4a71d9f3e26"
down_revision: Union[str, Sequence[str], None] = "b82e6a10c4f3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.add_column(sa.Column("status", sa.String(length=20), server_default="queued", nullable=False))
        batch_op.add_column(sa.Column("completed_cases", sa.Integer(), server_default="0", nullable=False))
        batch_op.add_column(sa.Column("current_case", sa.String(length=200), nullable=True))
        batch_op.add_column(sa.Column("error", sa.String(length=2000), nullable=True))
    op.execute("UPDATE evaluation_runs SET status = 'completed', completed_cases = case_count")

    op.create_table(
        "evaluation_case_sets",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("cases", sa.JSON(), nullable=False),
        sa.Column("change_summary", sa.String(length=500), nullable=False),
        sa.Column("created_by", sa.String(length=254), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("version"),
    )
    op.create_index("ix_evaluation_case_sets_created_at", "evaluation_case_sets", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_case_sets_created_at", table_name="evaluation_case_sets")
    op.drop_table("evaluation_case_sets")
    with op.batch_alter_table("evaluation_runs") as batch_op:
        batch_op.drop_column("error")
        batch_op.drop_column("current_case")
        batch_op.drop_column("completed_cases")
        batch_op.drop_column("status")
