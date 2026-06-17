"""
Reranker — computes the final relevance score for memory retrieval results.

score_final = semantic × 0.7 + recency × 0.2 + frequency × 0.1
"""
from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any


def rerank(
    results: list[dict[str, Any]],
    entries: list[Any],  # MemoryEntry ORM objects
    weights: dict[str, float] | None = None,
) -> list[dict[str, Any]]:
    """
    results: list of Qdrant search results with 'point_id' and 'score'
    entries: corresponding MemoryEntry objects, same order
    """
    w = weights or {"semantic": 0.7, "recency": 0.2, "frequency": 0.1}
    now = datetime.now(timezone.utc)

    # Compute recency and frequency normalisation bounds
    max_access = max((e.access_count for e in entries), default=1) or 1
    max_age_days = 30.0

    scored = []
    for result, entry in zip(results, entries):
        semantic = result["score"]

        age_days = (now - entry.created_at.replace(tzinfo=timezone.utc)).total_seconds() / 86400
        recency = max(0.0, 1.0 - (age_days / max_age_days))

        frequency = math.log1p(entry.access_count) / math.log1p(max_access)

        final = (
            semantic * w["semantic"]
            + recency * w["recency"]
            + frequency * w["frequency"]
        )

        scored.append({
            "memory_entry_id": str(entry.id),
            "key": entry.key,
            "value": entry.value,
            "scope": entry.scope,
            "score": round(final, 4),
            "semantic_score": round(semantic, 4),
        })

    return sorted(scored, key=lambda x: x["score"], reverse=True)
