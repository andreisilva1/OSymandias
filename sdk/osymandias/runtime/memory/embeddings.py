"""
Generate embeddings via LiteLLM using the configured provider.
Falls back to a zero vector if the provider is unavailable.
"""
from loguru import logger

# Dimensions per embedding model:
#   nomic-embed-text (Ollama default) → 768
#   text-embedding-3-small (OpenAI)   → 1536
_PROVIDER_DIMS = {
    "ollama": 768,
    "openai": 1536,
}

def get_embedding_dimension() -> int:
    from osymandias.runtime.config import settings
    return _PROVIDER_DIMS.get(settings.llm_default_provider, 768)

# Kept for backwards compat (used by migration reference)
EMBEDDING_DIMENSION = 768


def generate_embedding(text: str) -> list[float]:
    try:
        import litellm
        from osymandias.runtime.config import settings

        provider = settings.llm_default_provider
        dim = _PROVIDER_DIMS.get(provider, 768)

        if provider == "ollama":
            response = litellm.embedding(
                model="ollama/nomic-embed-text",
                input=[text],
                api_base=settings.ollama_base_url,
            )
        elif provider == "openai":
            response = litellm.embedding(model="text-embedding-3-small", input=[text])
        else:
            response = litellm.embedding(model="text-embedding-3-small", input=[text])

        return response.data[0]["embedding"]

    except Exception as exc:
        logger.warning("generate_embedding failed ({}), using zero vector", exc)
        return [0.0] * get_embedding_dimension()
