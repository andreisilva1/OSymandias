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
    from osymandias.runtime.services.metrics_service import compute_metrics_sync

    session = get_sync_session()
    r = _redis.from_url(settings.osy_redis_url, decode_responses=True)
    try:
        metrics = compute_metrics_sync(session)
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
