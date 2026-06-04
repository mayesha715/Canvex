"""add active session unique index

Revision ID: 202606040001
Revises: 202605240002
Create Date: 2026-06-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "202606040001"
down_revision = "202605240002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        WITH ranked AS (
            SELECT
                id,
                ROW_NUMBER() OVER (
                    PARTITION BY page_id
                    ORDER BY started_at DESC, id DESC
                ) AS row_number
            FROM sessions
            WHERE ended_at IS NULL
        )
        UPDATE sessions
        SET ended_at = NOW()
        WHERE id IN (
            SELECT id
            FROM ranked
            WHERE row_number > 1
        )
        """
    )
    op.create_index(
        "uq_sessions_active_page",
        "sessions",
        ["page_id"],
        unique=True,
        postgresql_where=sa.text("ended_at IS NULL"),
    )


def downgrade() -> None:
    op.drop_index("uq_sessions_active_page", table_name="sessions")
