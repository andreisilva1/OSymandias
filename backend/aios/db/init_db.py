"""
Seeds AgentDefinitions and ToolDefinitions on first startup.
Run via: python -m aios.db.init_db
"""
import asyncio

from loguru import logger
from sqlalchemy import select

from aios.db.session import AsyncSessionLocal
from aios.models import AgentDefinition, ToolDefinition

BUILTIN_TOOLS = [
    {
        "name": "web_search",
        "description": "Search the web for information given a query string.",
        "input_schema": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "rate_limit_per_minute": 30,
        "requires_external_api": True,
    },
    {
        "name": "read_url",
        "description": "Fetch and extract the text content of a URL.",
        "input_schema": {
            "type": "object",
            "properties": {"url": {"type": "string"}},
            "required": ["url"],
        },
        "output_schema": {"type": "object", "properties": {"content": {"type": "string"}}},
        "rate_limit_per_minute": 60,
        "requires_external_api": True,
    },
    {
        "name": "send_message",
        "description": "Send a message to another agent in the same job.",
        "input_schema": {
            "type": "object",
            "properties": {
                "to": {"type": "string"},
                "subject": {"type": "string"},
                "message_type": {"type": "string", "enum": ["TASK_RESULT", "DATA_SHARE", "REQUEST", "BROADCAST"]},
                "content": {"type": "object"},
            },
            "required": ["to", "subject", "message_type", "content"],
        },
        "output_schema": {"type": "object", "properties": {"delivered": {"type": "boolean"}}},
        "requires_external_api": False,
    },
    {
        "name": "write_to_job_memory",
        "description": "Persist a value to job-scoped memory so other agents can access it.",
        "input_schema": {
            "type": "object",
            "properties": {
                "key": {"type": "string"},
                "value": {"type": "object"},
                "embed": {"type": "boolean", "default": False},
            },
            "required": ["key", "value"],
        },
        "output_schema": {"type": "object", "properties": {"stored": {"type": "boolean"}}},
        "requires_external_api": False,
    },
    {
        "name": "read_from_job_memory",
        "description": "Read a value from job-scoped memory by key.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string"}},
            "required": ["key"],
        },
        "output_schema": {"type": "object"},
        "requires_external_api": False,
    },
    {
        "name": "search_memory",
        "description": "Semantic search across memory entries accessible to this agent.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "top_k": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "requires_external_api": False,
    },
]

BUILTIN_AGENTS = [
    {
        "name": "PlannerAgent",
        "version": "1.0",
        "description": "Decomposes a high-level job into a DAG of tasks.",
        "role": "supervisor",
        "system_prompt_template": (
            "You are a PlannerAgent in an AI Operating System.\n"
            "Decompose the job below into 2-4 subtasks.\n\n"
            "AVAILABLE AGENT TYPES (use EXACTLY these names, case-sensitive):\n"
            "- ResearchAgent\n"
            "- WriterAgent\n"
            "- AnalystAgent\n"
            "- EvaluatorAgent\n\n"
            "Output ONLY a JSON object, no markdown, no explanation:\n"
            '{"tasks": [{"title": "...", "description": "...", "agent_type": "ResearchAgent", "depends_on": []}]}\n\n'
            "Job: {{job_description}}"
        ),
        "allowed_tools": [],
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "max_iterations": 3,
        "timeout_seconds": 60,
        "output_schema": {
            "type": "object",
            "properties": {
                "tasks": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "title": {"type": "string"},
                            "description": {"type": "string"},
                            "agent_type": {"type": "string"},
                            "depends_on": {"type": "array", "items": {"type": "string"}},
                        },
                        "required": ["title", "description", "agent_type"],
                    },
                }
            },
            "required": ["tasks"],
        },
    },
    {
        "name": "ResearchAgent",
        "version": "1.0",
        "description": "Searches the web and extracts information.",
        "role": "researcher",
        "system_prompt_template": (
            "You are a ResearchAgent in an AI Operating System.\n"
            "Task: {{task_description}}\n\n"
            "INSTRUCTIONS:\n"
            "1. Call web_search 1-3 times maximum to gather information.\n"
            "2. Optionally call write_to_job_memory to store key findings.\n"
            "3. After gathering enough information, output your final answer as JSON.\n\n"
            "IMPORTANT: You MUST end by outputting ONLY a JSON object like this:\n"
            '{"summary": "...", "findings": {...}, "sources": [...]}\n\n'
            "Do NOT keep calling tools indefinitely. 3 searches is the maximum."
        ),
        "allowed_tools": ["web_search", "read_url", "write_to_job_memory", "read_from_job_memory", "search_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "max_iterations": 8,
        "timeout_seconds": 120,
        "output_schema": {
            "type": "object",
            "properties": {
                "summary": {"type": "string"},
                "sources": {"type": "array", "items": {"type": "string"}},
                "findings": {"type": "object"},
            },
            "required": ["summary", "findings"],
        },
    },
    {
        "name": "WriterAgent",
        "version": "1.0",
        "description": "Produces written reports and documents from structured data.",
        "role": "writer",
        "system_prompt_template": (
            "You are a WriterAgent in an AI Operating System.\n"
            "Task: {{task_description}}\n\n"
            "INSTRUCTIONS:\n"
            "1. Optionally call read_from_job_memory or search_memory once to get context.\n"
            "2. Write the document based on the task and any retrieved context.\n"
            "3. Output your final answer as JSON immediately after.\n\n"
            "IMPORTANT: Output ONLY a JSON object like this:\n"
            '{"title": "...", "content": "...", "format": "markdown"}\n\n'
            "Do NOT call tools more than twice. Write the document from what you know."
        ),
        "allowed_tools": ["read_from_job_memory", "search_memory", "write_to_job_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "max_iterations": 5,
        "timeout_seconds": 120,
        "output_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "content": {"type": "string"},
                "format": {"type": "string", "enum": ["markdown", "plain"]},
            },
            "required": ["title", "content"],
        },
    },
    {
        "name": "AnalystAgent",
        "version": "1.0",
        "description": "Analyses structured data and produces insights.",
        "role": "analyst",
        "system_prompt_template": (
            "You are an AnalystAgent in an AI Operating System.\n"
            "Task: {{task_description}}\n"
            "Read the data from job memory, analyse it, and return structured insights."
        ),
        "allowed_tools": ["read_from_job_memory", "search_memory", "write_to_job_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "max_iterations": 15,
        "timeout_seconds": 120,
        "output_schema": {
            "type": "object",
            "properties": {
                "insights": {"type": "array", "items": {"type": "string"}},
                "data": {"type": "object"},
            },
            "required": ["insights"],
        },
    },
    {
        "name": "EvaluatorAgent",
        "version": "1.0",
        "description": "Evaluates the quality of another agent's output against acceptance criteria.",
        "role": "evaluator",
        "system_prompt_template": (
            "You are an EvaluatorAgent in an AI Operating System.\n"
            "Output to evaluate: {{output}}\n"
            "Acceptance criteria: {{criteria}}\n"
            "Score the output from 0.0 to 1.0 and provide feedback.\n"
            "Return JSON with 'score' (float) and 'feedback' (string)."
        ),
        "allowed_tools": [],
        "llm_provider": "ollama",
        "llm_model": "llama3.2",
        "max_iterations": 3,
        "timeout_seconds": 60,
        "output_schema": {
            "type": "object",
            "properties": {
                "score": {"type": "number", "minimum": 0.0, "maximum": 1.0},
                "feedback": {"type": "string"},
                "passed": {"type": "boolean"},
            },
            "required": ["score", "feedback", "passed"],
        },
    },
]


async def seed():
    async with AsyncSessionLocal() as session:
        for tool_data in BUILTIN_TOOLS:
            existing = await session.get(ToolDefinition, tool_data["name"])
            if not existing:
                session.add(ToolDefinition(**tool_data))

        for agent_data in BUILTIN_AGENTS:
            existing = await session.get(AgentDefinition, agent_data["name"])
            if not existing:
                session.add(AgentDefinition(**agent_data))
            else:
                # Always update prompt and config so changes take effect on restart
                existing.system_prompt_template = agent_data["system_prompt_template"]
                existing.allowed_tools = agent_data["allowed_tools"]
                existing.llm_provider = agent_data["llm_provider"]
                existing.llm_model = agent_data["llm_model"]

        await session.commit()
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
