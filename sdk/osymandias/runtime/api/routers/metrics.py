import json

import redis as _redis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from datetime import datetime, timedelta, timezone

from osymandias.runtime.api.deps import get_db
from osymandias.runtime.config import settings
from osymandias.runtime.models import Job, JobStatus
from osymandias.runtime.services.metrics_service import compute_metrics_async

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary(db: AsyncSession = Depends(get_db)):
    r = _redis.from_url(settings.osy_redis_url, decode_responses=True)
    cached = r.get("metrics:summary")
    r.close()
    if cached:
        return json.loads(cached)

    # Beat worker hasn't run yet — compute on-the-fly from DB
    return await compute_metrics_async(db)


@router.get("/daily")
async def metrics_daily(db: AsyncSession = Depends(get_db)):
    """Return completed/failed counts for each of the last 7 days."""
    now = datetime.now(timezone.utc)
    days = []
    for offset in range(6, -1, -1):
        day_start = (now - timedelta(days=offset)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )
        day_end = day_start + timedelta(days=1)
        label = day_start.strftime("%a")

        completed = await db.scalar(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.COMPLETED,
                Job.completed_at >= day_start,
                Job.completed_at < day_end,
            )
        ) or 0

        failed = await db.scalar(
            select(func.count(Job.id)).where(
                Job.status == JobStatus.FAILED,
                Job.completed_at >= day_start,
                Job.completed_at < day_end,
            )
        ) or 0

        days.append({"name": label, "date": day_start.date().isoformat(), "completed": completed, "failed": failed})

    return days
