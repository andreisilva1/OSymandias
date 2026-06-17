import enum
import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osymandias.runtime.models.base import Base, new_uuid

if TYPE_CHECKING:
    from osymandias.runtime.models.agent_instance import AgentInstance


class MessageType(str, enum.Enum):
    TASK_RESULT = "TASK_RESULT"
    DATA_SHARE = "DATA_SHARE"
    REQUEST = "REQUEST"
    BROADCAST = "BROADCAST"


class Message(Base):
    __tablename__ = "messages"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("jobs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    sender_agent_instance_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_instances.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # null = broadcast or type-based routing
    receiver_agent_instance_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("agent_instances.id", ondelete="SET NULL"),
        index=True,
    )
    # used when routing by agent type instead of specific instance
    receiver_agent_type: Mapped[str | None] = mapped_column(String(100))
    message_type: Mapped[MessageType] = mapped_column(String(20), nullable=False)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    content: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    sender: Mapped["AgentInstance"] = relationship(
        "AgentInstance",
        foreign_keys=[sender_agent_instance_id],
        back_populates="sent_messages",
    )
    receiver: Mapped["AgentInstance | None"] = relationship(
        "AgentInstance",
        foreign_keys=[receiver_agent_instance_id],
        back_populates="received_messages",
    )
