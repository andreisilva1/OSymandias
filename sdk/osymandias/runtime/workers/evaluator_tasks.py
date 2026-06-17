"""
Evaluator tasks — assess quality of agent outputs.
"""
import uuid

from loguru import logger

from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import AgentInstance, AgentInstanceStatus, Task, TaskStatus
from osymandias.runtime.workers.celery_app import celery_app


@celery_app.task(
    name="aios.workers.evaluator_tasks.evaluate_output",
    bind=True,
    max_retries=1,
    soft_time_limit=90,
    time_limit=120,
)
def evaluate_output(self, task_id: str) -> dict:
    """
    Spawns an EvaluatorAgent, scores the task output, and optionally
    triggers a retry with feedback injected into the next context.
    """
    session = get_sync_session()
    try:
        task = session.get(Task, uuid.UUID(task_id))
        if not task or not task.output_result:
            logger.warning("evaluate_output: task {} has no output, skipping", task_id)
            return {"skipped": True}

        EventEmitter.emit_sync(
            session,
            "EVALUATION_STARTED",
            {"task_id": task_id},
            job_id=task.job_id,
            task_id=task.id,
        )
        session.commit()

        # Spawn EvaluatorAgent inline (short task, no separate dispatch needed)
        from osymandias.runtime.agents.base_agent import BaseAgent
        agent = BaseAgent(
            agent_definition_name="EvaluatorAgent",
            job_id=task.job_id,
            task_id=task.id,
            session=session,
        )

        criteria = task.input_context.get("evaluation_criteria", "Be accurate and complete.")
        context = {
            "output": task.output_result,
            "criteria": criteria,
        }
        result = agent.run_sync(context)

        score = float(result.get("score", 0.0))
        feedback = result.get("feedback", "")
        passed = result.get("passed", score >= 0.7)

        task.evaluation_score = score
        task.evaluation_feedback = feedback
        session.flush()

        EventEmitter.emit_sync(
            session,
            "EVALUATION_COMPLETED",
            {"score": score, "passed": passed, "feedback": feedback[:200]},
            job_id=task.job_id,
            task_id=task.id,
        )

        # If failed evaluation and retries remain, requeue task with feedback
        if not passed and task.attempt_count < task.max_attempts:
            task.status = TaskStatus.RETRYING
            task.attempt_count += 1
            task.input_context["evaluation_feedback"] = feedback
            session.flush()
            EventEmitter.emit_sync(
                session,
                "TASK_RETRYING",
                {"attempt": task.attempt_count, "reason": "evaluation_failed"},
                job_id=task.job_id,
                task_id=task.id,
            )
            session.commit()

            from osymandias.runtime.workers.scheduler_tasks import dispatch_task
            dispatch_task.apply_async(args=[task_id], queue="scheduler", countdown=5)
        else:
            session.commit()
            # Trigger DAG resolution
            from osymandias.runtime.workers.scheduler_tasks import resolve_dag
            resolve_dag.apply_async(args=[str(task.job_id)], queue="scheduler")

        return {"score": score, "passed": passed}

    except Exception as exc:
        session.rollback()
        logger.exception("evaluate_output failed for task {}: {}", task_id, exc)
        raise self.retry(exc=exc, countdown=10)
    finally:
        session.close()
