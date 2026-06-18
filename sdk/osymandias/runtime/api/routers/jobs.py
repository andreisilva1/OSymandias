import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db
from osymandias.runtime.api.schemas.job import JobCreate, JobResponse, TaskResponse
from osymandias.runtime.config import settings
from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.models import Job, JobPriority, JobStatus, Task

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(
        title=body.title,
        description=body.description,
        priority=JobPriority(body.priority),
        input_payload=body.input_payload,
        retry_policy=body.retry_policy.model_dump(),
    )
    db.add(job)
    await db.flush()

    await EventEmitter.emit(db, "JOB_CREATED", {"title": job.title}, job_id=job.id)
    await db.commit()
    await db.refresh(job)

    # Enqueue dispatch_job
    from osymandias.runtime.workers.scheduler_tasks import dispatch_job
    dispatch_job.apply_async(args=[str(job.id)], queue="scheduler")

    return job


@router.get("", response_model=list[JobResponse])
async def list_jobs(
    status_filter: str | None = None,
    limit: int = Query(default=50, le=1000),
    offset: int = 0,
    db: AsyncSession = Depends(get_db),
):
    if status_filter is not None:
        valid = {s.value for s in JobStatus}
        if status_filter not in valid:
            raise HTTPException(status_code=400, detail=f"Invalid status '{status_filter}'. Valid values: {sorted(valid)}")
    q = select(Job).order_by(Job.created_at.desc()).limit(limit).offset(offset)
    if status_filter:
        q = q.where(Job.status == status_filter)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/{job_id}", response_model=JobResponse)
async def get_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return job


@router.post("/{job_id}/resubmit", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def resubmit_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    original = await db.get(Job, job_id)
    if not original:
        raise HTTPException(status_code=404, detail="Job not found")

    job = Job(
        title=original.title,
        description=original.description,
        priority=original.priority,
        input_payload=original.input_payload,
        retry_policy=original.retry_policy,
    )
    db.add(job)
    await db.flush()

    await EventEmitter.emit(db, "JOB_CREATED", {"title": job.title, "resubmitted_from": str(job_id)}, job_id=job.id)
    await db.commit()
    await db.refresh(job)

    from osymandias.runtime.workers.scheduler_tasks import dispatch_job
    dispatch_job.apply_async(args=[str(job.id)], queue="scheduler")

    return job


@router.patch("/{job_id}/cancel", response_model=JobResponse)
async def cancel_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(status_code=400, detail=f"Cannot cancel job with status {job.status}")

    job.status = JobStatus.CANCELLED
    job.completed_at = datetime.now(timezone.utc)
    await EventEmitter.emit(db, "JOB_CANCELLED", {}, job_id=job.id)
    await db.commit()
    await db.refresh(job)
    return job


@router.get("/{job_id}/tasks", response_model=list[TaskResponse])
async def get_job_tasks(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models.task import TaskDependency
    tasks_result = await db.execute(select(Task).where(Task.job_id == job_id))
    tasks = tasks_result.scalars().all()

    # Load dependency titles for each task
    if tasks:
        task_ids = [t.id for t in tasks]
        id_to_title = {t.id: t.title for t in tasks}
        deps_result = await db.execute(
            select(TaskDependency).where(TaskDependency.task_id.in_(task_ids))
        )
        deps_by_task: dict[uuid.UUID, list[str]] = {}
        for dep in deps_result.scalars().all():
            deps_by_task.setdefault(dep.task_id, []).append(
                id_to_title.get(dep.depends_on_task_id, str(dep.depends_on_task_id))
            )

        responses = []
        for task in tasks:
            resp = TaskResponse.model_validate(task)
            resp.depends_on = deps_by_task.get(task.id, [])
            responses.append(resp)
        return responses

    return []


@router.get("/{job_id}/messages")
async def get_job_messages(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import Message
    result = await db.execute(
        select(Message).where(Message.job_id == job_id).order_by(Message.sent_at)
    )
    msgs = result.scalars().all()
    return [
        {
            "id": str(m.id),
            "job_id": str(m.job_id),
            "sender_agent_instance_id": str(m.sender_agent_instance_id),
            "receiver_agent_instance_id": str(m.receiver_agent_instance_id) if m.receiver_agent_instance_id else None,
            "receiver_agent_type": m.receiver_agent_type,
            "message_type": m.message_type,
            "subject": m.subject,
            "content": m.content,
            "is_read": m.is_read,
            "sent_at": m.sent_at.isoformat(),
            "read_at": m.read_at.isoformat() if m.read_at else None,
        }
        for m in msgs
    ]


@router.get("/{job_id}/tool-calls")
async def get_job_tool_calls(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import ToolCall
    result = await db.execute(
        select(ToolCall).where(ToolCall.job_id == job_id).order_by(ToolCall.created_at)
    )
    tcs = result.scalars().all()
    return [
        {
            "id": str(tc.id),
            "task_id": str(tc.task_id),
            "agent_instance_id": str(tc.agent_instance_id),
            "tool_name": tc.tool_name,
            "input_args": tc.input_args,
            "output_result": tc.output_result,
            "status": tc.status,
            "attempt_count": tc.attempt_count,
            "error_message": tc.error_message,
            "created_at": tc.created_at.isoformat(),
            "completed_at": tc.completed_at.isoformat() if tc.completed_at else None,
            "duration_ms": tc.duration_ms,
            "estimated_cost": float(tc.estimated_cost) if tc.estimated_cost else 0.0,
        }
        for tc in tcs
    ]


@router.get("/{job_id}/agents")
async def get_job_agent_instances(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import AgentInstance
    result = await db.execute(
        select(AgentInstance).where(AgentInstance.job_id == job_id).order_by(AgentInstance.created_at)
    )
    instances = result.scalars().all()
    return [
        {
            "id": str(i.id),
            "job_id": str(i.job_id),
            "task_id": str(i.task_id) if i.task_id else None,
            "agent_definition_name": i.agent_definition_name,
            "status": i.status,
            "iteration_count": i.iteration_count,
            "tokens_used": i.tokens_used,
            "tool_calls_count": i.tool_calls_count,
            "last_heartbeat_at": i.last_heartbeat_at.isoformat() if i.last_heartbeat_at else None,
            "created_at": i.created_at.isoformat(),
            "terminated_at": i.terminated_at.isoformat() if i.terminated_at else None,
        }
        for i in instances
    ]


@router.get("/{job_id}/output")
async def get_job_output(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await db.get(Job, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return {"output": job.output_payload}


@router.get("/{job_id}/events")
async def stream_job_events(job_id: uuid.UUID):
    """SSE endpoint — streams events for a specific job in real time."""

    async def event_generator():
        r = aioredis.from_url(settings.osy_redis_url, decode_responses=True)
        pubsub = r.pubsub()
        await pubsub.subscribe(f"events:job:{job_id}")

        try:
            yield ":\n\n"  # immediate keepalive

            while True:
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=15.0
                )
                if message is not None and message["type"] == "message":
                    data = message["data"]
                    try:
                        parsed = json.loads(data)
                        event_id = parsed.get("id", "")
                        event_type = parsed.get("event_type", "event")
                        yield f"id: {event_id}\nevent: {event_type}\ndata: {data}\n\n"
                    except Exception:
                        yield f"data: {data}\n\n"
                else:
                    # keepalive comment to prevent proxy/browser timeout
                    yield ":\n\n"

                await asyncio.sleep(0)

        except asyncio.CancelledError:
            pass
        finally:
            await pubsub.unsubscribe(f"events:job:{job_id}")
            await r.aclose()

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )
