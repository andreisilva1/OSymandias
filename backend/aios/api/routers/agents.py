import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from aios.api.deps import get_db
from aios.api.schemas.agent import (
    AgentDefinitionCreate,
    AgentDefinitionResponse,
    AgentDefinitionUpdate,
    AgentInstanceResponse,
)
from aios.models import AgentDefinition, AgentInstance

router = APIRouter(prefix="/api/v1/agents", tags=["agents"])


@router.get("", response_model=list[AgentDefinitionResponse])
async def list_agents(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(AgentDefinition).order_by(AgentDefinition.name))
    return result.scalars().all()


@router.post("", response_model=AgentDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_agent(body: AgentDefinitionCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.get(AgentDefinition, body.name)
    if existing:
        raise HTTPException(status_code=409, detail=f"Agent '{body.name}' already exists")
    agent = AgentDefinition(**body.model_dump())
    db.add(agent)
    await db.commit()
    await db.refresh(agent)
    return agent


@router.get("/{name}", response_model=AgentDefinitionResponse)
async def get_agent(name: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    return agent


@router.put("/{name}", response_model=AgentDefinitionResponse)
async def update_agent(name: str, body: AgentDefinitionUpdate, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(agent, field, value)
    agent.updated_at = datetime.now(timezone.utc)
    # Bump version
    major, minor = agent.version.split(".")
    agent.version = f"{major}.{int(minor) + 1}"
    await db.commit()
    await db.refresh(agent)
    return agent


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_agent(name: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    await db.commit()


@router.get("/{name}/instances", response_model=list[AgentInstanceResponse])
async def get_agent_instances(name: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentInstance)
        .where(AgentInstance.agent_definition_name == name)
        .order_by(AgentInstance.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
