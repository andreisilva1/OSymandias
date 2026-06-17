"""
Tool Executor — validates permissions and runs tool callables.
Used inside execute_tool_call Celery task.
"""
import uuid
from typing import Any

from loguru import logger
from sqlalchemy.orm import Session

from osymandias.runtime.tools.permissions import PermissionDenied, check_permission
from osymandias.runtime.tools.registry import get_callable


class ToolExecutor:

    @staticmethod
    def run_sync(
        tool_name: str,
        input_args: dict[str, Any],
        agent_instance_id: uuid.UUID,
        session: Session,
    ) -> dict[str, Any]:
        """
        Validates permission and executes the tool synchronously.
        Builtin tools: dispatch to registered Python callable.
        Webhook tools: POST input_args to webhook_url and return JSON response.
        """
        # 1. Permission check
        check_permission(tool_name, agent_instance_id, session)

        # 2. Try Python registry first (builtin tools)
        try:
            fn = get_callable(tool_name)
            import inspect
            sig = inspect.signature(fn)
            params = sig.parameters
            if "session" in params:
                filtered = {k: v for k, v in input_args.items() if k in params and k not in ("session", "agent_instance_id")}
                result = fn(**filtered, session=session, agent_instance_id=agent_instance_id)
            else:
                filtered = {k: v for k, v in input_args.items() if k in params}
                result = fn(**filtered)
            return result if isinstance(result, dict) else {"result": result}

        except KeyError:
            pass  # not a builtin — check for webhook

        # 3. Webhook tool
        from osymandias.runtime.models import ToolDefinition
        td = session.get(ToolDefinition, tool_name)
        if td and td.webhook_url and td.is_active:
            import httpx
            timeout = 30.0
            try:
                resp = httpx.post(
                    td.webhook_url,
                    json={"tool": tool_name, "input": input_args},
                    timeout=timeout,
                    headers={"Content-Type": "application/json"},
                )
                resp.raise_for_status()
                data = resp.json()
                return data if isinstance(data, dict) else {"result": data}
            except httpx.TimeoutException:
                raise TimeoutError(f"Webhook '{tool_name}' timed out after {timeout}s")
            except httpx.HTTPStatusError as e:
                raise RuntimeError(f"Webhook '{tool_name}' returned HTTP {e.response.status_code}: {e.response.text[:200]}")

        raise KeyError(f"Tool '{tool_name}' is not registered and has no webhook URL.")
