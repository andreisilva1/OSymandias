import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from osymandias.runtime.models.base import Base, TimestampMixin, new_uuid


class WebhookSubscription(Base, TimestampMixin):
    __tablename__ = "webhook_subscriptions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=new_uuid
    )
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    # List of event types to deliver (e.g. ["JOB_COMPLETED"]); null = all eligible events.
    events: Mapped[list | None] = mapped_column(JSONB)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
