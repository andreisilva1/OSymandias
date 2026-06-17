"""initial schema

Revision ID: 0001
Revises:
Create Date: 2024-01-01 00:00:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp"')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector"')

    # agent_definitions
    op.create_table(
        "agent_definitions",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("version", sa.String(20), nullable=False, server_default="1.0"),
        sa.Column("description", sa.Text),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("system_prompt_template", sa.Text, nullable=False),
        sa.Column("allowed_tools", postgresql.JSONB, nullable=False, server_default="[]"),
        sa.Column("llm_provider", sa.String(50), nullable=False, server_default="ollama"),
        sa.Column("llm_model", sa.String(100), nullable=False, server_default="llama3.2"),
        sa.Column("max_iterations", sa.Integer, nullable=False, server_default="20"),
        sa.Column("timeout_seconds", sa.Integer, nullable=False, server_default="120"),
        sa.Column("output_schema", postgresql.JSONB),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True)),
    )

    # tool_definitions
    op.create_table(
        "tool_definitions",
        sa.Column("name", sa.String(100), primary_key=True),
        sa.Column("description", sa.Text, nullable=False),
        sa.Column("input_schema", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output_schema", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("rate_limit_per_minute", sa.Integer),
        sa.Column("requires_external_api", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default="true"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    # jobs
    op.create_table(
        "jobs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING", index=True),
        sa.Column("priority", sa.String(10), nullable=False, server_default="NORMAL"),
        sa.Column("input_payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output_payload", postgresql.JSONB),
        sa.Column("retry_policy", postgresql.JSONB, nullable=False),
        sa.Column("total_tokens", sa.Integer, nullable=False, server_default="0"),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # agent_instances
    op.create_table(
        "agent_instances",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("agent_definition_name", sa.String(100), sa.ForeignKey("agent_definitions.name", ondelete="RESTRICT"), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="CREATED", index=True),
        sa.Column("iteration_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tokens_used", sa.Integer, nullable=False, server_default="0"),
        sa.Column("tool_calls_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("last_heartbeat_at", sa.DateTime(timezone=True), index=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("terminated_at", sa.DateTime(timezone=True)),
    )

    # tasks
    op.create_table(
        "tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text),
        sa.Column("status", sa.String(20), nullable=False, server_default="PENDING", index=True),
        sa.Column("agent_type", sa.String(100), sa.ForeignKey("agent_definitions.name", ondelete="SET NULL")),
        sa.Column("agent_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_instances.id", ondelete="SET NULL")),
        sa.Column("input_context", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output_result", postgresql.JSONB),
        sa.Column("output_schema", postgresql.JSONB),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("max_attempts", sa.Integer, nullable=False, server_default="3"),
        sa.Column("evaluation_score", sa.Float),
        sa.Column("evaluation_feedback", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True)),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
    )

    # now that tasks table exists, add the deferred FK on agent_instances.task_id
    op.create_foreign_key(
        "fk_agent_instances_task_id",
        "agent_instances", "tasks",
        ["task_id"], ["id"],
        ondelete="SET NULL",
    )

    # task_dependencies
    op.create_table(
        "task_dependencies",
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("depends_on_task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_index("idx_task_dep_task", "task_dependencies", ["task_id"])
    op.create_index("idx_task_dep_depends", "task_dependencies", ["depends_on_task_id"])

    # messages
    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("sender_agent_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("receiver_agent_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_instances.id", ondelete="SET NULL"), index=True),
        sa.Column("receiver_agent_type", sa.String(100)),
        sa.Column("message_type", sa.String(20), nullable=False),
        sa.Column("subject", sa.String(255), nullable=False),
        sa.Column("content", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("is_read", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_message_mailbox", "messages", ["receiver_agent_instance_id", "is_read", "sent_at"])

    # tool_calls
    op.create_table(
        "tool_calls",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agent_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_instances.id", ondelete="CASCADE"), nullable=False, index=True),
        sa.Column("tool_name", sa.String(100), sa.ForeignKey("tool_definitions.name", ondelete="RESTRICT"), nullable=False),
        sa.Column("input_args", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("output_result", postgresql.JSONB),
        sa.Column("status", sa.String(30), nullable=False, server_default="PENDING"),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("error_message", sa.Text),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True)),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("estimated_cost", sa.Numeric(10, 6), nullable=False, server_default="0"),
    )

    # events
    op.create_table(
        "events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("job_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("jobs.id", ondelete="CASCADE"), index=True),
        sa.Column("task_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("tasks.id", ondelete="CASCADE")),
        sa.Column("agent_instance_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("agent_instances.id", ondelete="SET NULL")),
        sa.Column("event_type", sa.String(100), nullable=False, index=True),
        sa.Column("payload", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("tokens_used", sa.Integer),
        sa.Column("estimated_cost", sa.Numeric(10, 6)),
        sa.Column("duration_ms", sa.Integer),
        sa.Column("timestamp", sa.DateTime(timezone=True), nullable=False, index=True),
    )
    op.create_index("idx_event_job_timestamp", "events", ["job_id", sa.text("timestamp DESC")])

    # memory_entries
    op.create_table(
        "memory_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("scope", sa.String(10), nullable=False, index=True),
        sa.Column("scope_id", postgresql.UUID(as_uuid=True), index=True),
        sa.Column("key", sa.String(255), nullable=False),
        sa.Column("value", postgresql.JSONB, nullable=False, server_default="{}"),
        sa.Column("embedding", postgresql.ARRAY(sa.Float), nullable=True),
        sa.Column("qdrant_point_id", postgresql.UUID(as_uuid=True)),
        sa.Column("access_count", sa.Integer, nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_accessed_at", sa.DateTime(timezone=True)),
        sa.Column("expires_at", sa.DateTime(timezone=True)),
    )
    op.create_index("idx_memory_scope", "memory_entries", ["scope", "scope_id"])


def downgrade() -> None:
    op.drop_table("memory_entries")
    op.drop_table("events")
    op.drop_table("tool_calls")
    op.drop_table("messages")
    op.drop_table("task_dependencies")
    op.drop_constraint("fk_agent_instances_task_id", "agent_instances", type_="foreignkey")
    op.drop_table("tasks")
    op.drop_table("agent_instances")
    op.drop_table("jobs")
    op.drop_table("tool_definitions")
    op.drop_table("agent_definitions")
