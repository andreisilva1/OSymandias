import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osymandias.runtime.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from osymandias.runtime.models.agent_definition import AgentDefinition
    from osymandias.runtime.models.task import Task
    from osymandias.runtime.models.tool_call import ToolCall
    from osymandias.runtime.models.message import Message


class AgentInstanceStatus(str, enum.Enum):
    CREATED = "CREATED"
    READY = "READY"
    RUNNING = "RUNNING"
    BLOCKED = "BLOCKED"
    SUSPENDED = "SUSPENDED"
    TERMINATED = "TERMINATED"
    CRASHED = "CRASHED"


class AgentInstance(Base, TimestampMixin):
    __tablename__ = "agent_instances"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="SET NULL")
    )
    agent_definition_name: Mapped[str] = mapped_column(
        String(100), ForeignKey("agent_definitions.name", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[AgentInstanceStatus] = mapped_column(
        String(20),
        nullable=False,
        default=AgentInstanceStatus.CREATED,
        index=True,
    )
    iteration_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tokens_used: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    tool_calls_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_heartbeat_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), index=True
    )
    terminated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    agent_definition: Mapped["AgentDefinition"] = relationship(
        "AgentDefinition", back_populates="instances"
    )
    task: Mapped["Task | None"] = relationship(
        "Task", foreign_keys=[task_id], back_populates="agent_instances"
    )
    tool_calls: Mapped[list["ToolCall"]] = relationship(
        "ToolCall", back_populates="agent_instance"
    )
    sent_messages: Mapped[list["Message"]] = relationship(
        "Message", foreign_keys="Message.sender_agent_instance_id", back_populates="sender"
    )
    received_messages: Mapped[list["Message"]] = relationship(
        "Message", foreign_keys="Message.receiver_agent_instance_id", back_populates="receiver"
    )
