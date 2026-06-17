"""
ContextBuilder — assembles the prompt context for each LLM iteration.
Respects a token budget and prioritises content by importance.
"""
from __future__ import annotations

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from osymandias.runtime.models import AgentDefinition, Message, Task
from osymandias.runtime.models.memory_entry import MemoryScope

# Approximate tokens per character (rough estimate)
CHARS_PER_TOKEN = 4
DEFAULT_TOKEN_BUDGET = 6000  # reserved for context injection


def _estimate_tokens(text: str) -> int:
    return max(1, len(text) // CHARS_PER_TOKEN)


class ContextBuilder:
    def __init__(
        self,
        session: Session,
        agent_instance_id: uuid.UUID,
        job_id: uuid.UUID,
        task_id: uuid.UUID | None,
        agent_definition: AgentDefinition,
    ):
        self.session = session
        self.agent_instance_id = agent_instance_id
        self.job_id = job_id
        self.task_id = task_id
        self.definition = agent_definition

    def build(self, task: Task, token_budget: int = DEFAULT_TOKEN_BUDGET) -> dict[str, Any]:
        """
        Returns a dict with:
        - system_prompt: str
        - injected_context: str  (injected as a user message before the conversation)
        - tool_schemas: list[dict]
        - mailbox_messages: list[dict]
        """
        budget = token_budget
        sections: list[str] = []

        # --- Mailbox (highest priority after system prompt) ---
        mailbox = self._load_mailbox()
        if mailbox:
            block = self._format_mailbox(mailbox)
            if _estimate_tokens(block) <= budget * 0.3:
                sections.append(block)
                budget -= _estimate_tokens(block)

        # --- Task memory ---
        task_mem = self._load_task_memory()
        if task_mem:
            block = self._format_memory_block("Task memory (your previous progress)", task_mem)
            if _estimate_tokens(block) <= budget * 0.3:
                sections.append(block)
                budget -= _estimate_tokens(block)

        # --- Job memory (semantic search) ---
        job_mem = self._load_job_memory_semantic(task.description or task.title, top_k=5)
        if job_mem:
            block = self._format_memory_block("Relevant job memory from other agents", job_mem)
            if _estimate_tokens(block) <= budget * 0.3:
                sections.append(block)
                budget -= _estimate_tokens(block)

        # --- System prompt (render template) ---
        system_prompt = self._render_system_prompt(task)

        return {
            "system_prompt": system_prompt,
            "injected_context": "\n\n".join(sections),
            "tool_schemas": self._load_tool_schemas(),
            "mailbox_messages": mailbox,
        }

    # ------------------------------------------------------------------

    def _render_system_prompt(self, task: Task) -> str:
        template = self.definition.system_prompt_template
        return (
            template
            .replace("{{task_description}}", task.description or task.title)
            .replace("{{job_context}}", f"Job ID: {self.job_id}")
        )

    def _load_mailbox(self) -> list[dict[str, Any]]:
        messages = self.session.scalars(
            select(Message).where(
                Message.receiver_agent_instance_id == self.agent_instance_id,
                Message.is_read == False,  # noqa: E712
            ).order_by(Message.sent_at)
        ).all()
        return [
            {"from": str(m.sender_agent_instance_id), "subject": m.subject, "content": m.content}
            for m in messages
        ]

    def _load_task_memory(self) -> list[dict[str, Any]]:
        if not self.task_id:
            return []
        from osymandias.runtime.memory.manager import MemoryManager
        return MemoryManager.read_all_sync(self.session, MemoryScope.TASK, self.task_id)

    def _load_job_memory_semantic(self, query: str, top_k: int) -> list[dict[str, Any]]:
        from osymandias.runtime.memory.manager import MemoryManager
        results = MemoryManager.search_sync(
            query=query,
            scopes=[MemoryScope.JOB],
            scope_ids=[self.job_id],
            top_k=top_k,
            session=self.session,
        )
        return [{"key": r["key"], "value": r["value"]} for r in results]

    def _load_tool_schemas(self) -> list[dict[str, Any]]:
        schemas = []
        for tool_name in self.definition.allowed_tools:
            from osymandias.runtime.models import ToolDefinition
            td = self.session.get(ToolDefinition, tool_name)
            if td and td.is_active:
                schemas.append({
                    "type": "function",
                    "function": {
                        "name": td.name,
                        "description": td.description,
                        "parameters": td.input_schema,
                    },
                })
        return schemas

    @staticmethod
    def _format_mailbox(messages: list[dict]) -> str:
        lines = ["## Messages from other agents"]
        for m in messages:
            lines.append(f"From: {m['from']} | Subject: {m['subject']}")
            lines.append(f"Content: {m['content']}")
        return "\n".join(lines)

    @staticmethod
    def _format_memory_block(header: str, entries: list[dict]) -> str:
        lines = [f"## {header}"]
        for e in entries:
            lines.append(f"[{e['key']}]: {e['value']}")
        return "\n".join(lines)
