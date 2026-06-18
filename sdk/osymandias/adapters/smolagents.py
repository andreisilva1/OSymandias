"""Smolagents (HuggingFace) adapter."""
from __future__ import annotations

import base64
from typing import Any


class SmolAgentsAdapter:
    """Wrap a HuggingFace Smolagents agent as an OSy agent.

    If the agent generates matplotlib figures or PIL images, they are
    base64-encoded and included under '_media' for dashboard rendering.

    Usage::

        from smolagents import CodeAgent, HfApiModel
        from osymandias.adapters.smolagents import SmolAgentsAdapter

        agent = CodeAgent(tools=[...], model=HfApiModel())

        @osy.agent("HFAgent")
        def hf_agent(task: str) -> dict:
            return SmolAgentsAdapter(agent).run(task)
    """

    def __init__(self, agent) -> None:
        try:
            import smolagents  # noqa: F401
        except ImportError:
            raise ImportError(
                "Smolagents is not installed. Run: pip install osymandias[smolagents]"
            )
        self._agent = agent

    def run(self, task: str, ctx=None) -> dict[str, Any]:
        if ctx is not None:
            ctx.emit_event("TASK_PROGRESS", {"step": "running", "task": task[:200]})

        output = self._agent.run(task)

        result = self._normalise(output)

        if ctx is not None:
            ctx.emit_event("TASK_PROGRESS", {"step": "done"})

        return result

    @staticmethod
    def _normalise(output: Any) -> dict[str, Any]:
        if isinstance(output, dict):
            return output

        media = []

        # matplotlib Figure → base64 PNG
        try:
            import matplotlib.pyplot as plt
            import matplotlib.figure
            if isinstance(output, matplotlib.figure.Figure):
                import io
                buf = io.BytesIO()
                output.savefig(buf, format="png")
                b64 = base64.b64encode(buf.getvalue()).decode()
                media.append({"type": "image", "base64": f"data:image/png;base64,{b64}"})
                result: dict[str, Any] = {"output": "figure"}
                result["_media"] = media
                return result
        except ImportError:
            pass

        # PIL Image → base64 PNG
        try:
            from PIL import Image
            import io
            if isinstance(output, Image.Image):
                buf = io.BytesIO()
                output.save(buf, format="PNG")
                b64 = base64.b64encode(buf.getvalue()).decode()
                media.append({"type": "image", "base64": f"data:image/png;base64,{b64}"})
                result = {"output": "image"}
                result["_media"] = media
                return result
        except ImportError:
            pass

        if hasattr(output, "model_dump"):
            return output.model_dump()

        return {"output": str(output)}
