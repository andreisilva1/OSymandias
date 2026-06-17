import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osymandias.runtime.models.base import Base, TimestampMixin, new_uuid

if TYPE_CHECKING:
    from osymandias.runtime.models.agent_instance import AgentInstance


class ToolCallStatus(str, enum.Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    TIMEOUT = "TIMEOUT"
    PERMISSION_DENIED = "PERMISSION_DENIED"


class ToolCall(Base, TimestampMixin):
    __tablename__ = "tool_calls"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    task_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False
    )
    agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tool_name: Mapped[str] = mapped_column(String(100), nullable=False)
    input_args: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_result: Mapped[dict | None] = mapped_column(JSONB)
    status: Mapped[ToolCallStatus] = mapped_column(
        String(30), nullable=False, default=ToolCallStatus.PENDING
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    error_message: Mapped[str | None] = mapped_column(Text)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    estimated_cost: Mapped[float] = mapped_column(Numeric(10, 6), nullable=False, default=0.0)

    agent_instance: Mapped["AgentInstance"] = relationship(
        "AgentInstance", back_populates="tool_calls"
    )
