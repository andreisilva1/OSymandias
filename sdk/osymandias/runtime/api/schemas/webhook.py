from datetime import datetime
from uuid import UUID

from pydantic import BaseModel


class WebhookCreate(BaseModel):
    url: str
    # Event types to deliver (e.g. ["JOB_COMPLETED"]); omit/null to receive all.
    events: list[str] | None = None


class WebhookResponse(BaseModel):
    id: UUID
    url: str
    events: list[str] | None
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
