"""drop tool_calls.tool_name FK — LLMs generate arbitrary names

Revision ID: 0002
Revises: 0001
Create Date: 2026-06-15
"""
from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint(
        "tool_calls_tool_name_fkey", "tool_calls", type_="foreignkey"
    )


def downgrade() -> None:
    op.create_foreign_key(
        "tool_calls_tool_name_fkey",
        "tool_calls",
        "tool_definitions",
        ["tool_name"],
        ["name"],
        ondelete="RESTRICT",
    )
