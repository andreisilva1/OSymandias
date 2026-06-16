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


@router.patch("/{name}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_agent(name: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = False
    await db.commit()


@router.patch("/{name}/reactivate", status_code=status.HTTP_204_NO_CONTENT)
async def reactivate_agent(name: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    agent.is_active = True
    await db.commit()


@router.delete("/{name}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_agent(name: str, db: AsyncSession = Depends(get_db)):
    agent = await db.get(AgentDefinition, name)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    await db.delete(agent)
    await db.commit()


@router.post("/{name}/clone", response_model=AgentDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def clone_agent(name: str, db: AsyncSession = Depends(get_db)):
    source = await db.get(AgentDefinition, name)
    if not source:
        raise HTTPException(status_code=404, detail="Agent not found")

    base = f"{name} (copy)"
    new_name = base
    i = 2
    while await db.get(AgentDefinition, new_name):
        new_name = f"{base} {i}"
        i += 1

    clone = AgentDefinition(
        name=new_name,
        version="1.0",
        description=source.description,
        role=source.role,
        system_prompt_template=source.system_prompt_template,
        allowed_tools=list(source.allowed_tools or []),
        llm_provider=source.llm_provider,
        llm_model=source.llm_model,
        max_iterations=source.max_iterations,
        timeout_seconds=source.timeout_seconds,
        output_schema=source.output_schema,
        is_active=True,
    )
    db.add(clone)
    await db.commit()
    await db.refresh(clone)
    return clone


@router.get("/{name}/instances", response_model=list[AgentInstanceResponse])
async def get_agent_instances(name: str, limit: int = 50, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(AgentInstance)
        .where(AgentInstance.agent_definition_name == name)
        .order_by(AgentInstance.created_at.desc())
        .limit(limit)
    )
    return result.scalars().all()
