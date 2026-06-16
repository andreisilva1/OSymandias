"""
Permission checker — verifies that an AgentInstance's role allows a tool call.
"""
import uuid

from sqlalchemy.orm import Session

from aios.models import AgentInstance, AgentDefinition, ToolCallStatus


class PermissionDenied(Exception):
    pass


def check_permission(
    tool_name: str,
    agent_instance_id: uuid.UUID,
    session: Session,
) -> None:
    """Raise PermissionDenied if the agent is not allowed to call this tool."""
    instance = session.get(AgentInstance, agent_instance_id)
    if not instance:
        raise PermissionDenied(f"AgentInstance {agent_instance_id} not found")

    definition = session.get(AgentDefinition, instance.agent_definition_name)
    if not definition:
        raise PermissionDenied(f"AgentDefinition {instance.agent_definition_name} not found")

    if tool_name not in definition.allowed_tools:
        raise PermissionDenied(
            f"Agent role '{definition.role}' is not allowed to call tool '{tool_name}'"
        )
