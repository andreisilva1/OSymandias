"""
EventEmitter — writes structured events to PostgreSQL and publishes
them to Redis pub/sub so the SSE endpoint can stream them to clients.
"""
import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis as _redis
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.config import settings
from osymandias.runtime.models.event import Event

# Lifecycle events that fan out to registered webhook subscribers.
_WEBHOOK_EVENTS = {"JOB_COMPLETED", "JOB_FAILED", "JOB_CANCELLED", "JOB_BUDGET_EXCEEDED"}

# Synchronous Redis client used inside Celery workers (no async loop available)
_redis_client: _redis.Redis | None = None


def _get_redis() -> _redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = _redis.from_url(settings.osy_redis_url, decode_responses=True)
    return _redis_client


def _serialize(obj: Any) -> Any:
    if isinstance(obj, uuid.UUID):
        return str(obj)
    if isinstance(obj, datetime):
        return obj.isoformat()
    return str(obj)


class EventEmitter:
    """
    Use emit_sync() inside Celery workers (synchronous context).
    Use emit() inside FastAPI route handlers (async context).
    """

    # ------------------------------------------------------------------
    # Async (FastAPI context)
    # ------------------------------------------------------------------

    @staticmethod
    async def emit(
        session: AsyncSession,
        event_type: str,
        payload: dict[str, Any],
        job_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        agent_instance_id: uuid.UUID | None = None,
        tokens_used: int | None = None,
        estimated_cost: float | None = None,
        duration_ms: int | None = None,
    ) -> Event:
        event = Event(
            event_type=event_type,
            payload=payload,
            job_id=job_id,
            task_id=task_id,
            agent_instance_id=agent_instance_id,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
        )
        session.add(event)
        await session.flush()  # get the id without committing

        EventEmitter._publish(event)
        EventEmitter._dispatch_webhooks(event)
        return event

    # ------------------------------------------------------------------
    # Sync (Celery worker context)
    # ------------------------------------------------------------------

    @staticmethod
    def emit_sync(
        session: Any,  # sync SQLAlchemy session
        event_type: str,
        payload: dict[str, Any],
        job_id: uuid.UUID | None = None,
        task_id: uuid.UUID | None = None,
        agent_instance_id: uuid.UUID | None = None,
        tokens_used: int | None = None,
        estimated_cost: float | None = None,
        duration_ms: int | None = None,
    ) -> Event:
        event = Event(
            event_type=event_type,
            payload=payload,
            job_id=job_id,
            task_id=task_id,
            agent_instance_id=agent_instance_id,
            tokens_used=tokens_used,
            estimated_cost=estimated_cost,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc),
        )
        session.add(event)
        session.flush()

        EventEmitter._publish(event)
        EventEmitter._dispatch_webhooks(event)
        return event

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _dispatch_webhooks(event: Event) -> None:
        """Enqueue webhook delivery for lifecycle events. The Celery task does the
        subscription lookup, so this stays cheap (one enqueue) and no-ops when no
        subscribers exist."""
        if event.event_type not in _WEBHOOK_EVENTS or not event.job_id:
            return
        try:
            from osymandias.runtime.workers.celery_app import celery_app
            celery_app.send_task(
                "osymandias.runtime.workers.webhook_tasks.deliver_event",
                args=[event.event_type, str(event.job_id), event.payload],
                queue="tools",
            )
        except Exception as exc:
            logger.warning("webhook enqueue failed for {} — {}", event.event_type, exc)

    @staticmethod
    def _publish(event: Event) -> None:
        try:
            r = _get_redis()
            data = json.dumps(
                {
                    "id": str(event.id),
                    "event_type": event.event_type,
                    "job_id": str(event.job_id) if event.job_id else None,
                    "task_id": str(event.task_id) if event.task_id else None,
                    "agent_instance_id": str(event.agent_instance_id) if event.agent_instance_id else None,
                    "payload": event.payload,
                    "tokens_used": event.tokens_used,
                    "estimated_cost": float(event.estimated_cost) if event.estimated_cost else None,
                    "duration_ms": event.duration_ms,
                    "timestamp": event.timestamp.isoformat(),
                },
                default=_serialize,
            )

            # channel per job (consumed by SSE endpoint)
            if event.job_id:
                r.publish(f"events:job:{event.job_id}", data)

            # global channel (consumed by system monitors)
            r.publish("events:global", data)

        except Exception as exc:
            # publishing failures must never crash the worker
            logger.warning("EventEmitter: Redis publish failed — {}", exc)
