from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class EventResponse(BaseModel):
    id: UUID
    job_id: UUID | None
    task_id: UUID | None
    agent_instance_id: UUID | None
    event_type: str
    payload: dict[str, Any] | None
    tokens_used: int | None
    estimated_cost: float | None
    duration_ms: int | None
    timestamp: datetime

    model_config = {"from_attributes": True}
