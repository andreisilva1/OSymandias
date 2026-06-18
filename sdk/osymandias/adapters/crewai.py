"""CrewAI adapter — wraps a Crew as a single OSy agent (black-box)."""
from __future__ import annotations

from typing import Any


class CrewAIAdapter:
    """Wrap a CrewAI Crew as an OSy agent.

    The crew's final output becomes the task result. Internal agent handoffs
    within the crew are not exposed to the OSy dashboard — the crew runs as
    a black box. Use OsyContext.emit_event manually inside kickoff callbacks
    if intermediate progress is needed.

    Usage::

        from crewai import Crew, Agent, Task
        from osymandias.adapters.crewai import CrewAIAdapter

        crew = Crew(agents=[...], tasks=[...])

        @osy.agent("AnalystCrew")
        def analyst_crew(task: str) -> dict:
            return CrewAIAdapter(crew).run(task)
    """

    def __init__(self, crew) -> None:
        try:
            from crewai import Crew  # noqa: F401
        except ImportError:
            raise ImportError(
                "CrewAI is not installed. Run: pip install osymandias[crewai]"
            )
        self._crew = crew

    def run(self, task: str, ctx=None) -> dict[str, Any]:
        result = self._crew.kickoff(inputs={"task": task})
        return self._normalise(result)

    @staticmethod
    def _normalise(result: Any) -> dict[str, Any]:
        if isinstance(result, dict):
            return result
        # CrewOutput object
        if hasattr(result, "raw"):
            raw = result.raw
            if isinstance(raw, dict):
                return raw
            return {"output": str(raw)}
        if hasattr(result, "model_dump"):
            return result.model_dump()
        return {"output": str(result)}
