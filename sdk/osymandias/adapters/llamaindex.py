"""LlamaIndex adapter — wraps QueryEngine or ReActAgent."""
from __future__ import annotations

from typing import Any


class LlamaIndexAdapter:
    """Wrap a LlamaIndex QueryEngine or ReActAgent as an OSy agent.

    Source nodes (retrieved documents) are included in the output under
    the 'sources' key. Images found in source nodes are collected under
    '_media' for dashboard multi-modal rendering.

    Usage::

        from llama_index.core import VectorStoreIndex
        from osymandias.adapters.llamaindex import LlamaIndexAdapter

        index = VectorStoreIndex.from_documents(docs)
        query_engine = index.as_query_engine()

        @osy.agent("Retriever")
        def retriever(task: str, ctx: OsyContext) -> dict:
            return LlamaIndexAdapter(query_engine).run(task, ctx=ctx)
    """

    def __init__(self, engine) -> None:
        try:
            import llama_index  # noqa: F401
        except ImportError:
            raise ImportError(
                "LlamaIndex is not installed. Run: pip install osymandias[llamaindex]"
            )
        self._engine = engine

    def run(self, task: str, ctx=None) -> dict[str, Any]:
        if ctx is not None:
            ctx.emit_event("TASK_PROGRESS", {"step": "querying", "query": task[:200]})

        # ReActAgent uses .chat(); QueryEngine uses .query()
        if hasattr(self._engine, "chat"):
            response = self._engine.chat(task)
        else:
            response = self._engine.query(task)

        result = self._normalise(response)

        if ctx is not None:
            ctx.emit_event("TASK_PROGRESS", {"step": "done", "sources": len(result.get("sources", []))})

        return result

    @staticmethod
    def _normalise(response: Any) -> dict[str, Any]:
        text = str(getattr(response, "response", response))
        source_nodes = getattr(response, "source_nodes", [])

        sources = []
        media = []
        for node in source_nodes:
            node_obj = getattr(node, "node", node)
            url = getattr(node_obj, "metadata", {}).get("url") or getattr(node_obj, "id_", None)
            if url:
                sources.append(url)
            image_url = getattr(node_obj, "metadata", {}).get("image_url")
            if image_url:
                media.append({"type": "image", "url": image_url})

        result: dict[str, Any] = {"output": text, "sources": sources}
        if media:
            result["_media"] = media
        return result
