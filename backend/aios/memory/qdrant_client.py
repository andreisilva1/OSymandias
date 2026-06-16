"""
Qdrant client wrapper — handles upsert and search for memory embeddings.
"""
import uuid
from typing import Any

from loguru import logger
from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
    QueryRequest,
)

from aios.config import settings
from aios.memory.embeddings import EMBEDDING_DIMENSION

COLLECTION_NAME = "memory"

_client: QdrantClient | None = None


def get_client() -> QdrantClient:
    global _client
    if _client is None:
        _client = QdrantClient(url=settings.qdrant_url)
        _ensure_collection(_client)
    return _client


def _ensure_collection(client: QdrantClient) -> None:
    existing = [c.name for c in client.get_collections().collections]
    if COLLECTION_NAME not in existing:
        client.create_collection(
            collection_name=COLLECTION_NAME,
            vectors_config=VectorParams(size=EMBEDDING_DIMENSION, distance=Distance.COSINE),
        )
        logger.info("Qdrant: created collection '{}'", COLLECTION_NAME)


def upsert(
    point_id: uuid.UUID,
    vector: list[float],
    payload: dict[str, Any],
) -> None:
    try:
        client = get_client()
        client.upsert(
            collection_name=COLLECTION_NAME,
            points=[PointStruct(id=str(point_id), vector=vector, payload=payload)],
        )
    except Exception as exc:
        logger.warning("Qdrant upsert failed: {}", exc)
        raise


def search(
    query_vector: list[float],
    scope_filter: dict[str, Any] | None = None,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    try:
        client = get_client()
        conditions = []
        if scope_filter:
            for key, value in scope_filter.items():
                conditions.append(FieldCondition(key=key, match=MatchValue(value=value)))

        filt = Filter(must=conditions) if conditions else None
        try:
            # qdrant-client >= 1.7: query_points()
            response = client.query_points(
                collection_name=COLLECTION_NAME,
                query=query_vector,
                query_filter=filt,
                limit=top_k,
                with_payload=True,
            )
            hits = response.points
        except AttributeError:
            # fallback for older qdrant-client: search()
            hits = client.search(  # type: ignore[attr-defined]
                collection_name=COLLECTION_NAME,
                query_vector=query_vector,
                query_filter=filt,
                limit=top_k,
                with_payload=True,
            )
        return [{"point_id": r.id, "score": r.score, "payload": r.payload} for r in hits]

    except Exception as exc:
        logger.warning("Qdrant search failed: {}", exc)
        return []


def delete_point(point_id: uuid.UUID) -> None:
    try:
        client = get_client()
        client.delete(
            collection_name=COLLECTION_NAME,
            points_selector=[str(point_id)],
        )
    except Exception as exc:
        logger.warning("Qdrant delete failed for {}: {}", point_id, exc)
