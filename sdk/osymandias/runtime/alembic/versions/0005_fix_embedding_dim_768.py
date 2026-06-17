"""fix embedding vector dimension: 1536 → 768 (nomic-embed-text default)

Revision ID: 0005
Revises: 0004
Create Date: 2026-06-15
"""
from alembic import op

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE memory_entries DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memory_entries ADD COLUMN embedding vector(768)")


def downgrade() -> None:
    op.execute("ALTER TABLE memory_entries DROP COLUMN IF EXISTS embedding")
    op.execute("ALTER TABLE memory_entries ADD COLUMN embedding vector(1536)")
