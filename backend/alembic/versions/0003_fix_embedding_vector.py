"""fix memory_entries.embedding: ARRAY(float) → vector(1536)

Revision ID: 0003
Revises: 0002
Create Date: 2026-06-15
"""
from alembic import op
import sqlalchemy as sa

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    # Drop old float[] column and recreate as vector(1536)
    op.drop_column("memory_entries", "embedding")
    op.execute("ALTER TABLE memory_entries ADD COLUMN embedding vector(1536)")


def downgrade() -> None:
    op.drop_column("memory_entries", "embedding")
    op.add_column(
        "memory_entries",
        sa.Column("embedding", sa.ARRAY(sa.Float), nullable=True),
    )
