"""
MemoryManager — unified read/write API for all memory scopes.
Used by agent workers (sync) and FastAPI routes (async).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from loguru import logger
from sqlalchemy import select
from sqlalchemy.orm import Session

from aios.models.memory_entry import MemoryEntry, MemoryScope


class MemoryManager:

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    @staticmethod
    def write_sync(
        session: Session,
        scope: MemoryScope,
        scope_id: uuid.UUID | None,
        key: str,
        value: dict[str, Any],
        embed: bool = False,
    ) -> MemoryEntry:
        # Upsert: update existing entry if same scope+scope_id+key
        existing = session.scalars(
            select(MemoryEntry).where(
                MemoryEntry.scope == scope,
                MemoryEntry.scope_id == scope_id,
                MemoryEntry.key == key,
            )
        ).first()

        if existing:
            existing.value = value
            existing.last_accessed_at = datetime.now(timezone.utc)
            entry = existing
        else:
            entry = MemoryEntry(
                scope=scope,
                scope_id=scope_id,
                key=key,
                value=value,
            )
            session.add(entry)

        if embed:
            MemoryManager._embed_and_sync(entry, value, session)

        session.flush()
        return entry

    # ------------------------------------------------------------------
    # Read by key
    # ------------------------------------------------------------------

    @staticmethod
    def read_sync(
        session: Session,
        scope: MemoryScope,
        scope_id: uuid.UUID | None,
        key: str,
    ) -> dict[str, Any] | None:
        entry = session.scalars(
            select(MemoryEntry).where(
                MemoryEntry.scope == scope,
                MemoryEntry.scope_id == scope_id,
                MemoryEntry.key == key,
            )
        ).first()

        if not entry:
            return None

        entry.access_count += 1
        entry.last_accessed_at = datetime.now(timezone.utc)
        session.flush()
        return entry.value

    # ------------------------------------------------------------------
    # Semantic search
    # ------------------------------------------------------------------

    @staticmethod
    def search_sync(
        query: str,
        scopes: list[MemoryScope],
        scope_ids: list[uuid.UUID],
        top_k: int,
        session: Session,
        rerank_weights: dict[str, float] | None = None,
    ) -> list[dict[str, Any]]:
        from aios.memory.embeddings import generate_embedding
        from aios.memory import qdrant_client as qc
        from aios.memory.reranker import rerank

        query_vector = generate_embedding(query)

        # Search Qdrant for each scope+scope_id combination
        all_results = []
        for scope in scopes:
            for sid in (scope_ids if scope != MemoryScope.GLOBAL else [None]):
                filter_payload = {"scope": scope.value}
                if sid is not None:
                    filter_payload["scope_id"] = str(sid)
                results = qc.search(query_vector, scope_filter=filter_payload, top_k=top_k)
                all_results.extend(results)

        if not all_results:
            return []

        # Fetch MemoryEntry objects from PostgreSQL
        point_ids = [uuid.UUID(r["point_id"]) for r in all_results]
        entries_map: dict[str, MemoryEntry] = {}
        for entry in session.scalars(
            select(MemoryEntry).where(MemoryEntry.qdrant_point_id.in_(point_ids))
        ).all():
            entries_map[str(entry.qdrant_point_id)] = entry

        # Pair results with entries
        paired_results = []
        paired_entries = []
        for r in all_results:
            entry = entries_map.get(r["point_id"])
            if entry:
                paired_results.append(r)
                paired_entries.append(entry)
                entry.access_count += 1
                entry.last_accessed_at = datetime.now(timezone.utc)

        session.flush()
        return rerank(paired_results, paired_entries, rerank_weights)[:top_k]

    # ------------------------------------------------------------------
    # Bulk read by scope (for context builder)
    # ------------------------------------------------------------------

    @staticmethod
    def read_all_sync(
        session: Session,
        scope: MemoryScope,
        scope_id: uuid.UUID | None,
    ) -> list[dict[str, Any]]:
        entries = session.scalars(
            select(MemoryEntry).where(
                MemoryEntry.scope == scope,
                MemoryEntry.scope_id == scope_id,
            )
        ).all()
        return [{"key": e.key, "value": e.value} for e in entries]

    # ------------------------------------------------------------------
    # Internal: embed + sync to Qdrant
    # ------------------------------------------------------------------

    @staticmethod
    def _embed_and_sync(entry: MemoryEntry, value: dict, session: Session) -> None:
        try:
            from aios.memory.embeddings import generate_embedding
            from aios.memory import qdrant_client as qc

            text = str(value)
            vector = generate_embedding(text)
            entry.embedding = vector

            point_id = entry.qdrant_point_id or uuid.uuid4()
            entry.qdrant_point_id = point_id

            qc.upsert(
                point_id=point_id,
                vector=vector,
                payload={
                    "scope": entry.scope.value,
                    "scope_id": str(entry.scope_id) if entry.scope_id else None,
                    "key": entry.key,
                },
            )
        except Exception as exc:
            logger.warning("Memory embed/sync failed: {} — embedding skipped", exc)
