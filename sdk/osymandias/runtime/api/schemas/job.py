from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field


class RetryPolicy(BaseModel):
    max_attempts: int = 3
    backoff: str = "exponential"
    backoff_seconds: int = 5


class JobCreate(BaseModel):
    title: str
    description: str | None = None
    priority: str = "NORMAL"
    input_payload: dict[str, Any] = Field(default_factory=dict)
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)


class JobResponse(BaseModel):
    id: UUID
    title: str
    description: str | None
    status: str
    priority: str
    input_payload: dict[str, Any]
    output_payload: dict[str, Any] | None
    retry_policy: dict[str, Any]
    total_tokens: int
    estimated_cost: float
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}


class TaskResponse(BaseModel):
    id: UUID
    job_id: UUID
    parent_task_id: UUID | None
    title: str
    description: str | None
    status: str
    agent_type: str | None
    agent_instance_id: UUID | None
    input_context: dict[str, Any]
    output_result: dict[str, Any] | None
    attempt_count: int
    max_attempts: int
    evaluation_score: float | None
    evaluation_feedback: str | None
    depends_on: list[str] = []
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None

    model_config = {"from_attributes": True}
