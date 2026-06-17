from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osymandias.runtime.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from osymandias.runtime.models.agent_instance import AgentInstance


class AgentDefinition(Base, TimestampMixin):
    __tablename__ = "agent_definitions"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    version: Mapped[str] = mapped_column(String(20), nullable=False, default="1.0")
    description: Mapped[str | None] = mapped_column(Text)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    system_prompt_template: Mapped[str] = mapped_column(Text, nullable=False)
    allowed_tools: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False, default="ollama")
    llm_model: Mapped[str] = mapped_column(String(100), nullable=False, default="llama3.2")
    max_iterations: Mapped[int] = mapped_column(Integer, nullable=False, default=20)
    timeout_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=120)
    output_schema: Mapped[dict | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    instances: Mapped[list["AgentInstance"]] = relationship(
        "AgentInstance", back_populates="agent_definition"
    )
