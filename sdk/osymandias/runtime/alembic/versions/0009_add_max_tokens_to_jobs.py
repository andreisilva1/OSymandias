"""add max_tokens to jobs

Revision ID: 0009
Revises: 0008
Create Date: 2026-06-20
"""
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE jobs ADD COLUMN IF NOT EXISTS max_tokens INTEGER"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE jobs DROP COLUMN IF EXISTS max_tokens"
    )
