from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from osymandias.runtime.models.base import Base, TimestampMixin


class ToolDefinition(Base, TimestampMixin):
    __tablename__ = "tool_definitions"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    input_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    output_schema: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    rate_limit_per_minute: Mapped[int | None] = mapped_column(Integer)
    requires_external_api: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    # Webhook-based user-defined syscalls: POST input_args → webhook_url → return JSON
    webhook_url: Mapped[str | None] = mapped_column(Text)
