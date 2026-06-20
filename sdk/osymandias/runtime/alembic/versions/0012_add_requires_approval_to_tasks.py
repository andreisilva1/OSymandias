"""add requires_approval to tasks

Revision ID: 0012
Revises: 0011
Create Date: 2026-06-20
"""
from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS "
        "requires_approval BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE tasks DROP COLUMN IF EXISTS requires_approval"
    )
