import uuid as uuid_lib

from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db
from osymandias.runtime.api.schemas.event import EventResponse
from osymandias.runtime.models import Event

router = APIRouter(prefix="/api/v1/events", tags=["events"])


@router.get("", response_model=list[EventResponse])
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
    return result.scalars().all()
