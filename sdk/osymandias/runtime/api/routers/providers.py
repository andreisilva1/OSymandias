"""
GET /api/v1/providers/{provider}/models
Queries each LLM provider's own API for available models.
Anthropic has no listing endpoint — returns a static list.
"""
from __future__ import annotations

import httpx
from fastapi import APIRouter, HTTPException

from osymandias.runtime.config import settings

router = APIRouter(prefix="/api/v1/providers", tags=["providers"])

# Anthropic has no models listing API; keep a curated static list.
_ANTHROPIC_STATIC = [
    "claude-opus-4-8",
    "claude-sonnet-4-6",
    "claude-haiku-4-5-20251001",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-haiku-20240307",
]


@router.get("/{provider}/models")
async def list_provider_models(provider: str) -> list[str]:
    try:
        return await _fetch_models(provider)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


async def _fetch_models(provider: str) -> list[str]:
    if provider == "anthropic":
        return _ANTHROPIC_STATIC

    if provider == "ollama":
        async with httpx.AsyncClient(timeout=5) as client:
            r = await client.get(f"{settings.ollama_base_url}/api/tags")
            r.raise_for_status()
            data = r.json()
        return sorted(m["name"] for m in data.get("models", []))

    if provider == "openai":
        if not settings.openai_api_key:
            raise HTTPException(status_code=400, detail="OPENAI_API_KEY not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {settings.openai_api_key}"},
            )
            r.raise_for_status()
        ids = [m["id"] for m in r.json().get("data", [])]
        # Keep only chat-capable models
        keep = ("gpt-4", "gpt-3.5", "o1", "o3", "o4")
        return sorted(i for i in ids if any(i.startswith(p) for p in keep))

    if provider == "deepseek":
        if not settings.deepseek_api_key:
            raise HTTPException(status_code=400, detail="DEEPSEEK_API_KEY not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.deepseek.com/v1/models",
                headers={"Authorization": f"Bearer {settings.deepseek_api_key}"},
            )
            r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))

    if provider == "groq":
        if not settings.groq_api_key:
            raise HTTPException(status_code=400, detail="GROQ_API_KEY not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://api.groq.com/openai/v1/models",
                headers={"Authorization": f"Bearer {settings.groq_api_key}"},
            )
            r.raise_for_status()
        return sorted(m["id"] for m in r.json().get("data", []))

    if provider == "gemini":
        if not settings.gemini_api_key:
            raise HTTPException(status_code=400, detail="GEMINI_API_KEY not configured")
        async with httpx.AsyncClient(timeout=10) as client:
            r = await client.get(
                "https://generativelanguage.googleapis.com/v1beta/models",
                headers={"x-goog-api-key": settings.gemini_api_key},
            )
            r.raise_for_status()
        models = r.json().get("models", [])
        # Only generative models (excludes embedding models)
        return sorted(
            m["name"].replace("models/", "")
            for m in models
            if "generateContent" in m.get("supportedGenerationMethods", [])
        )

    raise HTTPException(status_code=400, detail=f"Unknown provider: {provider}")
