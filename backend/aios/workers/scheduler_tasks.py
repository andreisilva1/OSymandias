"""
Scheduler tasks — orchestrate job lifecycle and DAG resolution.
All tasks run on the 'scheduler' queue (single worker, no race conditions).
"""
import uuid
from datetime import datetime, timezone

from celery import shared_task
from loguru import logger
from sqlalchemy import select

from aios.core.event_emitter import EventEmitter
from aios.db.sync_session import get_sync_session
from aios.models import (
    AgentInstance,
    AgentInstanceStatus,
    Job,
    JobStatus,
    Task,
    TaskDependency,
    TaskStatus,
)
from aios.workers.celery_app import celery_app


# ---------------------------------------------------------------------------
# dispatch_job
# ---------------------------------------------------------------------------

@celery_app.task(name="aios.workers.scheduler_tasks.dispatch_job", bind=True, max_retries=3)
def dispatch_job(self, job_id: str) -> None:
    """Entry point for a new job. Transitions to PLANNING and spawns PlannerAgent."""
    session = get_sync_session()
    try:
        job = session.get(Job, uuid.UUID(job_id))
        if not job:
            logger.error("dispatch_job: job {} not found", job_id)
            return

        job.status = JobStatus.PLANNING
        job.started_at = datetime.now(timezone.utc)
        session.flush()

        EventEmitter.emit_sync(session, "JOB_STARTED", {}, job_id=job.id)

        # Create PlannerAgent instance (task_id=None — exists before tasks are created)
        instance = AgentInstance(
            job_id=job.id,
            agent_definition_name="PlannerAgent",
            status=AgentInstanceStatus.CREATED,
        )
        session.add(instance)
        session.flush()

        EventEmitter.emit_sync(
            session,
            "AGENT_SPAWNED",
            {"agent_type": "PlannerAgent"},
            job_id=job.id,
            agent_instance_id=instance.id,
        )
        session.commit()

        # Dispatch the planning task to the agents queue
        from aios.workers.agent_tasks import run_planner  # avoid circular import
        run_planner.apply_async(args=[str(job.id), str(instance.id)], queue="agents")

    except Exception as exc:
        session.rollback()
        logger.exception("dispatch_job failed for job {}: {}", job_id, exc)
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# resolve_dag
# ---------------------------------------------------------------------------

@celery_app.task(name="aios.workers.scheduler_tasks.resolve_dag", bind=True)
def resolve_dag(self, job_id: str) -> None:
    """
    After any task completes, scan the DAG for newly unblocked tasks.
    Transitions WAITING tasks with all deps COMPLETED to READY and dispatches them.
    """
    session = get_sync_session()
    try:
        job = session.get(Job, uuid.UUID(job_id))
        if not job:
            return

        tasks = session.scalars(
            select(Task).where(
                Task.job_id == uuid.UUID(job_id),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.WAITING]),
            )
        ).all()

        dispatched = []
        for task in tasks:
            dep_ids = [d.depends_on_task_id for d in task.dependencies]
            if not dep_ids:
                # No dependencies → immediately ready
                _mark_ready_and_dispatch(session, task, job)
                dispatched.append(task.id)
                continue

            dep_statuses = session.scalars(
                select(Task.status).where(Task.id.in_(dep_ids))
            ).all()

            if all(s == TaskStatus.COMPLETED for s in dep_statuses):
                _mark_ready_and_dispatch(session, task, job)
                dispatched.append(task.id)

        # Check if all tasks are done → complete or fail the job
        all_tasks = session.scalars(
            select(Task).where(Task.job_id == uuid.UUID(job_id))
        ).all()

        if all_tasks and all(t.status == TaskStatus.COMPLETED for t in all_tasks):
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(timezone.utc)
            # Aggregate outputs from all tasks into job.output_payload
            job.output_payload = {
                t.title: t.output_result
                for t in all_tasks
                if t.output_result
            }
            EventEmitter.emit_sync(session, "JOB_COMPLETED", {}, job_id=job.id)

        elif any(t.status == TaskStatus.FAILED for t in all_tasks):
            failed_retrying = [
                t for t in all_tasks
                if t.status in (TaskStatus.FAILED, TaskStatus.RETRYING)
                and t.attempt_count >= t.max_attempts
            ]
            if failed_retrying:
                job.status = JobStatus.FAILED
                job.completed_at = datetime.now(timezone.utc)
                EventEmitter.emit_sync(
                    session, "JOB_FAILED", {"reason": "task_failed"}, job_id=job.id
                )

        session.commit()
        logger.info("resolve_dag: job {} — {} tasks dispatched", job_id, len(dispatched))

    except Exception as exc:
        session.rollback()
        logger.exception("resolve_dag failed for job {}: {}", job_id, exc)
    finally:
        session.close()


def _mark_ready_and_dispatch(session, task: Task, job: Job) -> None:
    task.status = TaskStatus.READY
    session.flush()
    EventEmitter.emit_sync(session, "TASK_READY", {"title": task.title}, job_id=job.id, task_id=task.id)
    dispatch_task.apply_async(args=[str(task.id)], queue="scheduler")


# ---------------------------------------------------------------------------
# dispatch_task
# ---------------------------------------------------------------------------

@celery_app.task(name="aios.workers.scheduler_tasks.dispatch_task", bind=True, max_retries=3)
def dispatch_task(self, task_id: str) -> None:
    """Assign a READY task to an AgentInstance and enqueue run_agent_task."""
    session = get_sync_session()
    try:
        task = session.get(Task, uuid.UUID(task_id))
        if not task or task.status != TaskStatus.READY:
            return

        instance = AgentInstance(
            job_id=task.job_id,
            task_id=task.id,
            agent_definition_name=task.agent_type or "ResearchAgent",
            status=AgentInstanceStatus.CREATED,
        )
        session.add(instance)
        session.flush()

        task.status = TaskStatus.ASSIGNED
        task.agent_instance_id = instance.id
        session.flush()

        EventEmitter.emit_sync(
            session,
            "AGENT_SPAWNED",
            {"agent_type": instance.agent_definition_name},
            job_id=task.job_id,
            task_id=task.id,
            agent_instance_id=instance.id,
        )
        session.commit()

        from aios.workers.agent_tasks import run_agent_task  # avoid circular import
        run_agent_task.apply_async(args=[task_id, str(instance.id)], queue="agents")

    except Exception as exc:
        session.rollback()
        logger.exception("dispatch_task failed for task {}: {}", task_id, exc)
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()
