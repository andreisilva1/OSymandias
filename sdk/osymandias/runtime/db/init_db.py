"""
Seeds AgentDefinitions and ToolDefinitions on first startup.
Run via: python -m osymandias.runtime.db.init_db
"""
import asyncio

from loguru import logger
from sqlalchemy import select

from osymandias.runtime.db.session import AsyncSessionLocal
from osymandias.runtime.models import AgentDefinition, ToolDefinition

BUILTIN_TOOLS = [
    # ── Web / network ─────────────────────────────────────────────────────────
    {
        "name": "web_search",
        "description": "Search the web for information given a query string.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
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
            "properties": {
                "url": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 15},
            },
            "required": ["url"],
        },
        "output_schema": {"type": "object", "properties": {"content": {"type": "string"}, "status_code": {"type": "integer"}}},
        "rate_limit_per_minute": 60,
        "requires_external_api": True,
    },
    {
        "name": "http_request",
        "description": "Make an HTTP request to any URL with configurable method, headers, and body.",
        "input_schema": {
            "type": "object",
            "properties": {
                "url": {"type": "string"},
                "method": {"type": "string", "enum": ["GET", "POST", "PUT", "PATCH", "DELETE"], "default": "GET"},
                "headers": {"type": "object"},
                "body": {"type": "object"},
            },
            "required": ["url"],
        },
        "output_schema": {"type": "object", "properties": {"status_code": {"type": "integer"}, "body": {"type": "object"}}},
        "rate_limit_per_minute": 60,
        "requires_external_api": True,
    },
    # ── Memory ────────────────────────────────────────────────────────────────
    {
        "name": "write_to_job_memory",
        "description": "Persist a key-value pair to job-scoped memory so other agents can access it.",
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
    {
        "name": "list_memory_keys",
        "description": "List all keys stored in job-scoped memory.",
        "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "array", "items": {"type": "string"}},
        "requires_external_api": False,
    },
    # ── Agent communication ───────────────────────────────────────────────────
    {
        "name": "send_message",
        "description": "Send a typed message to another agent running in the same job.",
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
        "name": "spawn_agent",
        "description": "Dynamically spawn a child agent to handle a sub-task.",
        "input_schema": {
            "type": "object",
            "properties": {
                "agent_type": {"type": "string"},
                "task_title": {"type": "string"},
                "task_description": {"type": "string"},
                "depends_on": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["agent_type", "task_title", "task_description"],
        },
        "output_schema": {"type": "object", "properties": {"task_id": {"type": "string"}}},
        "requires_external_api": False,
    },
    # ── Code / compute ────────────────────────────────────────────────────────
    {
        "name": "python_eval",
        "description": "Execute a Python code snippet in a sandboxed environment and return stdout + result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 10},
            },
            "required": ["code"],
        },
        "output_schema": {"type": "object", "properties": {"stdout": {"type": "string"}, "result": {}, "error": {"type": "string"}}},
        "requires_external_api": False,
    },
    {
        "name": "run_shell",
        "description": "Run a shell command and return stdout and stderr.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string"},
                "timeout_seconds": {"type": "integer", "default": 30},
            },
            "required": ["command"],
        },
        "output_schema": {"type": "object", "properties": {"stdout": {"type": "string"}, "stderr": {"type": "string"}, "exit_code": {"type": "integer"}}},
        "requires_external_api": False,
    },
    # ── File system ───────────────────────────────────────────────────────────
    {
        "name": "read_file",
        "description": "Read the contents of a file from the local filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "encoding": {"type": "string", "default": "utf-8"},
            },
            "required": ["path"],
        },
        "output_schema": {"type": "object", "properties": {"content": {"type": "string"}, "size_bytes": {"type": "integer"}}},
        "requires_external_api": False,
    },
    {
        "name": "write_file",
        "description": "Write or append text content to a file on the local filesystem.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "mode": {"type": "string", "enum": ["write", "append"], "default": "write"},
            },
            "required": ["path", "content"],
        },
        "output_schema": {"type": "object", "properties": {"written_bytes": {"type": "integer"}}},
        "requires_external_api": False,
    },
    {
        "name": "list_directory",
        "description": "List files and directories at the given path.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "pattern": {"type": "string", "default": "*"},
            },
            "required": ["path"],
        },
        "output_schema": {"type": "array", "items": {"type": "object", "properties": {"name": {"type": "string"}, "is_dir": {"type": "boolean"}, "size_bytes": {"type": "integer"}}}},
        "requires_external_api": False,
    },
    # ── Text processing ───────────────────────────────────────────────────────
    {
        "name": "extract_json",
        "description": "Extract and parse the first valid JSON object or array found in a text string.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
        "output_schema": {"type": "object", "properties": {"parsed": {}, "raw": {"type": "string"}}},
        "requires_external_api": False,
    },
    {
        "name": "parse_csv",
        "description": "Parse a CSV string into a list of row objects keyed by column headers.",
        "input_schema": {
            "type": "object",
            "properties": {
                "csv_text": {"type": "string"},
                "delimiter": {"type": "string", "default": ","},
            },
            "required": ["csv_text"],
        },
        "output_schema": {"type": "array", "items": {"type": "object"}},
        "requires_external_api": False,
    },
    # ── Utilities ─────────────────────────────────────────────────────────────
    {
        "name": "get_current_time",
        "description": "Return the current UTC datetime and Unix timestamp.",
        "input_schema": {"type": "object", "properties": {"timezone": {"type": "string", "default": "UTC"}}},
        "output_schema": {"type": "object", "properties": {"iso": {"type": "string"}, "unix": {"type": "number"}, "timezone": {"type": "string"}}},
        "requires_external_api": False,
    },
    {
        "name": "wait",
        "description": "Pause execution for the specified number of seconds (max 60).",
        "input_schema": {
            "type": "object",
            "properties": {"seconds": {"type": "number", "minimum": 0.1, "maximum": 60}},
            "required": ["seconds"],
        },
        "output_schema": {"type": "object", "properties": {"slept_seconds": {"type": "number"}}},
        "requires_external_api": False,
    },
    {
        "name": "log_event",
        "description": "Emit a structured log event visible in the Event Stream dashboard.",
        "input_schema": {
            "type": "object",
            "properties": {
                "level": {"type": "string", "enum": ["DEBUG", "INFO", "WARNING", "ERROR"], "default": "INFO"},
                "message": {"type": "string"},
                "data": {"type": "object"},
            },
            "required": ["message"],
        },
        "output_schema": {"type": "object", "properties": {"logged": {"type": "boolean"}}},
        "requires_external_api": False,
    },
    {
        "name": "format_output",
        "description": "Format a data structure as JSON, Markdown table, or plain text for the final job output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {},
                "format": {"type": "string", "enum": ["json", "markdown", "plain"], "default": "json"},
            },
            "required": ["data"],
        },
        "output_schema": {"type": "object", "properties": {"formatted": {"type": "string"}}},
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
            "You are a PlannerAgent. Break the job into 2-4 tasks.\n\n"
            "AVAILABLE AGENT TYPES — use the exact names shown:\n"
            "{{available_agents}}\n\n"
            "MEMORY RULE:\n"
            '- AnalystAgent: start description with \'Read job memory key "ResearchAgent". \'\n'
            '- WriterAgent: start description with \'Read job memory key "AnalystAgent". \'\n\n'
            "DEPENDENCY RULE: if task B needs task A output, put A title in B depends_on list.\n\n"
            "Example:\n"
            '{"tasks":['
            '{"title":"Research","description":"Research the topic.","agent_type":"ResearchAgent","depends_on":[]},'
            '{"title":"Write Report","description":"Read job memory key \\"ResearchAgent\\". Write the final report.","agent_type":"WriterAgent","depends_on":["Research"]}'
            "]}\n\n"
            "Output ONLY the JSON object. No markdown. No extra text.\n\n"
            "Job: {{job_description}}"
        ),
        "allowed_tools": [],
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
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
            "AVAILABLE TOOLS — use ONLY these exact names:\n"
            "{{available_tools}}\n\n"
            "YOU MUST CALL TOOLS BEFORE OUTPUTTING ANYTHING.\n\n"
            "STEP 1: Call web_search with a relevant query. Do this now.\n"
            "STEP 2: Call read_url on 2-3 of the most relevant URLs from the search results.\n"
            "STEP 3: Only after completing steps 1 and 2, output a JSON object with these keys:\n"
            "  - summary: a string with your overall summary\n"
            "  - findings: an object with the key facts you found\n"
            "  - sources: a list of URL strings you read\n\n"
            "Do NOT output JSON before calling tools. Do NOT invent tool names."
        ),
        "allowed_tools": ["web_search", "read_url", "write_to_job_memory", "read_from_job_memory", "search_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
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
            "AVAILABLE TOOLS — use ONLY these exact names:\n"
            "{{available_tools}}\n\n"
            "STEP 1: Call read_from_job_memory with the key mentioned in your task description to get the data.\n"
            "STEP 2: Write a well-structured document based on the retrieved data.\n"
            "STEP 3: Output a JSON object with these keys:\n"
            "  - title: a string title for the document\n"
            "  - content: the full document text in markdown\n"
            "  - format: the string 'markdown'\n\n"
            "Do NOT output JSON before calling read_from_job_memory. Do NOT invent tool names."
        ),
        "allowed_tools": ["read_from_job_memory", "search_memory", "write_to_job_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
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
            "Task: {{task_description}}\n\n"
            "AVAILABLE TOOLS — use ONLY these exact names:\n"
            "{{available_tools}}\n\n"
            "STEP 1: Call read_from_job_memory with key \"ResearchAgent\" to retrieve the research data.\n"
            "   If that returns nothing, try key \"research\" or key \"Research\".\n"
            "STEP 2: Analyse the retrieved data thoroughly — identify key trends, patterns, and conclusions.\n"
            "STEP 3: Output a JSON object with these keys:\n"
            "  - insights: a list of strings, each describing a key insight from the data\n"
            "  - data: an object containing structured data extracted from the research\n\n"
            "Do NOT output JSON before calling read_from_job_memory. Do NOT invent tool names."
        ),
        "allowed_tools": ["read_from_job_memory", "search_memory", "write_to_job_memory", "send_message"],
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
        "max_iterations": 6,
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
            "Acceptance criteria: {{criteria}}\n\n"
            "Score the output from 0.0 to 1.0 and provide concise feedback.\n"
            "Set 'passed' to true if score >= 0.7, false otherwise.\n\n"
            "Output ONLY this JSON — no markdown, no explanation:\n"
            '{"score": 0.0, "feedback": "...", "passed": false}'
        ),
        "allowed_tools": [],
        "llm_provider": "ollama",
        "llm_model": "qwen2.5:7b",
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
    from osymandias.runtime.models.agent_definition import AGENT_KIND_BUILTIN, AGENT_KIND_EXTERNAL

    async with AsyncSessionLocal() as session:
        for tool_data in BUILTIN_TOOLS:
            existing = await session.get(ToolDefinition, tool_data["name"])
            if not existing:
                session.add(ToolDefinition(**tool_data))

        for agent_data in BUILTIN_AGENTS:
            existing = await session.get(AgentDefinition, agent_data["name"])
            if not existing:
                session.add(AgentDefinition(**agent_data, agent_kind=AGENT_KIND_BUILTIN))
            else:
                # Always update prompt and config so changes take effect on restart
                existing.system_prompt_template = agent_data["system_prompt_template"]
                existing.allowed_tools = agent_data["allowed_tools"]
                existing.llm_provider = agent_data["llm_provider"]
                existing.llm_model = agent_data["llm_model"]
                existing.max_iterations = agent_data["max_iterations"]
                existing.timeout_seconds = agent_data["timeout_seconds"]
                existing.agent_kind = AGENT_KIND_BUILTIN

        # Seed external agents registered via @osy.agent decorator
        from osymandias.decorator import _AGENT_REGISTRY
        for entry in _AGENT_REGISTRY.values():
            existing = await session.get(AgentDefinition, entry.name)
            if not existing:
                session.add(AgentDefinition(
                    name=entry.name,
                    version="1.0",
                    description=entry.description,
                    role="external",
                    system_prompt_template="",  # external agents own their logic
                    allowed_tools=entry.tools,
                    llm_provider=entry.llm_provider or "",
                    llm_model=entry.llm_model or "",
                    input_schema=entry.input_schema,
                    output_schema=entry.output_schema or None,
                    agent_kind=AGENT_KIND_EXTERNAL,
                    callable_ref=entry.callable_ref,
                    framework=entry.framework,
                    requires_approval=entry.requires_approval,
                    is_active=True,
                ))
            else:
                existing.description = entry.description
                existing.allowed_tools = entry.tools
                existing.input_schema = entry.input_schema
                existing.output_schema = entry.output_schema or existing.output_schema
                existing.agent_kind = AGENT_KIND_EXTERNAL
                existing.callable_ref = entry.callable_ref
                existing.framework = entry.framework
                existing.requires_approval = entry.requires_approval

        await session.commit()
    logger.info("Seed complete.")


if __name__ == "__main__":
    asyncio.run(seed())
