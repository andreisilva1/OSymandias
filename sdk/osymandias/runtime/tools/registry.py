"""
Tool Registry — maps tool names to their Python callables and loads
ToolDefinitions from the database on startup.
"""
from __future__ import annotations

from typing import Any, Callable

from loguru import logger

# Registry: tool_name → callable
_REGISTRY: dict[str, Callable[..., Any]] = {}


def register(name: str):
    """Decorator to register a function as a tool implementation."""
    def decorator(fn: Callable[..., Any]) -> Callable[..., Any]:
        _REGISTRY[name] = fn
        logger.debug("Tool registered: {}", name)
        return fn
    return decorator


def get_callable(name: str) -> Callable[..., Any]:
    if name not in _REGISTRY:
        raise KeyError(f"Tool '{name}' is not registered.")
    return _REGISTRY[name]


def list_registered() -> list[str]:
    return list(_REGISTRY.keys())


# Import builtin tools so their @register decorators execute
def _load_builtins() -> None:
    from osymandias.runtime.tools.builtin import web_search, read_url, send_message, memory_ops  # noqa: F401


_load_builtins()
