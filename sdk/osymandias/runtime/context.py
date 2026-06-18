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
        from osymandias.runtime.memory.manager import MemoryManager
        from osymandias.runtime.models.memory_entry import MemoryScope
        return MemoryManager.read_sync(
            session=self._session,
            scope=MemoryScope.JOB,
            scope_id=self.job_id,
            key=key,
        )

    def write_memory(self, key: str, value: dict[str, Any]) -> None:
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
        """Create child tasks under the current task and enqueue them."""
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
        """Block until all child tasks complete or timeout is reached.

        Returns a mapping of task title → output_result.
        """
        from sqlalchemy import select
        from osymandias.runtime.models import Task, TaskStatus

        terminal = {TaskStatus.COMPLETED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        deadline = time.monotonic() + timeout
        pending = set(task_ids)

        while pending and time.monotonic() < deadline:
            rows = self._session.scalars(
                select(Task).where(Task.id.in_(list(pending)))
            ).all()
            for row in rows:
                if row.status in terminal:
                    pending.discard(row.id)
            if pending:
                self._session.expire_all()
                time.sleep(1)

        if pending:
            logger.warning(
                "wait_for_tasks: {} tasks did not complete within {}s",
                len(pending),
                timeout,
            )

        results: dict[str, dict[str, Any]] = {}
        rows = self._session.scalars(
            select(Task).where(Task.id.in_(list(task_ids)))
        ).all()
        for row in rows:
            results[row.title] = row.output_result or {}
        return results
