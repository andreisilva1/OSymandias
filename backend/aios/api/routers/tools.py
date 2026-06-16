from typing import Any
from urllib.parse import urlparse

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, field_validator
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aios.api.deps import get_db
from aios.models import ToolDefinition

_PRIVATE_PREFIXES = (
    "10.", "172.16.", "172.17.", "172.18.", "172.19.", "172.20.", "172.21.",
    "172.22.", "172.23.", "172.24.", "172.25.", "172.26.", "172.27.", "172.28.",
    "172.29.", "172.30.", "172.31.", "192.168.", "127.", "169.254.", "::1",
)


def _validate_webhook_url(url: str | None) -> str | None:
    if url is None:
        return None
    parsed = urlparse(url)
    if parsed.scheme not in ("http", "https"):
        raise ValueError("webhook_url must use http or https")
    host = parsed.hostname or ""
    if host in ("localhost",) or any(host.startswith(p) for p in _PRIVATE_PREFIXES):
        raise ValueError("webhook_url must not point to a private/loopback address")
    return url

router = APIRouter(prefix="/api/v1/tools", tags=["tools"])


def _serialize(t: ToolDefinition) -> dict:
    return {
        "name": t.name,
        "description": t.description,
        "input_schema": t.input_schema,
        "output_schema": t.output_schema,
        "rate_limit_per_minute": t.rate_limit_per_minute,
        "requires_external_api": t.requires_external_api,
        "webhook_url": t.webhook_url,
        "is_active": t.is_active,
        "created_at": t.created_at.isoformat(),
    }


class ToolCreate(BaseModel):
    name: str
    description: str
    input_schema: dict[str, Any] = {}
    output_schema: dict[str, Any] = {}
    rate_limit_per_minute: int | None = None
    requires_external_api: bool = True
    webhook_url: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook_url(v)


class ToolUpdate(BaseModel):
    description: str | None = None
    input_schema: dict[str, Any] | None = None
    output_schema: dict[str, Any] | None = None
    rate_limit_per_minute: int | None = None
    requires_external_api: bool | None = None
    webhook_url: str | None = None
    is_active: bool | None = None

    @field_validator("webhook_url")
    @classmethod
    def validate_webhook_url(cls, v: str | None) -> str | None:
        return _validate_webhook_url(v)


@router.get("")
async def list_tools(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ToolDefinition).order_by(ToolDefinition.name))
    return [_serialize(t) for t in result.scalars().all()]


@router.get("/{name}")
async def get_tool(name: str, db: AsyncSession = Depends(get_db)):
    tool = await db.get(ToolDefinition, name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    return _serialize(tool)


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_tool(body: ToolCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(ToolDefinition, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Tool '{body.name}' already exists")
    tool = ToolDefinition(**body.model_dump())
    db.add(tool)
    await db.commit()
    await db.refresh(tool)
    return _serialize(tool)


@router.put("/{name}")
async def update_tool(name: str, body: ToolUpdate, db: AsyncSession = Depends(get_db)):
    tool = await db.get(ToolDefinition, name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(tool, field, value)
    await db.commit()
    await db.refresh(tool)
    return _serialize(tool)


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_tool(name: str, db: AsyncSession = Depends(get_db)):
    tool = await db.get(ToolDefinition, name)
    if not tool:
        raise HTTPException(status_code=404, detail="Tool not found")
    tool.is_active = False
    await db.commit()
