"""
Scheduler tasks — orchestrate job lifecycle and DAG resolution.
All tasks run on the 'scheduler' queue (single worker, no race conditions).
"""
import uuid
from datetime import datetime, timezone

from celery import shared_task
from loguru import logger
from sqlalchemy import select

from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import (
    AgentDefinition,
    AgentInstance,
    AgentInstanceStatus,
    Job,
    JobStatus,
    Task,
    TaskStatus,
)
from osymandias.runtime.models.task import TaskDependency
from osymandias.runtime.workers.celery_app import celery_app


# ---------------------------------------------------------------------------
# dispatch_job
# ---------------------------------------------------------------------------

@celery_app.task(name="osymandias.runtime.workers.scheduler_tasks.dispatch_job", bind=True, max_retries=3)
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

        # __task_plan__ override: bypass PlannerAgent and directly create tasks.
        # Useful for tests and programmatic job submission.
        task_plan = (job.input_payload or {}).get("__task_plan__")
        if task_plan:
            _apply_task_plan(session, job, task_plan)
            session.commit()
            resolve_dag.apply_async(args=[str(job.id)], queue="scheduler")
            return

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

        celery_app.send_task(
            "osymandias.runtime.workers.agent_tasks.run_planner",
            args=[str(job.id), str(instance.id)],
            queue="agents",
        )

    except Exception as exc:
        session.rollback()
        logger.exception("dispatch_job failed for job {}: {}", job_id, exc)
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()


# ---------------------------------------------------------------------------
# resolve_dag
# ---------------------------------------------------------------------------

@celery_app.task(name="osymandias.runtime.workers.scheduler_tasks.resolve_dag", bind=True)
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

        # Stop dispatching once the job has reached a terminal state (e.g. a
        # sibling task tripped the token budget). Prevents new agent spawns.
        if job.status in (JobStatus.BUDGET_EXCEEDED, JobStatus.CANCELLED, JobStatus.FAILED, JobStatus.COMPLETED):
            return

        tasks = session.scalars(
            select(Task).where(
                Task.job_id == uuid.UUID(job_id),
                Task.status.in_([TaskStatus.PENDING, TaskStatus.WAITING]),
            )
        ).all()

        dispatched = []
        for task in tasks:
            # Explicit SQL for dep IDs — avoids SQLAlchemy lazy-load returning
            # stale empty collections when the session first loads a task.
            dep_ids = session.scalars(
                select(TaskDependency.depends_on_task_id).where(
                    TaskDependency.task_id == task.id
                )
            ).all()

            if not dep_ids:
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
            job.output_payload = {
                t.title: t.output_result
                for t in all_tasks
                if t.output_result
            }
            EventEmitter.emit_sync(session, "JOB_COMPLETED", {}, job_id=job.id)

        elif any(t.status == TaskStatus.FAILED for t in all_tasks):
            # A task is definitively failed when:
            #   • status=FAILED (set by _handle_task_failure — no retry attempted), or
            #   • status=RETRYING but all attempts exhausted (set by heartbeat monitor).
            # In both cases the job cannot complete.
            still_active = [
                t for t in all_tasks
                if t.status in (TaskStatus.PENDING, TaskStatus.WAITING, TaskStatus.READY,
                                TaskStatus.ASSIGNED, TaskStatus.RUNNING, TaskStatus.HUMAN_REVIEW)
                or (t.status == TaskStatus.RETRYING and t.attempt_count < t.max_attempts)
            ]
            if not still_active:
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


def _apply_task_plan(session, job: Job, task_plan: list[dict]) -> None:
    """Create Task rows from a pre-defined plan, bypassing PlannerAgent."""
    from osymandias.runtime.models.task import TaskDependency

    title_to_task: dict[str, Task] = {}
    for td in task_plan:
        task = Task(
            job_id=job.id,
            title=td["title"],
            description=td.get("description", ""),
            status=TaskStatus.PENDING,
            agent_type=td.get("agent_type", "ResearchAgent"),
            input_context={
                "task_description": td.get("description", ""),
                "job_description": job.description or "",
            },
            max_attempts=td.get("max_attempts", 3),
            requires_approval=td.get("requires_approval", False),
        )
        session.add(task)
        session.flush()
        title_to_task[td["title"]] = task
        EventEmitter.emit_sync(
            session, "TASK_CREATED",
            {"title": task.title, "agent_type": task.agent_type},
            job_id=job.id, task_id=task.id,
        )

    # Wire dependencies after all tasks are created
    for td in task_plan:
        task = title_to_task[td["title"]]
        for dep_title in td.get("depends_on", []):
            dep_task = title_to_task.get(dep_title)
            if dep_task:
                session.add(TaskDependency(task_id=task.id, depends_on_task_id=dep_task.id))
                task.status = TaskStatus.WAITING

    session.flush()


def _mark_ready_and_dispatch(session, task: Task, job: Job) -> None:
    # Human-in-the-loop gate: hold the task for approval instead of dispatching.
    # Two sources: per-task override OR a per-agent policy on its AgentDefinition.
    agent_def = session.get(AgentDefinition, task.agent_type) if task.agent_type else None
    needs_approval = task.requires_approval or bool(agent_def and agent_def.requires_approval)
    if needs_approval:
        task.status = TaskStatus.HUMAN_REVIEW
        session.flush()
        EventEmitter.emit_sync(
            session, "TASK_AWAITING_APPROVAL", {"title": task.title},
            job_id=job.id, task_id=task.id,
        )
        return
    task.status = TaskStatus.READY
    session.flush()
    EventEmitter.emit_sync(session, "TASK_READY", {"title": task.title}, job_id=job.id, task_id=task.id)
    dispatch_task.apply_async(args=[str(task.id)], queue="scheduler")


# ---------------------------------------------------------------------------
# dispatch_task
# ---------------------------------------------------------------------------

@celery_app.task(name="osymandias.runtime.workers.scheduler_tasks.dispatch_task", bind=True, max_retries=3)
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

        celery_app.send_task(
            "osymandias.runtime.workers.agent_tasks.run_agent_task",
            args=[task_id, str(instance.id)],
            queue="agents",
        )

    except Exception as exc:
        session.rollback()
        logger.exception("dispatch_task failed for task {}: {}", task_id, exc)
        raise self.retry(exc=exc, countdown=5)
    finally:
        session.close()
