# OSymandias

> Multi-agent runtime for Python developers. One command to start everything.

[![PyPI](https://img.shields.io/pypi/v/osymandias?style=flat-square&color=C8A040)](https://pypi.org/project/osymandias)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](https://github.com/andreisilva1/OSymandias/blob/main/LICENSE)
[![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)](https://github.com/andreisilva1/OSymandias)

**[Full documentation → GitHub](https://github.com/andreisilva1/OSymandias/blob/main/DOCS_en.md)**

---

## What is this?

**OSymandias** is a Python library and CLI that turns your project into a full multi-agent runtime.

```bash
pip install osymandias
osy init
osy serve
```

PostgreSQL, Redis, RabbitMQ, Qdrant — managed internally via Docker. Dashboard at `localhost:47759`. Four Celery workers ready.

---

## Quick start

**Prerequisites:** Python 3.11+, Docker

```bash
pip install osymandias

# Generate OSY.compose.yml + OSY.nginx.conf + .env + sample osy_tools.py
osy init

# Start everything
osy serve
```

Open `http://localhost:47759` — dashboard.
API directly at `http://localhost:47760/api/v1`.

```bash
osy stop    # pause containers, keep data
osy down    # remove containers, keep volumes
osy delete  # remove containers + volumes (asks for confirmation)
osy logs <job-id> -f  # live-stream events
```

---

## Built-in tool functions (`@osy.tool`)

```python
from osymandias import osy

@osy.tool
def fetch_competitor_data(company: str, metrics: list[str]) -> dict:
    """Fetch competitor metrics from internal database."""
    return {"company": company, "data": [...]}
```

Schema inferred from type hints. `osy serve` scans all `.py` files automatically — no YAML, no config files.

---

## External agents (`@osy.agent`)

Register any Python callable — LangChain chain, CrewAI crew, LlamaIndex query engine, or plain Python — as an OSymandias agent:

```python
from osymandias import osy, OsyContext

@osy.agent("ResearchAgent", framework="langchain",
           description="Searches and summarises web content")
def research_agent(task: str, ctx: OsyContext) -> dict:
    chain = build_langchain_chain()
    ctx.emit_event("TASK_PROGRESS", {"step": "running chain"})
    return {"summary": chain.invoke(task)}
```

Works with any framework: LangChain, CrewAI, LlamaIndex, Smolagents, OpenAI Agents SDK, plain Python.

---

## OsyContext

Every `@osy.agent` function optionally receives an `OsyContext` as its `ctx` parameter:

```python
@osy.agent("OrchestratorAgent")
def orchestrate(task: str, ctx: OsyContext) -> dict:

    # shared memory — any agent in the same job can read/write
    ctx.write_memory("plan", {"step": 1, "goal": task})

    # live events — streamed to the dashboard
    ctx.emit_event("TASK_PROGRESS", {"pct": 50})

    # sub-tasks — spawn child tasks and wait for results
    task_ids = ctx.spawn_tasks([
        {"title": "Research", "agent_type": "ResearchAgent", "description": task},
        {"title": "Analyse",  "agent_type": "AnalystAgent",  "description": task},
    ])
    return {"merged": ctx.wait_for_tasks(task_ids)}
```

| Method | Description |
|---|---|
| `ctx.write_memory(key, value)` | Write to shared job memory |
| `ctx.read_memory(key)` | Read from shared job memory |
| `ctx.emit_event(type, payload)` | Stream event to dashboard live feed |
| `ctx.spawn_tasks(list)` | Spawn sub-tasks in parallel |
| `ctx.wait_for_tasks(ids)` | Block until all sub-tasks complete |

---

## Supported LLM providers

OpenAI · Anthropic · DeepSeek · Groq · Gemini · Ollama (local)

Switch models per-agent from the dashboard — no restart required.

---

## How it works

```
Job        →  A user-submitted goal
  └── Task ×N  →  Subtask assigned to a specific agent type
        └── AgentInstance  →  A running agent loop (LLM + tools + memory)
              ├── ToolCall  →  web_search / @osy.tool / webhook / ...
              └── Sub-task  →  ctx.spawn_tasks([...]) → child Task ×N
```

Jobs are decomposed by a built-in PlannerAgent that sees all registered agents and routes tasks optimally. Tasks execute in parallel across specialized agents.

---

**[Full documentation → GitHub](https://github.com/andreisilva1/OSymandias/blob/main/DOCS_en.md)**

---

<sub>Built with FastAPI · Celery · PostgreSQL · Redis · RabbitMQ · Qdrant · LiteLLM · Next.js</sub>
