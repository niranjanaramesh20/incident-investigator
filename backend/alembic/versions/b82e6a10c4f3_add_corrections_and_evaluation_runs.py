"""Store analyst report corrections and evaluation run history."""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "b82e6a10c4f3"
down_revision: Union[str, Sequence[str], None] = "9ad3c16b72e1"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("investigation_feedback") as batch_op:
        batch_op.add_column(sa.Column("correction_target", sa.String(length=500), nullable=True))
        batch_op.add_column(sa.Column("corrected_cause", sa.Text(), nullable=True))

    op.create_table(
        "evaluation_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("dataset_version", sa.Integer(), nullable=False),
        sa.Column("initiated_by", sa.String(length=254), nullable=False),
        sa.Column("case_count", sa.Integer(), nullable=False),
        sa.Column("passed_count", sa.Integer(), nullable=False),
        sa.Column("pass_rate", sa.Float(), nullable=False),
        sa.Column("mean_confidence", sa.Float(), nullable=False),
        sa.Column("validation_rate", sa.Float(), nullable=False),
        sa.Column("citation_rate", sa.Float(), nullable=False),
        sa.Column("results", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_evaluation_runs_created_at", "evaluation_runs", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_evaluation_runs_created_at", table_name="evaluation_runs")
    op.drop_table("evaluation_runs")
    with op.batch_alter_table("investigation_feedback") as batch_op:
        batch_op.drop_column("corrected_cause")
        batch_op.drop_column("correction_target")
