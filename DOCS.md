# OSymandias — Documentation

> Complete API reference and usage guide.

---

## Table of Contents

1. [Installation](#installation)
2. [CLI reference](#cli-reference)
3. [@osy.tool — built-in tools](#osytool)
4. [@osy.agent — external agents](#osyagent)
5. [osymandias.toml](#osymandiastoml)
6. [OsyContext](#osycontext)
7. [Adapters](#adapters)
   - [LangChain](#langchain)
   - [CrewAI](#crewai)
   - [LlamaIndex](#llamaindex)
   - [Smolagents](#smolagents)
   - [OpenAI Agents SDK](#openai-agents-sdk)
8. [Submitting jobs via API](#submitting-jobs-via-api)
9. [Dashboard pages](#dashboard-pages)
10. [Supported LLM providers](#supported-llm-providers)
11. [Optional dependencies](#optional-dependencies)

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
osy serve [--no-docker]
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

Polls the database every second. Returns results for all tasks regardless of success or failure — check individual dicts for an `"error"` key if needed.

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

### REST

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
| Job detail | `/jobs/{id}` | Output viewer (JSON/markdown/image/audio), events feed, task tree timeline |
| Agents | `/agents` | Agent registry — builtin and external agents, adaptive detail panel, filter by type/framework |
| Tools | `/tools` | Built-in tools and `@osy.tool` functions |
| Memory | `/memory` | Browse and search job/agent memory entries, delete individual keys |
| Events | `/events` | Global live event stream — pause/resume, filter by job |
| Metrics | `/metrics` | 7-day charts: jobs, tokens, cost estimate, success rate |

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
