"""add requires_approval to agent_definitions

Revision ID: 0013
Revises: 0012
Create Date: 2026-06-20
"""
from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS "
        "requires_approval BOOLEAN NOT NULL DEFAULT FALSE"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_definitions DROP COLUMN IF EXISTS requires_approval"
    )
