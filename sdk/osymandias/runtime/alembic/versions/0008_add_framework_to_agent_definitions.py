"""add framework to agent_definitions

Revision ID: 0008
Revises: 0007
Create Date: 2026-06-18
"""
from alembic import op
import sqlalchemy as sa

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE agent_definitions ADD COLUMN IF NOT EXISTS framework VARCHAR(64)"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE agent_definitions DROP COLUMN IF EXISTS framework"
    )
