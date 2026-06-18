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

        from osymandias.runtime.models.agent_definition import AGENT_KIND_EXTERNAL
        definition = session.get(
            __import__("osymandias.runtime.models", fromlist=["AgentDefinition"]).AgentDefinition,
            task.agent_type or "ResearchAgent",
        )

        if definition and definition.agent_kind == AGENT_KIND_EXTERNAL:
            result = _run_external_agent(definition, task, session)
        else:
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
            "available_agents": _build_agent_catalogue(session),
        }
        result = agent.run_sync(extra_context=context)

        # Create tasks from plan
        from osymandias.runtime.models import Task, TaskDependency, TaskStatus
        task_map: dict[str, Task] = {}

        # Normalize LLM-returned agent type names to registered agent_definition names.
        # Seed with builtin aliases; then add exact names for every registered agent
        # so external agents are matched case-insensitively even if the LLM drops/adds
        # capitalisation.
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
        # Extend map with every registered agent (handles external agents)
        try:
            from sqlalchemy import select as _select
            from osymandias.runtime.models import AgentDefinition as _AD
            for _ad in session.scalars(_select(_AD).where(_AD.is_active == True)).all():  # noqa: E712
                _AGENT_TYPE_MAP[_ad.name.lower()] = _ad.name
        except Exception:
            pass

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


def _build_agent_catalogue(session) -> str:
    """Return a formatted list of all active agent types for the PlannerAgent prompt."""
    from sqlalchemy import select
    from osymandias.runtime.models import AgentDefinition
    from osymandias.runtime.models.agent_definition import AGENT_KIND_EXTERNAL

    _EXCLUDE = {"PlannerAgent", "EvaluatorAgent"}
    try:
        defs = session.scalars(
            select(AgentDefinition).where(AgentDefinition.is_active == True)  # noqa: E712
        ).all()
    except Exception:
        return "ResearchAgent, WriterAgent, AnalystAgent"

    lines = []
    for ad in defs:
        if ad.name in _EXCLUDE:
            continue
        kind = "external" if ad.agent_kind == AGENT_KIND_EXTERNAL else "builtin"
        framework = f" [{ad.framework}]" if getattr(ad, "framework", None) else ""
        desc = ad.description or ""
        lines.append(f"- {ad.name}{framework} ({kind}): {desc}")

    return "\n".join(lines) if lines else "ResearchAgent, WriterAgent, AnalystAgent"


def _resolve_callable_ref(callable_ref: str) -> None:
    """Import the module that owns callable_ref so its @osy.agent decorators register."""
    import importlib
    import sys
    from pathlib import Path

    cwd = str(Path.cwd())
    if cwd not in sys.path:
        sys.path.insert(0, cwd)

    module_path = callable_ref.rsplit(".", 1)[0]
    for attempt in (module_path, module_path.rsplit(".", 1)[0] if "." in module_path else None):
        if not attempt:
            continue
        try:
            importlib.import_module(attempt)
            return
        except ImportError:
            continue


def _run_external_agent(definition, task, session) -> dict:
    """Dispatch to an @osy.agent-registered callable, injecting OsyContext if declared."""
    from osymandias.decorator import _AGENT_REGISTRY
    from osymandias.runtime.context import OsyContext

    entry = _AGENT_REGISTRY.get(definition.name)
    if not entry and definition.callable_ref:
        _resolve_callable_ref(definition.callable_ref)
        entry = _AGENT_REGISTRY.get(definition.name)

    if not entry:
        raise RuntimeError(
            f"External agent '{definition.name}' is registered in the DB but not found in "
            f"_AGENT_REGISTRY — ensure the module containing @osy.agent('{definition.name}') "
            f"is importable from the working directory (check agent_modules in osymandias.toml)."
        )

    ctx = OsyContext(job_id=task.job_id, task_id=task.id, session=session)
    task_description = (task.input_context or {}).get("task_description", task.description or "")

    import inspect
    sig = inspect.signature(entry.fn)
    if "ctx" in sig.parameters:
        raw_result = entry.fn(task=task_description, ctx=ctx)
    else:
        raw_result = entry.fn(task=task_description)

    result = raw_result if isinstance(raw_result, dict) else {"result": raw_result}

    if definition.output_schema:
        result = _validate_output(result, definition.output_schema, definition.name)

    return result


def _validate_output(result: dict, schema: dict, agent_name: str) -> dict:
    """Validate result against JSON Schema. On failure, annotate but don't raise."""
    try:
        import jsonschema
        jsonschema.validate(instance=result, schema=schema)
    except ImportError:
        pass  # jsonschema not installed — skip validation
    except Exception as exc:
        logger.warning("Output validation failed for {}: {}", agent_name, exc)
        result["_validation_errors"] = str(exc)
    return result


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
