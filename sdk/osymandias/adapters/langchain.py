"""LangChain adapter — wraps LCEL chains and legacy AgentExecutor."""
from __future__ import annotations

from typing import Any

from loguru import logger


class OsyCallbackHandler:
    """LangChain callback handler that forwards events to OsyContext.emit_event.

    Attach to any LangChain chain or agent via the callbacks= parameter,
    or pass an OsyContext and let LangChainAdapter attach it automatically.
    """

    def __init__(self, ctx) -> None:
        self._ctx = ctx

    # LangChain BaseCallbackHandler interface (sync variants) ──────────────

    def on_llm_start(self, serialized: dict, prompts: list[str], **kwargs) -> None:
        self._ctx.emit_event("TASK_PROGRESS", {"step": "llm_start", "prompts": len(prompts)})

    def on_llm_end(self, response, **kwargs) -> None:
        self._ctx.emit_event("TASK_PROGRESS", {"step": "llm_end"})

    def on_tool_start(self, serialized: dict, input_str: str, **kwargs) -> None:
        self._ctx.emit_event(
            "TASK_PROGRESS",
            {"step": "tool_start", "tool": serialized.get("name", "unknown"), "input": input_str[:200]},
        )

    def on_tool_end(self, output: str, **kwargs) -> None:
        self._ctx.emit_event("TASK_PROGRESS", {"step": "tool_end", "output_len": len(str(output))})

    def on_chain_error(self, error: Exception, **kwargs) -> None:
        self._ctx.emit_event("TASK_PROGRESS", {"step": "error", "error": str(error)[:300]})

    # Make compatible with both old and new LangChain callback protocols
    def __getattr__(self, name: str):
        return lambda *a, **kw: None


class LangChainAdapter:
    """Wrap a LangChain LCEL Runnable or legacy AgentExecutor as an OSy agent.

    Usage::

        from osymandias.adapters.langchain import LangChainAdapter

        chain = prompt | llm | parser

        @osy.agent("MyChain")
        def my_chain(task: str, ctx: OsyContext) -> dict:
            return LangChainAdapter(chain).run(task, ctx=ctx)
    """

    def __init__(self, chain) -> None:
        try:
            from langchain_core.runnables import Runnable  # noqa: F401
        except ImportError:
            raise ImportError(
                "LangChain is not installed. Run: pip install osymandias[langchain]"
            )
        self._chain = chain

    def run(self, task: str, ctx=None) -> dict[str, Any]:
        callbacks = [OsyCallbackHandler(ctx)] if ctx is not None else []

        try:
            # LCEL Runnable
            from langchain_core.runnables import Runnable
            if isinstance(self._chain, Runnable):
                result = self._chain.invoke({"input": task}, config={"callbacks": callbacks})
                return self._normalise(result)
        except ImportError:
            pass

        try:
            # Legacy AgentExecutor
            from langchain.agents import AgentExecutor
            if isinstance(self._chain, AgentExecutor):
                result = self._chain.invoke({"input": task}, callbacks=callbacks)
                return self._normalise(result)
        except ImportError:
            pass

        # Fallback: try .invoke then .run
        if hasattr(self._chain, "invoke"):
            result = self._chain.invoke({"input": task})
        elif hasattr(self._chain, "run"):
            result = self._chain.run(task)
        else:
            raise TypeError(f"Unsupported LangChain object: {type(self._chain)}")

        return self._normalise(result)

    @staticmethod
    def _normalise(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        if hasattr(result, "model_dump"):
            return result.model_dump()
        if hasattr(result, "dict"):
            return result.dict()
        return {"output": str(result)}
