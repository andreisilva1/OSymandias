<div align="center">

<img src="banner.svg" width="100%"/>

*"Look on my works, ye Mighty, and dispatch."*

**Multi-agent runtime for Python developers. One command to start everything.**

[![PyPI](https://img.shields.io/pypi/v/osymandias?style=flat-square&color=C8A040)](https://pypi.org/project/osymandias)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml/badge.svg)](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml)

</div>

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

Open [http://localhost:47759](http://localhost:47759) — dashboard.  
API directly at [http://localhost:47760/api/v1](http://localhost:47760/api/v1).

To manage the runtime:

```bash
osy stop    # pause containers, keep data
osy down    # remove containers, keep volumes
osy delete  # remove containers + volumes (asks for confirmation)
```

**No Docker?** Use `--no-docker` to connect to externally managed services instead:

```bash
# Uncomment in .env and point to your own instances:
# OSY_NO_DOCKER=1
# OSY_POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/osymandias
# OSY_REDIS_URL=redis://host:6379/0
# OSY_RABBITMQ_URL=amqp://user:pass@host:5672/
# OSY_QDRANT_URL=http://host:6333

osy serve --no-docker
```

---

## Built-in tool functions (`@osy.tool`)

Your Python functions become agent tools with a single decorator:

```python
from osymandias import osy

@osy.tool
def fetch_competitor_data(company: str, metrics: list[str]) -> dict:
    """Fetch competitor metrics from internal database."""
    return {"company": company, "data": [...]}

@osy.tool
def send_slack_message(channel: str, text: str) -> dict:
    """Send a message to a Slack channel."""
    return {"ok": True}
```

Schema inferred from type hints. `osy serve` scans all `.py` files automatically — no YAML, no config files. Tools are then assignable to agents from the dashboard (`/tools`).

---

## External agents (`@osy.agent`)

Register any Python callable — LangChain chain, CrewAI crew, LlamaIndex query engine, or plain Python — as an OSymandias agent:

```python
from osymandias import osy, OsyContext

@osy.agent("ResearchAgent", framework="langchain",
           description="Searches and summarises web content",
           llm_provider="ollama", llm_model="qwen2.5:7b")
def research_agent(task: str, ctx: OsyContext) -> dict:
    chain = build_langchain_chain()
    ctx.emit_event("TASK_PROGRESS", {"step": "running chain"})
    return {"summary": chain.invoke(task)}
```

**All kwargs are optional metadata for the dashboard.** The agent executes regardless of what's declared.

| kwarg | Purpose |
|---|---|
| `framework` | Badge color in registry (`crewai`, `langchain`, `llamaindex`, `smolagents`, `autogen`) |
| `description` | Shown in agent detail panel |
| `llm_provider` / `llm_model` | Informational — displayed in dashboard |
| `output_schema` | Pydantic model or JSON Schema dict |
| `input_schema` | Pydantic model or JSON Schema dict |
| `tools` | Tool names this agent uses (informational) |

Declare which modules to scan in `osymandias.toml` (project root):

```toml
agent_modules = [
    "myproject.agents",
    "myproject.crews",
]
```

Agents in those modules are discovered and registered automatically on `osy serve`.

---

## OsyContext

Every `@osy.agent` function optionally receives an `OsyContext` as its `ctx` parameter:

```python
@osy.agent("OrchestratorAgent")
def orchestrate(task: str, ctx: OsyContext) -> dict:

    # shared memory — any agent in the same job can read/write
    ctx.write_memory("plan", {"step": 1, "goal": task})
    data = ctx.read_memory("previous_output")

    # live events — streamed to the dashboard event feed
    ctx.emit_event("TASK_PROGRESS", {"pct": 50, "message": "halfway"})

    # sub-tasks — spawn child tasks and wait for results
    task_ids = ctx.spawn_tasks([
        {"title": "Research", "agent_type": "ResearchAgent", "description": task},
        {"title": "Analyse",  "agent_type": "AnalystAgent",  "description": task},
    ])
    results = ctx.wait_for_tasks(task_ids)

    return {"merged": results}
```

| Method | Description |
|---|---|
| `ctx.write_memory(key, value)` | Write to shared job memory |
| `ctx.read_memory(key)` | Read from shared job memory |
| `ctx.emit_event(type, payload)` | Stream event to dashboard live feed |
| `ctx.spawn_tasks(list)` | Spawn sub-tasks; returns list of task IDs |
| `ctx.wait_for_tasks(ids)` | Block until all sub-tasks complete; returns their outputs |

Sub-tasks are visible as a tree in the job timeline dashboard.

---

## Three ways to give agents tools

| | What | How |
|---|---|---|
| **Built-in** | `web_search`, `read_url`, `http_request`, `write_to_job_memory`, `search_memory`, `python_eval`, `run_shell`, `read_file`, `write_file`, `send_message`, `spawn_agent` … (20 total) | Zero config — always available |
| **`@osy.tool`** | Your Python functions | Decorate + `osy serve` |
| **Webhook** | Any HTTP endpoint | Register URL in the dashboard |

---

## How it works

```
Job        →  A user-submitted goal ("research and write a report on X")
  └── Task ×N  →  Subtask assigned to a specific agent type
        └── AgentInstance  →  A running agent loop (LLM + tools + memory)
              ├── ToolCall  →  web_search / @osy.tool / webhook / ...
              └── Sub-task  →  ctx.spawn_tasks([...]) → child Task ×N
```

Jobs are decomposed into tasks by a PlannerAgent. Tasks execute in parallel across specialized agents. External agents registered via `@osy.agent` are dispatched via Celery — same queue, same observability. An EvaluatorAgent scores outputs and retries if confidence is below threshold.

---

## Dashboard pages

| Page | Path | Description |
|------|------|-------------|
| Jobs | `/jobs` | Job list with search, filter, pagination |
| Job detail | `/jobs/{id}` | Output, events, tasks, sub-task tree timeline |
| Agents | `/agents` | Agent registry — builtin and external, adaptive detail panel |
| Tools | `/tools` | Built-in and user tools |
| Memory | `/memory` | Search, filter by scope, delete entries |
| Events | `/events` | Live event stream with pause/resume |
| Metrics | `/metrics` | 7-day chart, tokens, cost, success rate |

---

## Supported LLM providers

| Provider | Key |
|---|---|
| OpenAI | `OPENAI_API_KEY` |
| Anthropic | `ANTHROPIC_API_KEY` |
| DeepSeek | `DEEPSEEK_API_KEY` |
| Groq | `GROQ_API_KEY` |
| Gemini | `GEMINI_API_KEY` |
| Ollama (local) | no key needed |

Switch models per-agent from the dashboard — no restart required.

---

## Spawning a job via API

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"title":"My Job","description":"Research the EV market in Europe in 2024.","priority":"NORMAL","input_payload":{}}'
```

Full API reference: **http://localhost:47760/api/v1/docs**

---

## Repo structure

```
OSymandias/
├── sdk/                  Python package — osymandias + osy CLI
│   └── osymandias/
│       ├── cli/          osy init / serve / stop / down / delete
│       ├── runtime/      FastAPI + Celery + agents
│       ├── decorator.py  @osy.tool + @osy.agent
│       ├── context.py    OsyContext (memory, events, sub-tasks)
│       ├── discovery.py  @osy.tool scanner
│       ├── tool_server.py  local HTTP tool server
│       ├── assets.py     GitHub asset fetcher + cache
│       └── process.py    subprocess manager
├── frontend/             Next.js 14 dashboard (built by CI, not bundled in wheel)
├── backend/              Legacy standalone backend (kept for reference)
├── fut_dev/              Slide assets + publication
└── .github/workflows/
    └── release.yml       Tag push → build → GitHub Release + PyPI
```

---

## Contributing

```bash
git clone https://github.com/andreisilva1/OSymandias
cd OSymandias

# Install the sdk in editable mode
pip install -e ./sdk

# Scaffold config files
osy init

# Start infra + API (the local frontend/out build is picked up automatically)
osy serve

# For live frontend development (separate terminal)
cd frontend
npm install
npm run dev   # http://localhost:3000 — hot reload
```

---

<div align="center">
<sub>Built with FastAPI · Next.js · Celery · PostgreSQL · Redis · RabbitMQ · Qdrant · LiteLLM</sub>
</div>
