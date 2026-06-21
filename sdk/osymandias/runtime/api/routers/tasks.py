from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db
from osymandias.runtime.api.schemas.job import TaskResponse
from osymandias.runtime.models import Task, TaskStatus

router = APIRouter(prefix="/api/v1/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskResponse])
async def list_tasks(
    status: str | None = None,
    limit: int = Query(default=100, le=500),
    db: AsyncSession = Depends(get_db),
):
    """List tasks across all jobs, optionally filtered by status.

    Powers cross-job views such as the approval inbox (status=HUMAN_REVIEW).
    """
    if status is not None:
        valid = {s.value for s in TaskStatus}
        if status not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status}'. Valid values: {sorted(valid)}")

    q = select(Task).order_by(Task.created_at.desc()).limit(limit)
    if status:
        q = q.where(Task.status == status)
    result = await db.execute(q)
    return result.scalars().all()
