"""
Webhook tasks — deliver lifecycle events to registered subscriber URLs.
"""
import httpx
from loguru import logger
from sqlalchemy import select

from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import WebhookSubscription
from osymandias.runtime.workers.celery_app import celery_app


@celery_app.task(
    name="osymandias.runtime.workers.webhook_tasks.deliver_event",
    bind=True,
    max_retries=0,  # best-effort; a failed POST to one URL must not re-POST to all
)
def deliver_event(self, event_type: str, job_id: str, payload: dict) -> None:
    """POST a lifecycle event to every active subscriber registered for it."""
    session = get_sync_session()
    try:
        subs = session.scalars(
            select(WebhookSubscription).where(WebhookSubscription.is_active == True)  # noqa: E712
        ).all()
        targets = [s for s in subs if not s.events or event_type in s.events]
        if not targets:
            return

        body = {"event_type": event_type, "job_id": job_id, "payload": payload}
        for sub in targets:
            try:
                httpx.post(sub.url, json=body, timeout=10)
            except Exception as exc:
                logger.warning("webhook POST to {} failed: {}", sub.url, exc)
    finally:
        session.close()
