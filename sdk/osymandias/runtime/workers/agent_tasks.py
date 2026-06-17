"""
Agent tasks — run agent loops inside Celery workers.
"""
import uuid
from datetime import datetime, timezone

from loguru import logger

from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import Job, JobStatus, Task, TaskStatus
from osymandias.runtime.workers.celery_app import celery_app


@celery_app.task(
    name="osymandias.runtime.workers.agent_tasks.run_agent_task",
    bind=True,
    max_retries=0,  # retry logic is handled by scheduler via heartbeat monitor
    soft_time_limit=130,
    time_limit=150,
)
def run_agent_task(self, task_id: str, agent_instance_id: str) -> None:
    """Execute a task using the assigned agent instance."""
    session = get_sync_session()
    job_id: uuid.UUID | None = None
    try:
        task = session.get(Task, uuid.UUID(task_id))
        if not task:
            logger.error("run_agent_task: task {} not found", task_id)
            return

        job_id = task.job_id  # capture early so except block can use it

        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        session.flush()

        EventEmitter.emit_sync(
            session,
            "TASK_STARTED",
            {"title": task.title, "agent_type": task.agent_type},
            job_id=task.job_id,
            task_id=task.id,
        )
        session.commit()

        from osymandias.runtime.agents.base_agent import BaseAgent
        agent = BaseAgent(
            agent_definition_name=task.agent_type or "ResearchAgent",
            job_id=task.job_id,
            task_id=task.id,
            session=session,
            agent_instance_id=uuid.UUID(agent_instance_id),
        )

        result = agent.run_sync()

        session.refresh(task)
        task.status = TaskStatus.COMPLETED
        task.output_result = result
        task.completed_at = datetime.now(timezone.utc)
        session.flush()

        # Auto-propagate task output to job memory so downstream agents
        # can read it without the agent needing to call write_to_job_memory.
        # Stored under task.title (e.g. "Research") and task.agent_type (e.g. "ResearchAgent").
        # embed=True enables semantic search via search_memory.
        try:
            from osymandias.runtime.memory.manager import MemoryManager
            from osymandias.runtime.models.memory_entry import MemoryScope
            for key in {task.title, task.agent_type}:
                if key:
                    MemoryManager.write_sync(
                        session=session,
                        scope=MemoryScope.JOB,
                        scope_id=task.job_id,
                        key=key,
                        value=result,
                        embed=False,
                    )
            session.flush()
        except Exception as mem_exc:
            logger.warning("auto-propagate memory failed for task {}: {}", task_id, mem_exc)

        EventEmitter.emit_sync(
            session,
            "TASK_COMPLETED",
            {"title": task.title},
            job_id=task.job_id,
            task_id=task.id,
        )
        session.commit()

        _update_job_totals(session, task.job_id)
        session.commit()  # persist token/cost aggregation

        if task.output_schema:
            from osymandias.runtime.workers.evaluator_tasks import evaluate_output
            evaluate_output.apply_async(args=[task_id], queue="evaluator", countdown=1)
        else:
            from osymandias.runtime.workers.scheduler_tasks import resolve_dag
            resolve_dag.apply_async(args=[str(task.job_id)], queue="scheduler")

    except Exception as exc:
        session.rollback()
        if job_id:
            try:
                _update_job_totals(session, job_id)
                session.commit()
            except Exception:
                session.rollback()
                logger.warning("run_agent_task: could not aggregate job totals for job {}", job_id)
        _handle_task_failure(task_id, agent_instance_id, str(exc))
        logger.exception("run_agent_task failed for task {}: {}", task_id, exc)
    finally:
        session.close()


@celery_app.task(
    name="osymandias.runtime.workers.agent_tasks.run_planner",
    bind=True,
    max_retries=2,
    soft_time_limit=90,
    time_limit=120,
)
def run_planner(self, job_id: str, agent_instance_id: str) -> None:
    """Run PlannerAgent to decompose a job into tasks."""
    session = get_sync_session()
    try:
        job = session.get(Job, uuid.UUID(job_id))
        if not job:
            return

        from osymandias.runtime.agents.base_agent import BaseAgent
        agent = BaseAgent(
            agent_definition_name="PlannerAgent",
            job_id=job.id,
            task_id=None,
            session=session,
            agent_instance_id=uuid.UUID(agent_instance_id),
        )

        context = {
            "job_description": job.description or job.title,
            "input_payload": job.input_payload,
        }
        result = agent.run_sync(extra_context=context)

        # Create tasks from plan
        from osymandias.runtime.models import Task, TaskDependency, TaskStatus
        task_map: dict[str, Task] = {}

        # Normalize LLM-returned agent type names to registered agent_definition names
        _AGENT_TYPE_MAP: dict[str, str] = {
            "researchagent": "ResearchAgent",
            "researcher": "ResearchAgent",
            "research": "ResearchAgent",
            "writeragent": "WriterAgent",
            "writer": "WriterAgent",
            "writing": "WriterAgent",
            "analystagent": "AnalystAgent",
            "analyst": "AnalystAgent",
            "analysis": "AnalystAgent",
            "evaluatoragent": "EvaluatorAgent",
            "evaluator": "EvaluatorAgent",
            "planneragent": "PlannerAgent",
            "planner": "PlannerAgent",
        }

        def _normalize_agent_type(raw: str) -> str:
            return _AGENT_TYPE_MAP.get(raw.lower().strip(), raw)

        for task_def in result.get("tasks", []):
            task = Task(
                job_id=job.id,
                title=task_def["title"],
                description=task_def.get("description", ""),
                status=TaskStatus.PENDING,
                agent_type=_normalize_agent_type(task_def.get("agent_type", "ResearchAgent")),
                input_context={
                    "task_description": task_def.get("description", ""),
                    "job_description": job.description or job.title,
                    "evaluation_criteria": task_def.get("acceptance_criteria", ""),
                    "input_payload": job.input_payload,
                },
                max_attempts=job.retry_policy.get("max_attempts", 3),
            )
            session.add(task)
            session.flush()
            task_map[task_def["title"]] = task

            EventEmitter.emit_sync(
                session,
                "TASK_CREATED",
                {"title": task.title, "agent_type": task.agent_type},
                job_id=job.id,
                task_id=task.id,
            )

        # Wire dependencies
        for task_def in result.get("tasks", []):
            for dep_title in task_def.get("depends_on", []):
                if dep_title in task_map and task_def["title"] in task_map:
                    dep = TaskDependency(
                        task_id=task_map[task_def["title"]].id,
                        depends_on_task_id=task_map[dep_title].id,
                    )
                    session.add(dep)

        job.status = JobStatus.RUNNING
        session.commit()

        # Start DAG resolution
        from osymandias.runtime.workers.scheduler_tasks import resolve_dag
        resolve_dag.apply_async(args=[job_id], queue="scheduler")

    except Exception as exc:
        session.rollback()
        logger.exception("run_planner failed for job {}: {}", job_id, exc)
        raise self.retry(exc=exc, countdown=10)
    finally:
        session.close()


def _update_job_totals(session, job_id: uuid.UUID) -> None:
    from sqlalchemy import select, func
    from osymandias.runtime.models import AgentInstance, ToolCall
    tokens = session.scalar(
        select(func.coalesce(func.sum(AgentInstance.tokens_used), 0))
        .where(AgentInstance.job_id == job_id)
    ) or 0
    cost = session.scalar(
        select(func.coalesce(func.sum(ToolCall.estimated_cost), 0))
        .where(ToolCall.job_id == job_id)
    ) or 0
    job = session.get(Job, job_id)
    if job:
        job.total_tokens = int(tokens)
        job.estimated_cost = float(cost)
        session.flush()


def _handle_task_failure(task_id: str, agent_instance_id: str, error: str) -> None:
    session = get_sync_session()
    try:
        task = session.get(Task, uuid.UUID(task_id))
        if not task:
            return
        task.status = TaskStatus.FAILED
        task.completed_at = datetime.now(timezone.utc)
        session.flush()
        EventEmitter.emit_sync(
            session,
            "TASK_FAILED",
            {"error": error[:500]},
            job_id=task.job_id,
            task_id=task.id,
        )
        session.commit()

        from osymandias.runtime.workers.scheduler_tasks import resolve_dag
        resolve_dag.apply_async(args=[str(task.job_id)], queue="scheduler")
    except Exception:
        session.rollback()
        logger.exception("_handle_task_failure could not mark task {} as failed", task_id)
    finally:
        session.close()
