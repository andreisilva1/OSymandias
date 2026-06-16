"""
web_search tool — real web results via DuckDuckGo (no API key required).
"""
from ddgs import DDGS
from loguru import logger

from aios.tools.registry import register

_MAX_RESULTS = 5


@register("web_search")
def web_search(query: str) -> dict:
    """Search the web using DuckDuckGo and return up to 5 real results."""
    try:
        with DDGS() as ddgs:
            raw = list(ddgs.text(query, max_results=_MAX_RESULTS))

        results = [
            {
                "title":   r.get("title", ""),
                "url":     r.get("href", ""),
                "snippet": r.get("body", ""),
            }
            for r in raw
        ]

        logger.debug("web_search: query='{}' → {} results", query, len(results))
        return {"query": query, "results": results}

    except Exception as exc:
        logger.warning("web_search failed for '{}': {}", query, exc)
        return {"query": query, "results": [], "error": str(exc)}
