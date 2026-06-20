"""add estimated_cost to agent_instances

Revision ID: 0010
Revises: 0009
Create Date: 2026-06-20
"""
from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_instances ADD COLUMN IF NOT EXISTS "
        "estimated_cost NUMERIC(10, 6) NOT NULL DEFAULT 0.0"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_instances DROP COLUMN IF EXISTS estimated_cost"
    )
