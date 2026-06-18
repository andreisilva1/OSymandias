# OSymandias — Documentation

> Complete API reference and usage guide.

---

## Table of Contents

1. [Installation](#installation)
2. [CLI reference](#cli-reference)
   - [osy --version](#osy---version)
3. [Authentication](#authentication)
4. [@osy.tool — built-in tools](#osytool)
5. [@osy.agent — external agents](#osyagent)
6. [osymandias.toml](#osymandiastoml)
7. [OsyContext](#osycontext)
8. [Adapters](#adapters)
   - [LangChain](#langchain)
   - [CrewAI](#crewai)
   - [LlamaIndex](#llamaindex)
   - [Smolagents](#smolagents)
   - [OpenAI Agents SDK](#openai-agents-sdk)
9. [Submitting jobs via API](#submitting-jobs-via-api)
   - [Natural language job](#natural-language-job)
   - [Explicit task plan (`__task_plan__`)](#explicit-task-plan-__task_plan__)
   - [Resubmitting a job](#resubmitting-a-job)
10. [Dashboard pages](#dashboard-pages)
11. [Supported LLM providers](#supported-llm-providers)
12. [Scaling](#scaling)
13. [Optional dependencies](#optional-dependencies)

---

## Installation

```bash
pip install osymandias
```

**Prerequisites:** Python 3.11+, Docker (used to manage the infrastructure containers).

Optional framework extras:

```bash
pip install osymandias[langchain]
pip install osymandias[crewai]
pip install osymandias[llamaindex]
pip install osymandias[smolagents]
pip install osymandias[openai-agents]

# All at once
pip install osymandias[all]
```

---

## CLI reference

### `osy --version`

Print the installed version and exit.

```bash
osy --version   # osy 0.3.0
osy -V
```

---

### `osy init`

Scaffold a new OSymandias project in the current directory.

```
osy init
```

Interactive prompts ask for your LLM provider and API key. Creates:

| File | Purpose |
|---|---|
| `OSY.compose.yml` | Docker Compose file for all infrastructure containers |
| `OSY.nginx.conf` | Nginx config that serves the dashboard on port 47759 |
| `.env` | LLM provider keys and runtime config |
| `osy_tools.py` | Sample `@osy.tool` file to get started |
| `osymandias.toml` | Project config stub (agent_modules commented out) |

Safe to re-run — existing files are skipped.

---

### `osy serve`

Start the full runtime.

```
osy serve [--no-docker] [--concurrency N]
```

Starts Docker containers, runs DB migrations, discovers `@osy.tool` and `@osy.agent` callables, and launches:


| Service | Port |
|---|---|
| Dashboard (nginx) | `47759` |
| FastAPI backend | `47760` |
| Internal tool server | `47761` |

**`--no-docker` mode** — skip Docker entirely and connect to externally managed services:

```bash
# In .env — uncomment and update URLs to your own instances:
# OSY_NO_DOCKER=1
# OSY_POSTGRES_URL=postgresql+asyncpg://user:pass@my-db.example.com:5432/osymandias
# OSY_REDIS_URL=redis://my-redis.example.com:6379/0
# OSY_RABBITMQ_URL=amqp://user:pass@my-rabbit.example.com:5672/
# OSY_QDRANT_URL=http://my-qdrant.example.com:6333

osy serve --no-docker
# or: OSY_NO_DOCKER=1 osy serve
```

`osy serve --no-docker` verifies connectivity to all configured services before starting and gives a clear error if any are unreachable. `osy stop` and `osy down` skip Docker gracefully when not available.

**`--concurrency N`** — number of concurrent Celery worker slots on this node (default 4). Also reads from `OSY_WORKER_CONCURRENCY` in `.env`.

---

### `osy logs`

Tail events for a specific job or the global event stream.

```
osy logs [JOB_ID] [--follow] [--limit N] [--type EVENT_TYPE]
```

| Option | Default | Description |
|---|---|---|
| `JOB_ID` | — | Job ID or unambiguous prefix. Omit for all jobs. |
| `--follow` / `-f` | off | Subscribe to Redis pub/sub and stream live events |
| `--limit N` / `-n N` | `50` | Number of past events to print before streaming |
| `--type` / `-t` | — | Filter by event type (e.g. `TASK_PROGRESS`, `TOOL_CALL_STARTED`) |

```bash
osy logs                             # last 50 events across all jobs
osy logs abc123                      # last 50 events for job abc123...
osy logs abc123 -f                   # live-stream all events for that job
osy logs abc123 -f -t TASK_PROGRESS  # live-stream only progress events
```

---

### `osy workers`

Start **additional** Celery workers for horizontal scaling. No API server, no Docker — just worker processes connecting to the shared RabbitMQ and Redis.

```
osy workers [--queues QUEUES] [--concurrency N] [--loglevel LEVEL]
```

| Option | Default | Env var |
|---|---|---|
| `--queues` | `agents,tools,evaluator` | `OSY_WORKER_QUEUES` |
| `--concurrency` | `4` | `OSY_WORKER_CONCURRENCY` |
| `--loglevel` | `warning` | — |

Run this on any machine that can reach the same broker/backend. See [Scaling](#scaling).

---

### `osy stop`

Pause all containers without deleting data.

```
osy stop
```

---

### `osy down`

Stop and remove containers, but keep volumes (PostgreSQL data, Qdrant vectors).

```
osy down
```

---

### `osy delete`

Stop and remove containers **and** volumes. Asks for confirmation before deleting.

```
osy delete
```

> **Warning:** This permanently deletes all jobs, memory, and agent data.

---

## Authentication

OSymandias includes an optional static API key gate. Auth is **disabled by default** — no configuration needed for local development.

### Enabling auth

Set `OSY_API_KEY` in `.env` (or as an environment variable):

```bash
# .env
OSY_API_KEY=my-secret-key
```

Restart `osy serve`. All `/api/v1/*` endpoints now require the key. `/health`, `/docs`, and `/openapi.json` are always exempt.

### Sending the key

Either header works:

```bash
# Authorization header (Bearer scheme)
curl -H "Authorization: Bearer my-secret-key" http://localhost:47760/api/v1/jobs

# X-Api-Key header
curl -H "X-Api-Key: my-secret-key" http://localhost:47760/api/v1/jobs
```

Requests without a valid key receive `401 Unauthorized`.

### Disabling auth

Remove `OSY_API_KEY` from `.env` (or set it to an empty string) and restart.

---

## @osy.tool

Register any Python function as an agent tool. Tools are available to builtin agents via the dashboard (`/tools` page).

```python
from osymandias import osy

@osy.tool
def my_tool(arg1: str, arg2: int = 0) -> dict:
    """One-line description shown in the dashboard."""
    return {"result": ...}
```

**Rules:**
- The function name becomes the tool name.
- The docstring first line becomes the description.
- Parameter types and defaults are inferred from type hints.
- Return type must be `dict` (or JSON-serialisable).

**Example — multiple tools:**

```python
from osymandias import osy

@osy.tool
def search_database(query: str, limit: int = 10) -> dict:
    """Search internal product database. Returns matching items."""
    rows = db.execute("SELECT * FROM products WHERE ...", (query, limit))
    return {"items": [dict(r) for r in rows]}

@osy.tool
def send_slack_message(channel: str, text: str) -> dict:
    """Post a message to a Slack channel."""
    slack_client.chat_postMessage(channel=channel, text=text)
    return {"ok": True}
```

Tools are discovered automatically — no registration call needed. Any `.py` file in your project that imports `osymandias` is scanned on `osy serve`.

---

## @osy.agent

Register any Python callable as an external OSymandias agent. The agent is dispatched via Celery and appears in the `/agents` dashboard with a coloured badge.

```python
from osymandias import osy, OsyContext

@osy.agent("MyAgent")
def my_agent(task: str, ctx: OsyContext) -> dict:
    ...
    return {"result": ...}
```

### Signature

```python
osy.agent(
    name: str,
    *,
    description: str = "",
    framework: str | None = None,
    llm_provider: str | None = None,
    llm_model: str | None = None,
    output_schema = None,
    input_schema = None,
    tools: list[str] | None = None,
) -> Callable
```

### Parameters

| Parameter | Type | Description |
|---|---|---|
| `name` | `str` | **Required.** Display name and dispatch key. Must be unique. |
| `description` | `str` | Human-readable description shown in the agent detail panel. |
| `framework` | `str \| None` | Explicit framework declaration. Controls the badge colour in the registry. Accepted values: `"crewai"`, `"langchain"`, `"llamaindex"`, `"smolagents"`, `"autogen"`. Any other string is shown as-is. |
| `llm_provider` | `str \| None` | Provider used internally (e.g. `"ollama"`, `"openai"`). Informational only. |
| `llm_model` | `str \| None` | Model used internally (e.g. `"qwen2.5:7b"`). Informational only. |
| `output_schema` | Pydantic model or `dict` | JSON Schema describing the return shape. Shown in the detail panel. |
| `input_schema` | Pydantic model or `dict` | JSON Schema describing expected input beyond `task: str`. |
| `tools` | `list[str] \| None` | Names of tools this agent is known to use. Informational only. |

> **All kwargs are optional.** The agent executes regardless of what is declared. They exist purely to enrich the dashboard display.

### Adaptive agent registry

External agents are automatically included in the PlannerAgent's context on every job. When a natural language job is submitted (no `__task_plan__`), the planner receives the full list of available agent types — builtin *and* external — and can route tasks to any of them by name. No configuration required: register an agent with `@osy.agent`, and the planner discovers it on the next `osy serve`.

```
osy serve          ← discovers @osy.agent callables, seeds DB
↓
POST /jobs {"title": "...", "description": "Research EVs and write a summary"}
↓
PlannerAgent        ← sees: ResearchAgent, WriterAgent, AnalystAgent,
                           MyCustomAgent [langchain] (external), ...
↓
Creates tasks routed to the right agents automatically
```

### Callable signature

The decorated function must accept `task: str` as its first argument and return a `dict`. The `ctx: OsyContext` parameter is optional — include it to access memory, events, and sub-tasks.

```python
# Minimum
@osy.agent("EchoAgent")
def echo(task: str) -> dict:
    return {"result": task}

# With context
@osy.agent("EchoAgent")
def echo(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "echoing"})
    return {"result": task}
```

### Full example

```python
from pydantic import BaseModel
from osymandias import osy, OsyContext

class ResearchOutput(BaseModel):
    summary: str
    sources: list[str]
    confidence: float

@osy.agent(
    "ResearchAgent",
    framework="langchain",
    description="Searches the web and summarises findings",
    llm_provider="ollama",
    llm_model="qwen2.5:7b",
    output_schema=ResearchOutput,
)
def research_agent(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "starting research"})
    chain = build_chain()
    result = chain.invoke(task)
    ctx.write_memory("research_output", {"summary": result})
    return {"summary": result, "sources": [], "confidence": 0.9}
```

---

## osymandias.toml

Declare which Python modules contain your `@osy.agent` callables. Placed in the project root (created automatically by `osy init`).

```toml
# osymandias.toml

agent_modules = [
    "myproject.agents",
    "myproject.crews",
    "myproject.pipelines.research",
]
```

On `osy serve`, each module is imported in order and all `@osy.agent` decorators in those modules are executed, populating the agent registry.

**Fallback:** If `agent_modules` is absent or the file has no entries, `osy serve` falls back to scanning all `.py` files in the project directory that import `osymandias`. This is convenient during development but slower for large projects.

**Alternative:** You can also declare the modules in `pyproject.toml`:

```toml
[tool.osymandias]
agent_modules = ["myproject.agents"]
```

`osymandias.toml` takes priority over `pyproject.toml` if both exist.

---

## OsyContext

`OsyContext` is injected as the `ctx` parameter of every `@osy.agent` callable at execution time. It provides access to the job's shared memory, the live event stream, and sub-task spawning — all scoped to the current job.

```python
from osymandias import OsyContext
```

---

### `ctx.write_memory(key, value)`

Write a value to the current job's shared memory.

```python
ctx.write_memory(key: str, value: dict) -> None
```

- Overwrites any previous value at the same key.
- All agents in the same job share the same namespace — a LangChain agent can read what a CrewAI agent wrote.
- Flushed immediately within the current DB transaction.

```python
ctx.write_memory("plan", {
    "steps": ["research", "analyse", "write"],
    "priority": "high",
})
```

---

### `ctx.read_memory(key)`

Read a previously written value from job memory.

```python
ctx.read_memory(key: str) -> dict | None
```

Returns `None` if the key does not exist yet.

```python
plan = ctx.read_memory("plan")
if plan:
    steps = plan["steps"]
```

---

### `ctx.search_memory(query, top_k=5)`

Semantic vector search over all memory entries in the current job.

```python
ctx.search_memory(query: str, top_k: int = 5) -> list[dict]
```

Uses Qdrant embeddings. Useful for retrieving relevant past outputs without knowing the exact key.

```python
entries = ctx.search_memory("competitor pricing", top_k=3)
for e in entries:
    print(e["key"], e["value"])
```

---

### `ctx.emit_event(event, data)`

Emit an event that is streamed live to the dashboard SSE feed.

```python
ctx.emit_event(event: str, data: dict) -> None
```

Events appear instantly in the job's event timeline. Common conventions (not enforced):

| Event type | Typical payload |
|---|---|
| `"TASK_PROGRESS"` | `{"pct": 50, "step": "analysing"}` |
| `"AGENT_LOG"` | `{"message": "found 12 sources"}` |
| Any custom string | Any dict |

```python
ctx.emit_event("TASK_PROGRESS", {"pct": 25, "step": "fetching sources"})
ctx.emit_event("AGENT_LOG", {"message": f"query returned {n} results"})
```

---

### `ctx.spawn_tasks(task_defs)`

Spawn one or more child tasks that run under the current task.

```python
ctx.spawn_tasks(task_defs: list[dict]) -> list[uuid.UUID]
```

Each child task is enqueued immediately on the Celery scheduler and runs in parallel. Tasks appear as a tree under the parent task in the job timeline.

**task_def keys:**

| Key | Required | Description |
|---|---|---|
| `title` | Yes | Display name for the sub-task |
| `agent_type` | No | Name of the registered agent to dispatch to (default: `"ResearchAgent"`) |
| `description` | No | Input context passed to the agent |

Returns a list of task UUIDs in the same order as `task_defs`.

```python
ids = ctx.spawn_tasks([
    {
        "title": "Market Research",
        "agent_type": "ResearchAgent",
        "description": f"Research the EV market: {task}",
    },
    {
        "title": "Competitor Analysis",
        "agent_type": "AnalystAgent",
        "description": f"Analyse top EV competitors for: {task}",
    },
])
```

---

### `ctx.wait_for_tasks(task_ids, timeout=90)`

Block until all specified child tasks reach a terminal state (completed, failed, or cancelled).

```python
ctx.wait_for_tasks(task_ids: list[uuid.UUID], timeout: int = 90) -> dict[str, dict]
```

Subscribes to the job's Redis pub/sub channel and wakes immediately when each task completes — no fixed polling interval. Falls back to a final DB read to cover the edge case where a task finished before the subscription was established. Returns results for all tasks regardless of success or failure — check individual dicts for an `"error"` key if needed.

**Returns:** `{task_title: output_result_dict}`

Tasks that do not complete within `timeout` seconds are logged as a warning; their entry in the result dict will be `{}`.

```python
ids = ctx.spawn_tasks([...])
results = ctx.wait_for_tasks(ids, timeout=120)

research   = results.get("Market Research", {})
competitor = results.get("Competitor Analysis", {})

ctx.write_memory("combined", {**research, **competitor})
return {"merged": results}
```

---

## Adapters

Adapters wrap third-party framework objects so their output conforms to the `dict` return type expected by `@osy.agent`. Each adapter is in `osymandias.adapters.*`.

---

### LangChain

```bash
pip install osymandias[langchain]
```

```python
from osymandias.adapters.langchain import LangChainAdapter
```

Wraps any LangChain **LCEL Runnable** (chains, prompt | llm | parser pipelines) or legacy **AgentExecutor**. Automatically attaches an `OsyCallbackHandler` that forwards `on_llm_start`, `on_tool_start`, etc. as `TASK_PROGRESS` events to the dashboard.

```python
from langchain_core.prompts import ChatPromptTemplate
from langchain_ollama import ChatOllama
from osymandias import osy, OsyContext
from osymandias.adapters.langchain import LangChainAdapter

llm = ChatOllama(model="qwen2.5:7b")
prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful research assistant."),
    ("human", "{input}"),
])
chain = prompt | llm

@osy.agent("ResearchAgent", framework="langchain", llm_model="qwen2.5:7b")
def research_agent(task: str, ctx: OsyContext) -> dict:
    return LangChainAdapter(chain).run(task, ctx=ctx)
```

**`LangChainAdapter.run(task, ctx=None) → dict`**

Invokes the chain with `{"input": task}`. If `ctx` is provided, attaches the callback handler. Normalises the result to `dict` automatically (handles `str`, Pydantic models, and raw dicts).

---

### CrewAI

```bash
pip install osymandias[crewai]
```

```python
from osymandias.adapters.crewai import CrewAIAdapter
```

Wraps a `Crew` object. The crew runs as a black box — internal agent handoffs within the crew are not individually tracked in OSy. Use `ctx.emit_event` manually inside CrewAI callbacks if intermediate progress is needed.

```python
from crewai import Agent, Crew, Task
from osymandias import osy, OsyContext
from osymandias.adapters.crewai import CrewAIAdapter

researcher = Agent(role="Researcher", goal="Find accurate data", backstory="...", llm="ollama/qwen2.5:7b")
analyst    = Agent(role="Analyst",    goal="Interpret findings", backstory="...", llm="ollama/qwen2.5:7b")

crew = Crew(
    agents=[researcher, analyst],
    tasks=[
        Task(description="Research {task}", agent=researcher),
        Task(description="Analyse findings", agent=analyst),
    ],
    verbose=False,
)

@osy.agent("AnalystCrew", framework="crewai")
def analyst_crew(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "crew starting"})
    result = CrewAIAdapter(crew).run(task, ctx=ctx)
    ctx.write_memory("crew_output", result)
    return result
```

**`CrewAIAdapter.run(task, ctx=None) → dict`**

Calls `crew.kickoff(inputs={"task": task})`. Normalises `CrewOutput.raw` to `dict`.

---

### LlamaIndex

```bash
pip install osymandias[llamaindex]
```

```python
from osymandias.adapters.llamaindex import LlamaIndexAdapter
```

Wraps a `QueryEngine` (uses `.query()`) or a `ReActAgent` (uses `.chat()`). Source nodes from retrieval are included in the result under `"sources"`. Images found in source node metadata are collected under `"_media"` for dashboard multi-modal rendering.

```python
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader
from osymandias import osy, OsyContext
from osymandias.adapters.llamaindex import LlamaIndexAdapter

docs  = SimpleDirectoryReader("./data").load_data()
index = VectorStoreIndex.from_documents(docs)
engine = index.as_query_engine()

@osy.agent("RAGAgent", framework="llamaindex", description="Answers questions from local documents")
def rag_agent(task: str, ctx: OsyContext) -> dict:
    return LlamaIndexAdapter(engine).run(task, ctx=ctx)
```

**`LlamaIndexAdapter.run(task, ctx=None) → dict`**

Returns `{"output": str, "sources": list[str], "_media": list[dict]}`.

---

### Smolagents

```bash
pip install osymandias[smolagents]
```

```python
from osymandias.adapters.smolagents import SmolAgentsAdapter
```

Wraps any HuggingFace Smolagents agent. If the agent returns a `matplotlib.figure.Figure` or `PIL.Image`, it is base64-encoded and placed under `"_media"` for dashboard rendering.

```python
from smolagents import CodeAgent, HfApiModel
from osymandias import osy, OsyContext
from osymandias.adapters.smolagents import SmolAgentsAdapter

agent = CodeAgent(
    tools=[],
    model=HfApiModel("meta-llama/Llama-3.2-3B-Instruct"),
)

@osy.agent("HFCoder", framework="smolagents")
def hf_agent(task: str, ctx: OsyContext) -> dict:
    return SmolAgentsAdapter(agent).run(task, ctx=ctx)
```

**`SmolAgentsAdapter.run(task, ctx=None) → dict`**

Calls `agent.run(task)`. Returns `{"output": str}` for text, or `{"output": "figure", "_media": [...]}` for image outputs.

---

### OpenAI Agents SDK

```bash
pip install osymandias[openai-agents]
```

```python
from osymandias.adapters.openai_agents import OpenAIAgentsAdapter
```

Wraps an OpenAI Agents SDK `Agent`. Agent handoffs are emitted as `TASK_PROGRESS` events so the handoff chain is visible in the dashboard SSE stream.

```python
from agents import Agent
from osymandias import osy, OsyContext
from osymandias.adapters.openai_agents import OpenAIAgentsAdapter

agent = Agent(
    name="Assistant",
    instructions="You are a helpful assistant.",
    model="gpt-4o",
)

@osy.agent("GPT4Agent", framework="openai-agents", llm_provider="openai", llm_model="gpt-4o")
def gpt4_agent(task: str, ctx: OsyContext) -> dict:
    return OpenAIAgentsAdapter(agent).run(task, ctx=ctx)
```

**`OpenAIAgentsAdapter.run(task, ctx=None) → dict`**

Calls `Runner.run_sync(agent, task)`. Emits one `TASK_PROGRESS` event per handoff message if `ctx` is provided.

---

## Submitting jobs via API

### Natural language job

Let the PlannerAgent decompose the goal into tasks automatically:

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "EV Market Report",
    "description": "Research the European EV market in 2024 and write a structured report.",
    "priority": "NORMAL",
    "input_payload": {}
  }'
```

**Priority values:** `"LOW"` · `"NORMAL"` · `"HIGH"` · `"CRITICAL"`

### Explicit task plan (`__task_plan__`)

Bypass the PlannerAgent entirely by providing a task list directly in `input_payload`. Useful when you know exactly which agents to run and in what order:

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{
    "title": "EV Market Report",
    "description": "EV market research",
    "priority": "NORMAL",
    "input_payload": {
      "__task_plan__": [
        {"title": "Research",      "agent_type": "ResearchAgent", "description": "EV market in Europe 2024"},
        {"title": "Write Report",  "agent_type": "WriterAgent",   "description": "Write a structured report from research findings"}
      ]
    }
  }'
```

Each entry in `__task_plan__` accepts the same keys as `ctx.spawn_tasks` task defs: `title` (required), `agent_type`, `description`.

### Resubmitting a job

Copy a completed or failed job's input and create a new run:

```bash
curl -X POST http://localhost:47760/api/v1/jobs/<job-id>/resubmit
```

Returns the new job object. The original job is unchanged. The resubmit button is also available in the dashboard job detail view for any terminal job (COMPLETED, FAILED, CANCELLED).

### Python

```python
import httpx

resp = httpx.post("http://localhost:47760/api/v1/jobs", json={
    "title": "EV Market Report",
    "description": "Research the European EV market in 2024.",
    "priority": "NORMAL",
    "input_payload": {},
})
job = resp.json()
print(job["id"])
```

Full interactive API docs: **http://localhost:47760/api/v1/docs**

---

## Dashboard pages

| Page | URL | Description |
|------|-----|-------------|
| Jobs | `/jobs` | Job list — search, filter by status, pagination |
| Job detail | `/jobs/{id}` | Output viewer (JSON/markdown/image/audio), events feed, task tree timeline, resubmit button |
| Agents | `/agents` | Agent registry — builtin and external agents, adaptive detail panel, filter by type/framework |
| Tools | `/tools` | Built-in tools and `@osy.tool` functions |
| Memory | `/memory` | Browse and search job/agent memory entries, delete individual keys |
| Events | `/events` | Global live event stream — pause/resume, filter by job |
| Metrics | `/metrics` | 7-day charts: jobs, tokens, cost estimate, success rate |

### Live output preview

While a job is running, the OUTPUT tab shows a live preview of in-progress tasks. Each time an agent calls `ctx.emit_event("TASK_PROGRESS", {...})`, the dashboard updates the task card in real time via SSE — no polling required. Once the job completes and `output_payload` is available, the final output replaces the preview automatically.

---

## Supported LLM providers

Configured during `osy init` or by editing `.env` directly.

| Provider | `.env` key | Example model |
|---|---|---|
| Ollama (local) | *(none required)* | `llama3.2`, `qwen2.5:7b` |
| OpenAI | `OPENAI_API_KEY` | `gpt-4o`, `gpt-4o-mini` |
| Anthropic | `ANTHROPIC_API_KEY` | `claude-sonnet-4-6` |
| DeepSeek | `DEEPSEEK_API_KEY` | `deepseek-chat` |
| Groq | `GROQ_API_KEY` | `llama-3.3-70b-versatile` |
| Gemini | `GEMINI_API_KEY` | `gemini-2.0-flash` |

Models can be changed per-agent from the dashboard without restarting the runtime.

---

## Scaling

OSymandias scales horizontally by running additional Celery worker processes on separate machines. The API server, scheduler, and workers are independent — only RabbitMQ (task queue) and Redis (results + pub/sub) need to be reachable from all nodes.

### Queue architecture

| Queue | Handles | Concurrency recommendation |
|---|---|---|
| `scheduler` | DAG resolution, job dispatch | 1 (single-worker, avoid race conditions) |
| `agents` | Agent loops (LLM calls) | Scale out — most CPU/wait time here |
| `tools` | `@osy.tool` and webhook calls | Scale with agent workers |
| `evaluator` | Output scoring | Low volume; 1-2 slots sufficient |

The `scheduler` queue should stay on one machine (the one running `osy serve`). `agents`, `tools`, and `evaluator` can be distributed freely.

### Local concurrency

Increase slots on a single machine via `--concurrency` or `.env`:

```bash
# .env
OSY_WORKER_CONCURRENCY=8

# or at startup
osy serve --concurrency 8
```

### Horizontal scaling (multiple machines)

```bash
# ── Machine A — runs API + scheduler ──────────────────────────────
osy serve --no-docker   # or with Docker

# ── Machine B — extra agent workers ───────────────────────────────
# Point to the shared broker/redis in .env or env vars
OSY_RABBITMQ_URL=amqp://user:pass@machine-a:47764/ \
OSY_REDIS_URL=redis://machine-a:47763/0 \
osy workers --queues agents,tools --concurrency 8

# ── Machine C — dedicated evaluator ───────────────────────────────
OSY_RABBITMQ_URL=amqp://user:pass@machine-a:47764/ \
OSY_REDIS_URL=redis://machine-a:47763/0 \
osy workers --queues evaluator --concurrency 2
```

Worker nodes need `osymandias` installed and access to the same `osymandias.toml` (or the same `@osy.agent` modules importable). They do **not** need PostgreSQL access — the API server is the only process that talks directly to Postgres.

### Kubernetes / container deployments

Each Celery worker is a stateless process. A typical deployment:

| Deployment | Command | Replicas |
|---|---|---|
| API | `uvicorn osymandias.runtime.main:app` | 1-2 |
| Agent workers | `celery -A osymandias.runtime.workers.celery_app worker --queues agents,tools` | N |
| Scheduler | `celery -A osymandias.runtime.workers.celery_app worker --queues scheduler --concurrency 1` | 1 |
| Beat | `celery -A osymandias.runtime.workers.celery_app beat` | 1 |

All worker containers share the same RabbitMQ broker and Redis backend via environment variables.

---

## Optional dependencies

| Extra | Installs |
|---|---|
| `osymandias[langchain]` | `langchain-core`, `langchain` |
| `osymandias[crewai]` | `crewai` |
| `osymandias[llamaindex]` | `llama-index-core` |
| `osymandias[smolagents]` | `smolagents` |
| `osymandias[openai-agents]` | `openai-agents` |
| `osymandias[all]` | All of the above |

The base `osymandias` package has no framework dependencies — extras are only required if you use the corresponding adapter.
