"""
Shared metrics computation — used by the /metrics API router (async)
and the aggregate_metrics beat task (sync).
"""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Session

from osymandias.runtime.models import AgentInstance, Job, JobStatus


def compute_metrics_sync(session: Session) -> dict:
    now = datetime.now(timezone.utc)
    last_24h = now - timedelta(hours=24)
    last_7d = now - timedelta(days=7)

    completed_24h = session.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.COMPLETED, Job.completed_at >= last_24h
        )
    ) or 0

    failed_24h = session.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.FAILED, Job.completed_at >= last_24h
        )
    ) or 0

    completed_7d = session.scalar(
        select(func.count(Job.id)).where(
            Job.status == JobStatus.COMPLETED, Job.completed_at >= last_7d
        )
    ) or 0
    total_7d = session.scalar(
        select(func.count(Job.id)).where(Job.completed_at >= last_7d)
    ) or 1

    active = session.scalar(
        select(func.count(Job.id)).where(
            Job.status.in_([JobStatus.RUNNING, JobStatus.PLANNING])
        )
    ) or 0

    total_tokens_today = session.scalar(
        select(func.coalesce(func.sum(AgentInstance.tokens_used), 0)).where(
            AgentInstance.created_at >= last_24h
        )
    ) or 0

    total_cost_today = float(session.scalar(
        select(func.coalesce(func.sum(Job.estimated_cost), 0)).where(
            Job.created_at >= last_24h
        )
    ) or 0)

    avg_duration_row = session.scalar(
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


async def compute_metrics_async(db: AsyncSession) -> dict:
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
