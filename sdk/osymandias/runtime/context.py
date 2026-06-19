"""
OsyContext — injected into external @osy.agent callables at execution time.

Provides access to job memory, event emission, and sub-task spawning
without requiring the agent to import internal runtime modules directly.
"""
from __future__ import annotations

import time
import uuid
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session


class OsyContext:
    """Runtime context injected as the ``ctx`` parameter of every ``@osy.agent`` callable.

    All methods operate in the scope of the current job, so agents running in the
    same job automatically share the same memory namespace.

    Example::

        @osy.agent("MyAgent")
        def my_agent(task: str, ctx: OsyContext) -> dict:
            ctx.write_memory("plan", {"step": 1})
            ctx.emit_event("TASK_PROGRESS", {"pct": 10})
            return {"result": "done"}
    """

    def __init__(
        self,
        job_id: uuid.UUID,
        task_id: uuid.UUID | None,
        session: Session,
    ) -> None:
        self.job_id = job_id
        self.task_id = task_id
        self._session = session

    # ------------------------------------------------------------------
    # Memory
    # ------------------------------------------------------------------

    def read_memory(self, key: str) -> dict[str, Any] | None:
        """Return the value stored under *key* in the current job's memory.

        Returns ``None`` if the key has not been written yet.

        Args:
            key: Arbitrary string identifier. Case-sensitive.

        Example::

            data = ctx.read_memory("previous_output")
            if data:
                print(data["summary"])
        """
        from osymandias.runtime.memory.manager import MemoryManager
        from osymandias.runtime.models.memory_entry import MemoryScope
        return MemoryManager.read_sync(
            session=self._session,
            scope=MemoryScope.JOB,
            scope_id=self.job_id,
            key=key,
        )

    def write_memory(self, key: str, value: dict[str, Any]) -> None:
        """Write *value* to job memory under *key*, overwriting any previous value.

        Memory is scoped to the current job — all agents in the same job can
        read what this agent writes. Writes are flushed immediately within the
        current DB transaction.

        Args:
            key:   Arbitrary string identifier.
            value: Any JSON-serialisable dict.

        Example::

            ctx.write_memory("plan", {"steps": ["research", "analyse", "write"]})
        """
        from osymandias.runtime.memory.manager import MemoryManager
        from osymandias.runtime.models.memory_entry import MemoryScope
        MemoryManager.write_sync(
            session=self._session,
            scope=MemoryScope.JOB,
            scope_id=self.job_id,
            key=key,
            value=value,
            embed=False,
        )
        self._session.flush()

    def search_memory(self, query: str, top_k: int = 5) -> list[dict[str, Any]]:
        """Semantic vector search over the current job's memory entries.

        Uses Qdrant embeddings — useful for retrieving relevant past outputs
        without knowing the exact key.

        Args:
            query:  Natural-language search string.
            top_k:  Maximum number of results to return (default 5).

        Returns:
            List of matching memory entry dicts, sorted by relevance.

        Example::

            results = ctx.search_memory("competitor pricing data", top_k=3)
            for entry in results:
                print(entry["key"], entry["value"])
        """
        from osymandias.runtime.memory.manager import MemoryManager
        from osymandias.runtime.models.memory_entry import MemoryScope
        return MemoryManager.search_sync(
            query=query,
            scopes=[MemoryScope.JOB],
            scope_ids=[self.job_id],
            top_k=top_k,
            session=self._session,
        )

    # ------------------------------------------------------------------
    # Events
    # ------------------------------------------------------------------

    def emit_event(self, event: str, data: dict[str, Any]) -> None:
        """Emit an event that is streamed live to the dashboard SSE feed.

        Use this for progress updates, intermediate results, or any custom
        telemetry you want visible in the job's event timeline.

        Common event types (convention, not enforced):
        - ``"TASK_PROGRESS"`` — progress update with a payload dict
        - ``"AGENT_LOG"``     — free-form log entry
        - Any custom string   — appears in the dashboard event feed as-is

        Args:
            event: Event type string shown in the dashboard.
            data:  Any JSON-serialisable dict.

        Example::

            ctx.emit_event("TASK_PROGRESS", {"pct": 50, "step": "analysing"})
            ctx.emit_event("AGENT_LOG", {"message": "found 12 sources"})
        """
        from osymandias.runtime.core.event_emitter import EventEmitter
        EventEmitter.emit_sync(
            self._session,
            event,
            data,
            job_id=self.job_id,
            task_id=self.task_id,
        )

    # ------------------------------------------------------------------
    # Sub-tasks
    # ------------------------------------------------------------------

    def spawn_tasks(self, task_defs: list[dict[str, Any]]) -> list[uuid.UUID]:
        """Spawn child tasks under the current task and enqueue them immediately.

        Each child task is assigned to an ``agent_type`` and runs in parallel
        via the normal Celery worker queue. Spawned tasks appear as a tree
        under the current task in the job timeline dashboard.

        Args:
            task_defs: List of task definition dicts. Recognised keys:

                - ``title`` *(required)*: Display name for the task.
                - ``agent_type`` *(optional)*: Name of the registered agent to run
                  (default: ``"ResearchAgent"``).
                - ``description`` *(optional)*: Input passed to the agent as context.

        Returns:
            List of UUIDs for the newly created child tasks, in the same order
            as *task_defs*.

        Example::

            ids = ctx.spawn_tasks([
                {"title": "Research",  "agent_type": "ResearchAgent",  "description": task},
                {"title": "Summarise", "agent_type": "SummaryAgent",   "description": task},
            ])
            results = ctx.wait_for_tasks(ids)
        """
        from osymandias.runtime.models import Task, TaskStatus
        from osymandias.runtime.core.event_emitter import EventEmitter

        task_ids: list[uuid.UUID] = []
        for td in task_defs:
            child = Task(
                job_id=self.job_id,
                parent_task_id=self.task_id,
                title=td["title"],
                description=td.get("description", ""),
                status=TaskStatus.PENDING,
                agent_type=td.get("agent_type", "ResearchAgent"),
                input_context={
                    "task_description": td.get("description", ""),
                    "job_description": td.get("description", ""),
                },
                max_attempts=3,
            )
            self._session.add(child)
            self._session.flush()
            task_ids.append(child.id)
            EventEmitter.emit_sync(
                self._session,
                "TASK_CREATED",
                {"title": child.title, "agent_type": child.agent_type, "parent_task_id": str(self.task_id)},
                job_id=self.job_id,
                task_id=child.id,
            )

        self._session.commit()

        from osymandias.runtime.workers.scheduler_tasks import resolve_dag
        resolve_dag.apply_async(args=[str(self.job_id)], queue="scheduler")

        return task_ids

    def wait_for_tasks(
        self,
        task_ids: list[uuid.UUID],
        timeout: int = 90,
    ) -> dict[str, dict[str, Any]]:
        """Block until all specified child tasks reach a terminal state.

        Subscribes to the job's Redis pub/sub channel so it wakes immediately
        when each task completes — no fixed polling interval. Falls back to a
        final DB read to catch tasks that finished before the subscription was
        established. Returns all results regardless of whether individual tasks
        succeeded or failed — check each value for an ``"error"`` key if
        failure handling is needed.

        Args:
            task_ids: List of task UUIDs returned by :meth:`spawn_tasks`.
            timeout:  Maximum seconds to wait before returning partial results
                      (default 90). Tasks still pending at timeout are logged
                      as a warning and their result dict will be empty ``{}``.

        Returns:
            Dict mapping ``task title → output_result dict``.

        Example::

            ids = ctx.spawn_tasks([...])
            results = ctx.wait_for_tasks(ids, timeout=120)

            research = results.get("Research", {})
            summary  = results.get("Summarise", {})
        """
        import json as _json

        import redis as _redis
        from sqlalchemy import select

        from osymandias.runtime.config import settings
        from osymandias.runtime.models import Task, TaskStatus

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        pending = set(task_ids)

        # ── Initial snapshot ────────────────────────────────────────────────
        # Tasks may have already finished before this call.
        self._session.expire_all()
        rows = self._session.scalars(
            select(Task).where(Task.id.in_(list(task_ids)))
        ).all()
        for row in rows:
            if row.status in terminal:
                pending.discard(row.id)

        if not pending:
            return {row.title: row.output_result or {} for row in rows}

        # ── Redis pub/sub ────────────────────────────────────────────────────
        # EventEmitter publishes TASK_COMPLETED / TASK_FAILED to this channel.
        r = _redis.from_url(settings.osy_redis_url, decode_responses=True)
        pubsub = r.pubsub(ignore_subscribe_messages=True)
        pubsub.subscribe(f"events:job:{self.job_id}")

        deadline = time.monotonic() + timeout
        try:
            while pending and time.monotonic() < deadline:
                remaining = max(0.1, deadline - time.monotonic())
                msg = pubsub.get_message(timeout=min(remaining, 2.0))
                if not msg:
                    continue
                try:
                    data = _json.loads(msg["data"])
                except Exception:
                    continue
                if data.get("event_type") in ("TASK_COMPLETED", "TASK_FAILED", "TASK_CANCELLED"):
                    tid_str = data.get("task_id")
                    if tid_str:
                        try:
                            pending.discard(uuid.UUID(tid_str))
                        except ValueError:
                            pass
        finally:
            pubsub.unsubscribe()
            pubsub.close()
            r.close()

        # ── Fallback DB check ────────────────────────────────────────────────
        # Catches tasks that completed between the initial snapshot and the
        # subscribe call (pub/sub message would have been missed).
        if pending:
            self._session.expire_all()
            rows = self._session.scalars(
                select(Task).where(Task.id.in_(list(task_ids)))
            ).all()
            for row in rows:
                if row.status in terminal:
                    pending.discard(row.id)
            if pending:
                logger.warning(
                    "wait_for_tasks: {} task(s) did not complete within {}s",
                    len(pending),
                    timeout,
                )

        # ── Collect results ──────────────────────────────────────────────────
        self._session.expire_all()
        rows = self._session.scalars(
            select(Task).where(Task.id.in_(list(task_ids)))
        ).all()
        return {row.title: row.output_result or {} for row in rows}
