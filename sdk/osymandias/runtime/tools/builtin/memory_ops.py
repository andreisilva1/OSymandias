"""
memory_ops tools — write_to_job_memory, read_from_job_memory, search_memory.
"""
import uuid
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from osymandias.runtime.models import AgentInstance
from osymandias.runtime.tools.registry import register


@register("write_to_job_memory")
def write_to_job_memory(
    key: str,
    value: dict[str, Any],
    session: Session,
    agent_instance_id: uuid.UUID,
    embed: bool = False,
) -> dict:
    instance = session.get(AgentInstance, agent_instance_id)
    if not instance:
        return {"stored": False, "error": "agent not found"}

    from osymandias.runtime.memory.manager import MemoryManager
    from osymandias.runtime.models.memory_entry import MemoryScope
    MemoryManager.write_sync(
        session=session,
        scope=MemoryScope.JOB,
        scope_id=instance.job_id,
        key=key,
        value=value,
        embed=embed,
    )
    return {"stored": True, "key": key}


@register("read_from_job_memory")
def read_from_job_memory(
    key: str,
    session: Session,
    agent_instance_id: uuid.UUID,
) -> dict:
    instance = session.get(AgentInstance, agent_instance_id)
    if not instance:
        return {"found": False, "error": "agent not found"}

    from osymandias.runtime.memory.manager import MemoryManager
    from osymandias.runtime.models.memory_entry import MemoryScope
    entry = MemoryManager.read_sync(
        session=session,
        scope=MemoryScope.JOB,
        scope_id=instance.job_id,
        key=key,
    )
    if entry is None:
        return {"found": False, "key": key}
    return {"found": True, "key": key, "value": entry}


@register("search_memory")
def search_memory(
    query: str,
    session: Session,
    agent_instance_id: uuid.UUID,
    top_k: int = 5,
) -> dict:
    instance = session.get(AgentInstance, agent_instance_id)
    if not instance:
        return {"results": [], "error": "agent not found"}

    from osymandias.runtime.memory.manager import MemoryManager
    from osymandias.runtime.models.memory_entry import MemoryScope
    results = MemoryManager.search_sync(
        query=query,
        scopes=[MemoryScope.JOB, MemoryScope.GLOBAL],
        scope_ids=[instance.job_id],
        top_k=top_k,
        session=session,
    )
    return {"results": results}
