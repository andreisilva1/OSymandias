import uuid as uuid_lib

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from aios.api.deps import get_db
from aios.models import Event

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("")
async def list_events(
    limit: int = Query(50, le=200),
    job_id: str | None = None,
    event_type: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    q = select(Event).order_by(desc(Event.timestamp)).limit(limit)
    if job_id:
        try:
            q = q.where(Event.job_id == uuid_lib.UUID(job_id))
        except ValueError:
            pass
    if event_type:
        q = q.where(Event.event_type == event_type)

    result = await db.execute(q)
    events = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "job_id": str(e.job_id) if e.job_id else None,
            "task_id": str(e.task_id) if e.task_id else None,
            "agent_instance_id": str(e.agent_instance_id) if e.agent_instance_id else None,
            "event_type": e.event_type,
            "payload": e.payload,
            "tokens_used": e.tokens_used,
            "estimated_cost": float(e.estimated_cost) if e.estimated_cost is not None else None,
            "duration_ms": e.duration_ms,
            "timestamp": e.timestamp.isoformat(),
        }
        for e in events
    ]
