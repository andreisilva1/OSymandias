"""add webhook_subscriptions

Revision ID: 0011
Revises: 0010
Create Date: 2026-06-20
"""
from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS webhook_subscriptions (
            id UUID PRIMARY KEY,
            url VARCHAR(2048) NOT NULL,
            events JSONB,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT now()
        )
        """
    )


def downgrade() -> None:
    op.execute("DROP TABLE IF EXISTS webhook_subscriptions")
