from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class AgentDefinitionCreate(BaseModel):
    name: str
    version: str = "1.0"
    description: str | None = None
    role: str
    system_prompt_template: str
    allowed_tools: list[str] = []
    llm_provider: str = "ollama"
    llm_model: str = "llama3.2"
    max_iterations: int = 20
    timeout_seconds: int = 120
    output_schema: dict[str, Any] | None = None


class AgentDefinitionUpdate(BaseModel):
    description: str | None = None
    system_prompt_template: str | None = None
    allowed_tools: list[str] | None = None
    llm_provider: str | None = None
    llm_model: str | None = None
    max_iterations: int | None = None
    timeout_seconds: int | None = None
    output_schema: dict[str, Any] | None = None


class AgentDefinitionResponse(BaseModel):
    name: str
    version: str
    description: str | None
    role: str
    system_prompt_template: str
    allowed_tools: list[str]
    llm_provider: str
    llm_model: str
    max_iterations: int
    timeout_seconds: int
    output_schema: dict | None
    is_active: bool
    created_at: datetime
    updated_at: datetime | None
    agent_kind: str | None = None
    callable_ref: str | None = None
    framework: str | None = None

    model_config = {"from_attributes": True}


class AgentInstanceResponse(BaseModel):
    id: UUID
    job_id: UUID
    task_id: UUID | None
    agent_definition_name: str
    status: str
    iteration_count: int
    tokens_used: int
    tool_calls_count: int
    last_heartbeat_at: datetime | None
    created_at: datetime
    terminated_at: datetime | None

    model_config = {"from_attributes": True}
