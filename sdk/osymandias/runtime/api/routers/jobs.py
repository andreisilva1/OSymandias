import asyncio
import json
import uuid
from datetime import datetime, timezone

import redis.asyncio as aioredis
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from osymandias.runtime.api.deps import get_db, get_or_404
from osymandias.runtime.api.schemas.job import (
    AgentInstanceResponse,
    JobCreate,
    JobResponse,
    MessageResponse,
    TaskResponse,
    ToolCallResponse,
)
from osymandias.runtime.config import settings
from osymandias.runtime.core.event_emitter import EventEmitter
from osymandias.runtime.models import Job, JobPriority, JobStatus, Task, TaskStatus

router = APIRouter(prefix="/api/v1/jobs", tags=["jobs"])


@router.post("", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def create_job(body: JobCreate, db: AsyncSession = Depends(get_db)):
    job = Job(
        title=body.title,
        description=body.description,
        priority=JobPriority(body.priority),
        input_payload=body.input_payload,
        retry_policy=body.retry_policy.model_dump(),
        max_tokens=body.max_tokens,
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
    return await get_or_404(db, Job, job_id, "Job")


@router.post("/{job_id}/resubmit", response_model=JobResponse, status_code=status.HTTP_201_CREATED)
async def resubmit_job(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    original = await get_or_404(db, Job, job_id, "Job")

    job = Job(
        title=original.title,
        description=original.description,
        priority=original.priority,
        input_payload=original.input_payload,
        retry_policy=original.retry_policy,
        max_tokens=original.max_tokens,
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
    job = await get_or_404(db, Job, job_id, "Job")
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


@router.post("/{job_id}/tasks/{task_id}/approve")
async def approve_task(job_id: uuid.UUID, task_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    """Approve a task waiting in HUMAN_REVIEW so the scheduler dispatches it."""
    task = await get_or_404(db, Task, task_id, "Task")
    if task.status != TaskStatus.HUMAN_REVIEW:
        raise HTTPException(status_code=400, detail=f"Task is not awaiting approval (status {task.status})")

    task.status = TaskStatus.READY
    await EventEmitter.emit(db, "TASK_APPROVED", {"title": task.title}, job_id=task.job_id, task_id=task.id)
    await db.commit()

    from osymandias.runtime.workers.celery_app import celery_app
    celery_app.send_task(
        "osymandias.runtime.workers.scheduler_tasks.dispatch_task",
        args=[str(task.id)], queue="scheduler",
    )
    return {"status": "approved", "task_id": str(task.id)}


@router.get("/{job_id}/messages", response_model=list[MessageResponse])
async def get_job_messages(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import Message
    result = await db.execute(
        select(Message).where(Message.job_id == job_id).order_by(Message.sent_at)
    )
    return result.scalars().all()


@router.get("/{job_id}/tool-calls", response_model=list[ToolCallResponse])
async def get_job_tool_calls(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import ToolCall
    result = await db.execute(
        select(ToolCall).where(ToolCall.job_id == job_id).order_by(ToolCall.created_at)
    )
    return result.scalars().all()


@router.get("/{job_id}/agents", response_model=list[AgentInstanceResponse])
async def get_job_agent_instances(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    from osymandias.runtime.models import AgentInstance
    result = await db.execute(
        select(AgentInstance).where(AgentInstance.job_id == job_id).order_by(AgentInstance.created_at)
    )
    return result.scalars().all()


@router.get("/{job_id}/output")
async def get_job_output(job_id: uuid.UUID, db: AsyncSession = Depends(get_db)):
    job = await get_or_404(db, Job, job_id, "Job")
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
