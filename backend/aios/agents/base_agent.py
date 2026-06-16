"""
BaseAgent — the core agent loop.
All builtin agents inherit from or are configured via this class.
"""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Any

import redis as _redis
from loguru import logger
from sqlalchemy.orm import Session

from aios.config import settings
from aios.core.event_emitter import EventEmitter
from aios.llm.client import chat_completion
from aios.models import (
    AgentDefinition,
    AgentInstance,
    AgentInstanceStatus,
    Task,
    TaskStatus,
    ToolCall,
    ToolCallStatus,
)
from aios.models.memory_entry import MemoryScope


class MaxIterationsExceeded(Exception):
    pass


class BaseAgent:
    def __init__(
        self,
        agent_definition_name: str,
        job_id: uuid.UUID,
        task_id: uuid.UUID | None,
        session: Session,
        agent_instance_id: uuid.UUID | None = None,
    ):
        self.session = session
        self.job_id = job_id
        self.task_id = task_id

        self.definition: AgentDefinition = session.get(AgentDefinition, agent_definition_name)
        if not self.definition:
            raise ValueError(f"AgentDefinition '{agent_definition_name}' not found")

        if agent_instance_id:
            self.instance: AgentInstance = session.get(AgentInstance, agent_instance_id)
        else:
            self.instance = AgentInstance(
                job_id=job_id,
                task_id=task_id,
                agent_definition_name=agent_definition_name,
                status=AgentInstanceStatus.CREATED,
            )
            session.add(self.instance)
            session.flush()

        self._redis = _redis.from_url(settings.redis_url, decode_responses=True)

    # ------------------------------------------------------------------
    # Public entry points
    # ------------------------------------------------------------------

    def run_sync(self, extra_context: dict[str, Any] | None = None) -> dict[str, Any]:
        """Execute the agent loop synchronously (used in Celery workers)."""
        task = self.session.get(Task, self.task_id) if self.task_id else None
        return self._loop(task, extra_context or {})

    # ------------------------------------------------------------------
    # Core loop
    # ------------------------------------------------------------------

    def _loop(self, task: Task | None, extra_context: dict[str, Any]) -> dict[str, Any]:
        from aios.agents.context_builder import ContextBuilder

        self.instance.status = AgentInstanceStatus.RUNNING
        self.session.flush()

        EventEmitter.emit_sync(
            self.session,
            "AGENT_RUNNING",
            {"agent_type": self.definition.name, "iteration": 0},
            job_id=self.job_id,
            task_id=self.task_id,
            agent_instance_id=self.instance.id,
        )

        # Load checkpoint if exists
        conversation_history = self._load_checkpoint()
        if not conversation_history:
            conversation_history = []

        ctx_builder = ContextBuilder(
            session=self.session,
            agent_instance_id=self.instance.id,
            job_id=self.job_id,
            task_id=self.task_id,
            agent_definition=self.definition,
        )

        max_iter = self.definition.max_iterations

        for iteration in range(self.instance.iteration_count, max_iter):
            self._heartbeat()

            # Build context
            ctx = ctx_builder.build(task) if task else self._build_minimal_context(extra_context)

            # First iteration: inject system + context as first messages
            if not conversation_history:
                system_msg = {"role": "system", "content": ctx["system_prompt"]}
                if ctx.get("injected_context"):
                    user_msg = {"role": "user", "content": ctx["injected_context"]}
                    conversation_history = [system_msg, user_msg]
                elif task:
                    user_msg = {"role": "user", "content": f"Task: {task.title}\n{task.description or ''}"}
                    conversation_history = [system_msg, user_msg]
                else:
                    conversation_history = [system_msg]

            # Near-limit convergence nudges
            remaining = max_iter - iteration
            if remaining == 3:
                conversation_history.append({
                    "role": "user",
                    "content": (
                        f"SYSTEM: Only {remaining} iterations remain. "
                        "Stop calling tools. Synthesize everything you have so far "
                        "and output your final JSON response."
                    ),
                })
            elif remaining == 1:
                conversation_history.append({
                    "role": "user",
                    "content": (
                        "SYSTEM: This is your LAST iteration. "
                        "You MUST output ONLY a valid JSON object right now — "
                        "no tool calls, no explanation, no markdown. "
                        "Use whatever information you already have."
                    ),
                })

            # On the last iteration, disable tools to force a text response
            tools_for_this_call = ctx.get("tool_schemas") or None
            if remaining == 1:
                tools_for_this_call = None

            # LLM call
            start = datetime.now(timezone.utc)
            EventEmitter.emit_sync(
                self.session,
                "LLM_CALL_STARTED",
                {"model": self.definition.llm_model, "iteration": iteration},
                job_id=self.job_id,
                task_id=self.task_id,
                agent_instance_id=self.instance.id,
            )

            response = chat_completion(
                messages=conversation_history,
                tools=tools_for_this_call,
                provider=self.definition.llm_provider,
                model=self.definition.llm_model,
            )

            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)
            self.instance.tokens_used += response["input_tokens"] + response["output_tokens"]
            self.instance.iteration_count = iteration + 1
            self.session.flush()

            EventEmitter.emit_sync(
                self.session,
                "LLM_CALL_COMPLETED",
                {"iteration": iteration, "model": response["model"]},
                job_id=self.job_id,
                task_id=self.task_id,
                agent_instance_id=self.instance.id,
                tokens_used=response["input_tokens"] + response["output_tokens"],
                estimated_cost=response["cost_estimate"],
                duration_ms=duration_ms,
            )

            # --- Handle tool calls ---
            if response["tool_calls"]:
                assistant_msg = {
                    "role": "assistant",
                    "tool_calls": [
                        {
                            "id": tc["id"],
                            "type": "function",
                            "function": {"name": tc["name"], "arguments": tc["arguments"]},
                        }
                        for tc in response["tool_calls"]
                    ],
                }
                conversation_history.append(assistant_msg)

                # Execute each tool call
                for tc_data in response["tool_calls"]:
                    tool_result = self._execute_tool(tc_data, task)
                    conversation_history.append({
                        "role": "tool",
                        "tool_call_id": tc_data["id"],
                        "content": json.dumps(tool_result),
                    })

                # Detect loop: same tool + args last 3 iterations
                if self._detect_loop(conversation_history):
                    conversation_history.append({
                        "role": "user",
                        "content": "Warning: You called the same tool with the same arguments multiple times. Consider a different approach or acknowledge you cannot proceed.",
                    })

                self._save_checkpoint(conversation_history)
                continue

            # --- Handle final response ---
            if response["content"]:
                conversation_history.append({"role": "assistant", "content": response["content"]})
                result = self._parse_final_result(response["content"])
                if result is not None:
                    self._terminate(success=True)
                    return result

                # JSON parse failed: ask model to fix
                conversation_history.append({
                    "role": "user",
                    "content": "Your response must be valid JSON matching the required schema. Please try again.",
                })
                self._save_checkpoint(conversation_history)
                continue

        # Exhausted iterations
        self._terminate(success=False, reason="ITERATION_LIMIT")
        raise MaxIterationsExceeded(
            f"Agent {self.definition.name} reached max iterations ({max_iter})"
        )

    # ------------------------------------------------------------------
    # Tool execution (inline — calls executor directly, no Celery)
    # ------------------------------------------------------------------

    def _execute_tool(self, tc_data: dict, task: Task | None) -> dict[str, Any]:
        import json as _json
        from aios.models import ToolDefinition
        args = _json.loads(tc_data["arguments"]) if isinstance(tc_data["arguments"], str) else tc_data["arguments"]
        tool_name = tc_data["name"]

        # Validate tool exists — return error to LLM instead of crashing on FK
        tool_def = self.session.get(ToolDefinition, tool_name)
        if not tool_def:
            available = self.definition.allowed_tools
            logger.warning(f"Agent called unknown tool '{tool_name}'. Available: {available}")
            return {
                "error": (
                    f"Tool '{tool_name}' does not exist. "
                    f"You must call one of these exact tool names: {available}. "
                    "Do not invent tool names."
                )
            }

        # Persist ToolCall record (task_id is NULL for PlannerAgent — that's intentional)
        tc_record = ToolCall(
            job_id=self.job_id,
            task_id=self.task_id,
            agent_instance_id=self.instance.id,
            tool_name=tool_name,
            input_args=args,
            status=ToolCallStatus.PENDING,
        )
        self.session.add(tc_record)
        self.session.flush()

        EventEmitter.emit_sync(
            self.session,
            "TOOL_CALL_STARTED",
            {"tool_name": tool_name},
            job_id=self.job_id,
            task_id=self.task_id,
            agent_instance_id=self.instance.id,
        )

        from aios.tools.executor import ToolExecutor
        from aios.tools.permissions import PermissionDenied
        try:
            start = datetime.now(timezone.utc)
            result = ToolExecutor.run_sync(
                tool_name=tool_name,
                input_args=args,
                agent_instance_id=self.instance.id,
                session=self.session,
            )
            duration_ms = int((datetime.now(timezone.utc) - start).total_seconds() * 1000)

            tc_record.status = ToolCallStatus.SUCCESS
            tc_record.output_result = result
            tc_record.duration_ms = duration_ms
            tc_record.completed_at = datetime.now(timezone.utc)
            self.instance.tool_calls_count += 1
            self.session.flush()

            EventEmitter.emit_sync(
                self.session,
                "TOOL_CALL_COMPLETED",
                {"tool_name": tool_name, "duration_ms": duration_ms},
                job_id=self.job_id,
                task_id=self.task_id,
                agent_instance_id=self.instance.id,
                duration_ms=duration_ms,
            )
            return result

        except PermissionDenied as exc:
            tc_record.status = ToolCallStatus.PERMISSION_DENIED
            tc_record.error_message = str(exc)
            self.session.flush()
            EventEmitter.emit_sync(
                self.session,
                "TOOL_PERMISSION_DENIED",
                {"tool_name": tool_name, "error": str(exc)},
                job_id=self.job_id,
            )
            return {"error": f"Permission denied: {exc}"}

        except Exception as exc:
            tc_record.status = ToolCallStatus.FAILED
            tc_record.error_message = str(exc)
            self.session.flush()
            EventEmitter.emit_sync(
                self.session,
                "TOOL_CALL_FAILED",
                {"tool_name": tool_name, "error": str(exc)},
                job_id=self.job_id,
            )
            return {"error": str(exc)}

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _heartbeat(self) -> None:
        self.instance.last_heartbeat_at = datetime.now(timezone.utc)
        self.session.flush()

    def _save_checkpoint(self, history: list[dict]) -> None:
        from aios.memory.manager import MemoryManager
        MemoryManager.write_sync(
            session=self.session,
            scope=MemoryScope.TASK,
            scope_id=self.task_id,
            key="checkpoint",
            value={
                "iteration_count": self.instance.iteration_count,
                "conversation_history": history,
            },
        )
        self.session.flush()

    def _load_checkpoint(self) -> list[dict] | None:
        if not self.task_id:
            return None
        from aios.memory.manager import MemoryManager
        data = MemoryManager.read_sync(
            session=self.session,
            scope=MemoryScope.TASK,
            scope_id=self.task_id,
            key="checkpoint",
        )
        if data:
            self.instance.iteration_count = data.get("iteration_count", 0)
            return data.get("conversation_history")
        return None

    def _parse_final_result(self, content: str) -> dict | None:
        import re

        # 1. Direct JSON parse
        try:
            result = json.loads(content.strip())
            if isinstance(result, dict):
                return result
        except json.JSONDecodeError:
            pass

        # 2. Fenced code block: ```json {...} ``` or ``` {...} ```
        match = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", content, re.DOTALL)
        if match:
            try:
                result = json.loads(match.group(1))
                if isinstance(result, dict):
                    return result
            except json.JSONDecodeError:
                pass

        # 3. Scan for the first syntactically valid JSON object in the text
        decoder = json.JSONDecoder()
        for i, ch in enumerate(content):
            if ch == "{":
                try:
                    obj, _ = decoder.raw_decode(content, i)
                    if isinstance(obj, dict):
                        return obj
                except json.JSONDecodeError:
                    pass

        return None

    def _detect_loop(self, history: list[dict]) -> bool:
        tool_calls = [
            msg for msg in history[-6:]
            if msg.get("role") == "assistant" and msg.get("tool_calls")
        ]
        if len(tool_calls) < 3:
            return False
        last = tool_calls[-1]["tool_calls"]
        prev = tool_calls[-2]["tool_calls"] if len(tool_calls) >= 2 else []
        prev2 = tool_calls[-3]["tool_calls"] if len(tool_calls) >= 3 else []
        return (
            json.dumps(last, sort_keys=True) == json.dumps(prev, sort_keys=True) == json.dumps(prev2, sort_keys=True)
        )

    def _terminate(self, success: bool, reason: str = "") -> None:
        self.instance.status = AgentInstanceStatus.TERMINATED if success else AgentInstanceStatus.CRASHED
        self.instance.terminated_at = datetime.now(timezone.utc)
        self.session.flush()
        EventEmitter.emit_sync(
            self.session,
            "AGENT_TERMINATED",
            {"success": success, "reason": reason, "iterations": self.instance.iteration_count},
            job_id=self.job_id,
            task_id=self.task_id,
            agent_instance_id=self.instance.id,
        )

    def _build_minimal_context(self, extra_context: dict) -> dict:
        return {
            "system_prompt": self.definition.system_prompt_template,
            "injected_context": str(extra_context),
            "tool_schemas": [],
            "mailbox_messages": [],
        }
