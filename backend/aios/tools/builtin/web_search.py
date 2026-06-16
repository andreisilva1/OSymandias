"""
web_search tool — uses DuckDuckGo (no API key required) as default.
"""
import httpx
from loguru import logger

from aios.tools.registry import register


@register("web_search")
def web_search(query: str) -> dict:
    """Search the web using DuckDuckGo Instant Answer API."""
    try:
        response = httpx.get(
            "https://api.duckduckgo.com/",
            params={"q": query, "format": "json", "no_html": "1", "skip_disambig": "1"},
            timeout=15,
            follow_redirects=True,
        )
        response.raise_for_status()
        data = response.json()

        results = []

        # Abstract (top answer)
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", ""),
                "snippet": data["AbstractText"],
                "url": data.get("AbstractURL", ""),
                "source": "abstract",
            })

        # Related topics
        for topic in data.get("RelatedTopics", [])[:8]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("Text", "")[:120],
                    "snippet": topic.get("Text", ""),
                    "url": topic.get("FirstURL", ""),
                    "source": "related",
                })

        logger.debug("web_search: query='{}' → {} results", query, len(results))
        return {"query": query, "results": results}

    except Exception as exc:
        logger.warning("web_search failed for '{}': {}", query, exc)
        return {"query": query, "results": [], "error": str(exc)}
