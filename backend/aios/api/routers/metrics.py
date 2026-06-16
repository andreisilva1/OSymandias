import json
from datetime import datetime, timedelta, timezone

import redis as _redis
from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from aios.api.deps import get_db
from aios.config import settings
from aios.models import AgentInstance, Job, JobStatus

router = APIRouter(prefix="/api/v1/metrics", tags=["metrics"])


@router.get("/summary")
async def metrics_summary(db: AsyncSession = Depends(get_db)):
    r = _redis.from_url(settings.redis_url, decode_responses=True)
    cached = r.get("metrics:summary")
    if cached:
        return json.loads(cached)

    # Beat worker hasn't run yet — compute on-the-fly from DB
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    completed_24h = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.COMPLETED, Job.completed_at >= last_24h
        )
    ) or 0

    failed_24h = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.FAILED, Job.completed_at >= last_24h
        )
    ) or 0

    completed_7d = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.COMPLETED, Job.completed_at >= last_7d
        )
    ) or 0
    total_7d = await db.scalar(
        select(func.count(Job.id)).where(Job.completed_at >= last_7d)
    ) or 1

    active = await db.scalar(
        select(func.count(Job.id)).where(
            Job.status.in_([JobStatus.RUNNING, JobStatus.PLANNING])
        )
    ) or 0

    total_tokens_today = await db.scalar(
        select(func.coalesce(func.sum(AgentInstance.tokens_used), 0)).where(
            AgentInstance.created_at >= last_24h
        )
    ) or 0

    total_cost_today = float(await db.scalar(
        select(func.coalesce(func.sum(Job.estimated_cost), 0)).where(
            Job.created_at >= last_24h
        )
    ) or 0)

    avg_duration_row = await db.scalar(
        select(
            func.avg(
                func.extract("epoch", Job.completed_at) * 1000
                - func.extract("epoch", Job.started_at) * 1000
            )
        ).where(
            Job.status == JobStatus.COMPLETED,
            Job.started_at.isnot(None),
            Job.completed_at.isnot(None),
            Job.completed_at >= last_7d,
        )
    )

    return {
        "jobs_completed_last_24h": completed_24h,
        "jobs_failed_last_24h": failed_24h,
        "success_rate_7d": round(completed_7d / total_7d, 3),
        "active_jobs_count": active,
        "total_tokens_today": total_tokens_today,
        "total_cost_today": total_cost_today,
        "avg_job_duration_ms": int(avg_duration_row) if avg_duration_row else 0,
        "computed_at": now.isoformat(),
    }
