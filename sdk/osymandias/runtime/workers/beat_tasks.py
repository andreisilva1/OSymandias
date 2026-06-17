"""
Beat tasks — periodic background jobs.
"""
import json
from datetime import datetime, timedelta, timezone

import redis as _redis
from loguru import logger
from sqlalchemy import func, or_, and_, select

from osymandias.runtime.config import settings
from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import AgentInstance, AgentInstanceStatus, Job, JobStatus, Task, TaskStatus
from osymandias.runtime.workers.celery_app import celery_app


@celery_app.task(name="osymandias.runtime.workers.beat_tasks.monitor_heartbeats")
def monitor_heartbeats() -> None:
    """
    Detect crashed agents (no heartbeat for N seconds) and requeue their tasks.
    """
    session = get_sync_session()
    try:
        threshold = datetime.now(timezone.utc) - timedelta(seconds=settings.heartbeat_timeout_seconds)

        crashed = session.scalars(
            select(AgentInstance).where(
                AgentInstance.status == AgentInstanceStatus.RUNNING,
                or_(
                    # Agent sent at least one heartbeat but it is now stale
                    and_(
                        AgentInstance.last_heartbeat_at.isnot(None),
                        AgentInstance.last_heartbeat_at < threshold,
                    ),
                    # Agent never sent a heartbeat (worker died before first flush)
                    and_(
                        AgentInstance.last_heartbeat_at.is_(None),
                        AgentInstance.created_at < threshold,
                    ),
                ),
            )
        ).all()

        for instance in crashed:
            logger.warning("Heartbeat timeout: agent instance {} crashed", instance.id)
            instance.status = AgentInstanceStatus.CRASHED
            session.flush()

            EventEmitter.emit_sync(
                session,
                "AGENT_CRASHED",
                {"last_heartbeat_at": instance.last_heartbeat_at.isoformat() if instance.last_heartbeat_at else None},
                job_id=instance.job_id,
                task_id=instance.task_id,
                agent_instance_id=instance.id,
            )

            if instance.task_id:
                task = session.get(Task, instance.task_id)
                if task and task.attempt_count < task.max_attempts:
                    task.status = TaskStatus.RETRYING
                    task.attempt_count += 1
                    session.flush()

                    from osymandias.runtime.workers.scheduler_tasks import dispatch_task
                    dispatch_task.apply_async(
                        args=[str(task.id)], queue="scheduler", countdown=10
                    )
                elif task:
                    task.status = TaskStatus.FAILED
                    session.flush()

                    from osymandias.runtime.workers.scheduler_tasks import resolve_dag
                    resolve_dag.apply_async(args=[str(task.job_id)], queue="scheduler")

        session.commit()
        if crashed:
            logger.info("monitor_heartbeats: {} crashed agents detected and handled", len(crashed))

    except Exception as exc:
        session.rollback()
        logger.exception("monitor_heartbeats failed: {}", exc)
    finally:
        session.close()


@celery_app.task(name="osymandias.runtime.workers.beat_tasks.aggregate_metrics")
def aggregate_metrics() -> None:
    """
    Compute aggregate metrics and cache them in Redis for the /metrics endpoints.
    """
    session = get_sync_session()
    r = _redis.from_url(settings.osy_redis_url, decode_responses=True)
    try:
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

        from osymandias.runtime.models import AgentInstance
        total_tokens_today = session.scalar(
            select(func.coalesce(func.sum(AgentInstance.tokens_used), 0)).where(
                AgentInstance.created_at >= last_24h
            )
        ) or 0

        from sqlalchemy import Numeric
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
        avg_job_duration_ms = int(avg_duration_row) if avg_duration_row else 0

        metrics = {
            "jobs_completed_last_24h": completed_24h,
            "jobs_failed_last_24h": failed_24h,
            "success_rate_7d": round(completed_7d / total_7d, 3),
            "active_jobs_count": active,
            "total_tokens_today": total_tokens_today,
            "total_cost_today": total_cost_today,
            "avg_job_duration_ms": avg_job_duration_ms,
            "computed_at": now.isoformat(),
        }

        r.setex(
            "metrics:summary",
            settings.metrics_cache_ttl_seconds,
            json.dumps(metrics),
        )
        logger.debug("aggregate_metrics: cached {}", metrics)

    except Exception as exc:
        logger.exception("aggregate_metrics failed: {}", exc)
    finally:
        session.close()
