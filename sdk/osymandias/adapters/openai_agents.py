"""OpenAI Agents SDK adapter — exposes handoffs as TASK_PROGRESS events."""
from __future__ import annotations

from typing import Any


class OpenAIAgentsAdapter:
    """Wrap an OpenAI Agents SDK Agent as an OSy agent.

    Handoffs between sub-agents are emitted as TASK_PROGRESS events so they
    appear in the dashboard SSE stream.

    Usage::

        from agents import Agent, Runner
        from osymandias.adapters.openai_agents import OpenAIAgentsAdapter

        agent = Agent(name="Assistant", instructions="...", model="gpt-4o")

        @osy.agent("GPT4Agent")
        def gpt4_agent(task: str, ctx: OsyContext) -> dict:
            return OpenAIAgentsAdapter(agent).run(task, ctx=ctx)
    """

    def __init__(self, agent) -> None:
        try:
            from agents import Agent  # noqa: F401
        except ImportError:
            raise ImportError(
                "OpenAI Agents SDK is not installed. Run: pip install osymandias[openai-agents]"
            )
        self._agent = agent

    def run(self, task: str, ctx=None) -> dict[str, Any]:
        from agents import Runner

        result = Runner.run_sync(self._agent, task)

        if ctx is not None:
            self._emit_handoffs(result, ctx)

        output = result.final_output
        return self._normalise(output)

    @staticmethod
    def _emit_handoffs(result, ctx) -> None:
        for msg in getattr(result, "new_messages", []):
            agent_name = getattr(msg, "agent_name", None) or getattr(msg, "sender", None)
            if agent_name:
                ctx.emit_event(
                    "TASK_PROGRESS",
                    {"step": "handoff", "agent": agent_name, "content_len": len(str(getattr(msg, "content", "")))},
                )

    @staticmethod
    def _normalise(output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            return output
        if hasattr(output, "model_dump"):
            return output.model_dump()
        if hasattr(output, "dict"):
            return output.dict()
        return {"output": str(output)}
