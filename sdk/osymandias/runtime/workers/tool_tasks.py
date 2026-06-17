"""
Tool tasks — execute tool calls in isolation on the 'tools' queue.
"""
import uuid
from datetime import datetime, timezone

from celery import shared_task
from loguru import logger

from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.db.sync_session import get_sync_session
from osymandias.runtime.models import ToolCall, ToolCallStatus
from osymandias.runtime.workers.celery_app import celery_app


@celery_app.task(
    name="aios.workers.tool_tasks.execute_tool_call",
    bind=True,
    max_retries=2,
    soft_time_limit=60,
    time_limit=90,
)
def execute_tool_call(self, tool_call_id: str) -> dict:
    """
    Execute a single tool call.
    Returns the output_result dict so the agent worker can retrieve it
    via Celery result backend.
    """
    session = get_sync_session()
    try:
        tc = session.get(ToolCall, uuid.UUID(tool_call_id))
        if not tc:
            raise ValueError(f"ToolCall {tool_call_id} not found")

        tc.status = ToolCallStatus.RUNNING
        session.flush()

        EventEmitter.emit_sync(
            session,
            "TOOL_CALL_STARTED",
            {"tool_name": tc.tool_name, "input_args": tc.input_args},
            job_id=tc.job_id,
            task_id=tc.task_id,
            agent_instance_id=tc.agent_instance_id,
        )
        session.commit()

        start = datetime.now(timezone.utc)

        # Delegate to the tool registry
        from osymandias.runtime.tools.executor import ToolExecutor
        result = ToolExecutor.run_sync(
            tool_name=tc.tool_name,
            input_args=tc.input_args,
            agent_instance_id=tc.agent_instance_id,
            session=session,
        )

        duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

        session.refresh(tc)
        tc.status = ToolCallStatus.SUCCESS
        tc.output_result = result
        tc.duration_ms = duration_ms
        tc.completed_at = datetime.now(timezone.utc)
        session.flush()

        EventEmitter.emit_sync(
            session,
            "TOOL_CALL_COMPLETED",
            {"tool_name": tc.tool_name, "duration_ms": duration_ms},
            job_id=tc.job_id,
            task_id=tc.task_id,
            agent_instance_id=tc.agent_instance_id,
            duration_ms=duration_ms,
        )
        session.commit()
        return result

    except Exception as exc:
        session.rollback()
        session2 = get_sync_session()
        try:
            tc2 = session2.get(ToolCall, uuid.UUID(tool_call_id))
            if tc2:
                tc2.status = ToolCallStatus.FAILED
                tc2.error_message = str(exc)
                tc2.completed_at = datetime.now(timezone.utc)
                EventEmitter.emit_sync(
                    session2,
                    "TOOL_CALL_FAILED",
                    {"tool_name": tc2.tool_name, "error": str(exc)},
                    job_id=tc2.job_id,
                    task_id=tc2.task_id,
                    agent_instance_id=tc2.agent_instance_id,
                )
                session2.commit()
        finally:
            session2.close()

        logger.exception("execute_tool_call failed for {}: {}", tool_call_id, exc)
        raise self.retry(exc=exc, countdown=3)
    finally:
        session.close()
