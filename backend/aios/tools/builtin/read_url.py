"""
read_url tool — fetches a URL and extracts visible text.
"""
import httpx
from bs4 import BeautifulSoup
from loguru import logger

from aios.tools.registry import register

MAX_CONTENT_CHARS = 4_000


@register("read_url")
def read_url(url: str) -> dict:
    """Fetch a URL and return its cleaned text content."""
    try:
        response = httpx.get(
            url,
            timeout=20,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; AIOS-bot/1.0)"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove scripts, styles, navs
        for tag in soup(["script", "style", "nav", "footer", "header", "aside"]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        # Collapse blank lines
        lines = [l for l in text.splitlines() if l.strip()]
        content = "\n".join(lines)[:MAX_CONTENT_CHARS]

        title = soup.title.string.strip() if soup.title else url

        logger.debug("read_url: {} → {} chars extracted", url, len(content))
        return {"url": url, "title": title, "content": content}

    except Exception as exc:
        logger.warning("read_url failed for '{}': {}", url, exc)
        return {"url": url, "content": "", "error": str(exc)}
