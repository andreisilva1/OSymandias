"""
LiteLLM wrapper — single entry point for all LLM calls.
Handles provider routing, retry, and cost tracking.
"""
from __future__ import annotations

from typing import Any

import litellm
from loguru import logger
from tenacity import retry, stop_after_attempt, wait_exponential

from aios.config import settings
from aios.llm.cost_tracker import estimate_cost

litellm.set_verbose = False


def _build_model_string(provider: str, model: str) -> str:
    if provider == "ollama":
        return f"ollama/{model}"
    if provider == "deepseek":
        return f"deepseek/{model}"
    if provider == "groq":
        return f"groq/{model}"
    if provider == "gemini":
        return f"gemini/{model}"
    # anthropic and openai: LiteLLM accepts the model name directly
    return model


def _build_kwargs(provider: str) -> dict[str, Any]:
    kwargs: dict[str, Any] = {}
    if provider == "ollama":
        kwargs["api_base"] = settings.ollama_base_url
    elif provider == "anthropic":
        kwargs["api_key"] = settings.anthropic_api_key
    elif provider == "openai":
        kwargs["api_key"] = settings.openai_api_key
    elif provider == "deepseek":
        kwargs["api_key"] = settings.deepseek_api_key
    elif provider == "groq":
        kwargs["api_key"] = settings.groq_api_key
    elif provider == "gemini":
        kwargs["api_key"] = settings.gemini_api_key
    return kwargs


@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
def chat_completion(
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]] | None = None,
    provider: str | None = None,
    model: str | None = None,
    temperature: float = 0.2,
) -> dict[str, Any]:
    """
    Call the LLM and return a normalised response dict:
    {
        "content": str | None,
        "tool_calls": list | None,
        "input_tokens": int,
        "output_tokens": int,
        "cost_estimate": float,
        "model": str,
    }
    """
    _provider = provider or settings.llm_default_provider
    _model = model or settings.llm_default_model
    model_str = _build_model_string(_provider, _model)
    kwargs = _build_kwargs(_provider)

    call_kwargs: dict[str, Any] = {
        "model": model_str,
        "messages": messages,
        "temperature": temperature,
        **kwargs,
    }
    if tools:
        call_kwargs["tools"] = tools
        call_kwargs["tool_choice"] = "auto"

    logger.debug("LLM call: model={} messages={}", model_str, len(messages))
    response = litellm.completion(**call_kwargs)

    choice = response.choices[0]
    message = choice.message

    input_tokens = response.usage.prompt_tokens if response.usage else 0
    output_tokens = response.usage.completion_tokens if response.usage else 0
    cost = estimate_cost(_provider, _model, input_tokens, output_tokens)

    tool_calls = None
    if hasattr(message, "tool_calls") and message.tool_calls:
        tool_calls = [
            {
                "id": tc.id,
                "name": tc.function.name,
                "arguments": tc.function.arguments,
            }
            for tc in message.tool_calls
        ]

    return {
        "content": message.content,
        "tool_calls": tool_calls,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_estimate": cost,
        "model": model_str,
    }
