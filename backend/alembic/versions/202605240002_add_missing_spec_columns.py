"""Add missing spec columns.

Revision ID: 202605240002
Revises: 202605240001
Create Date: 2026-05-24
"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "202605240002"
down_revision: str | None = "202605240001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "element_permissions",
        sa.Column("can_delete", sa.Boolean(), nullable=False, server_default=sa.text("false")),
    )
    op.add_column(
        "review_comments",
        sa.Column("resolved_by", postgresql.UUID(as_uuid=True), nullable=True),
    )
    op.create_foreign_key(
        "fk_review_comments_resolved_by_users",
        "review_comments",
        "users",
        ["resolved_by"],
        ["id"],
    )
    op.add_column(
        "canvas_analytics",
        sa.Column("time_on_canvas_s", sa.Integer(), nullable=False, server_default=sa.text("0")),
    )


def downgrade() -> None:
    op.drop_column("canvas_analytics", "time_on_canvas_s")
    op.drop_constraint("fk_review_comments_resolved_by_users", "review_comments", type_="foreignkey")
    op.drop_column("review_comments", "resolved_by")
    op.drop_column("element_permissions", "can_delete")
