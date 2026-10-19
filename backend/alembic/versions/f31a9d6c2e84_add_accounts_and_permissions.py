"""Add user accounts and ownership references.

Revision ID: f31a9d6c2e84
Revises: e8b61a2d4f90
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f31a9d6c2e84"
down_revision: Union[str, Sequence[str], None] = "e8b61a2d4f90"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=300), nullable=False),
        sa.Column("role", sa.String(length=20), server_default="viewer", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_index("ix_users_id", "users", ["id"])
    op.create_index("ix_users_email", "users", ["email"])

    with op.batch_alter_table("investigation_status_events") as batch_op:
        batch_op.add_column(sa.Column("changed_by", sa.String(length=254), nullable=True))

    with op.batch_alter_table("investigations") as batch_op:
        batch_op.alter_column("assignee", existing_type=sa.String(length=100), type_=sa.String(length=254))

    with op.batch_alter_table("investigations") as batch_op:
        batch_op.add_column(sa.Column("assignee_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_investigations_assignee_user_id", ["assignee_user_id"])
        batch_op.create_foreign_key(
            "fk_investigations_assignee_user_id_users", "users", ["assignee_user_id"], ["id"], ondelete="SET NULL"
        )

    for table in ("investigation_comments", "investigation_activities"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.add_column(sa.Column("user_id", sa.Integer(), nullable=True))
            batch_op.create_index(f"ix_{table}_user_id", ["user_id"])
            batch_op.create_foreign_key(
                f"fk_{table}_user_id_users", "users", ["user_id"], ["id"], ondelete="SET NULL"
            )

    with op.batch_alter_table("notifications") as batch_op:
        batch_op.add_column(sa.Column("recipient_user_id", sa.Integer(), nullable=True))
        batch_op.create_index("ix_notifications_recipient_user_id", ["recipient_user_id"])
        batch_op.create_foreign_key(
            "fk_notifications_recipient_user_id_users", "users", ["recipient_user_id"], ["id"], ondelete="CASCADE"
        )


def downgrade() -> None:
    with op.batch_alter_table("notifications") as batch_op:
        batch_op.drop_constraint("fk_notifications_recipient_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_notifications_recipient_user_id")
        batch_op.drop_column("recipient_user_id")
    for table in ("investigation_activities", "investigation_comments"):
        with op.batch_alter_table(table) as batch_op:
            batch_op.drop_constraint(f"fk_{table}_user_id_users", type_="foreignkey")
            batch_op.drop_index(f"ix_{table}_user_id")
            batch_op.drop_column("user_id")
    with op.batch_alter_table("investigations") as batch_op:
        batch_op.drop_constraint("fk_investigations_assignee_user_id_users", type_="foreignkey")
        batch_op.drop_index("ix_investigations_assignee_user_id")
        batch_op.drop_column("assignee_user_id")
        batch_op.alter_column("assignee", existing_type=sa.String(length=254), type_=sa.String(length=100))
    with op.batch_alter_table("investigation_status_events") as batch_op:
        batch_op.drop_column("changed_by")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_index("ix_users_id", table_name="users")
    op.drop_table("users")
