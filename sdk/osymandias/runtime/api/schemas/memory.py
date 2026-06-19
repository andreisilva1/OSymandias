from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class MemoryEntryResponse(BaseModel):
    id: UUID
    scope: str
    scope_id: UUID | None
    key: str
    value: dict[str, Any]
    access_count: int
    created_at: datetime
    last_accessed_at: datetime | None
    expires_at: datetime | None

    model_config = {"from_attributes": True}
