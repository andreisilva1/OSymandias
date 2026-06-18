"""v1.0: agent_kind + callable_ref on agent_definitions; parent_task_id on tasks

Revision ID: 0006
Revises: 0005
Create Date: 2026-06-17
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # AgentDefinition: kind discriminator + external callable reference
    op.add_column(
        "agent_definitions",
        sa.Column(
            "agent_kind",
            sa.String(20),
            nullable=False,
            server_default="builtin",
        ),
    )
    op.add_column(
        "agent_definitions",
        sa.Column("callable_ref", sa.Text, nullable=True),
    )

    # Task: optional parent for sub-tasks spawned by external agents
    op.add_column(
        "tasks",
        sa.Column(
            "parent_task_id",
            UUID(as_uuid=True),
            sa.ForeignKey("tasks.id", ondelete="CASCADE"),
            nullable=True,
            index=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("tasks", "parent_task_id")
    op.drop_column("agent_definitions", "callable_ref")
    op.drop_column("agent_definitions", "agent_kind")
