<div align="right">
  <b>English</b> · <a href="README.pt-br.md">Português BR</a>
</div>

<div align="center">

<img src="banner.svg" width="100%"/>

*"Look on my works, ye Mighty, and dispatch."*

**Multi-agent runtime for Python developers. One command to start everything.**

[![PyPI](https://img.shields.io/pypi/v/osymandias?style=flat-square&color=C8A040)](https://pypi.org/project/osymandias)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml/badge.svg)](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml)
[![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)](https://github.com/andreisilva1/OSymandias)

📖 **Documentation:** [English](DOCS_en.md) · [Português BR](DOCS_pt-br.md)

</div>

---

```bash
pip install osymandias && osy init && osy serve
```

PostgreSQL · Redis · RabbitMQ · Qdrant · 4 Celery workers · dashboard at `localhost:47759` — all from one command.

---

## The problem

Building a multi-agent system means wiring together a task queue, a vector store, a message broker, shared memory between agents, a way to observe what's happening, and glue code to hold it all together. Before writing a single agent.

**OSymandias is that infrastructure.** Decorate your functions. Submit a goal in plain English. Watch it run.

---

## How it works

```mermaid
flowchart LR
    J(["📋 Job\nplain English goal"])
    P["⚙️ PlannerAgent\nauto-decomposes"]
    T1["🤖 ResearchAgent"]
    T2["🤖 WriterAgent"]
    T3["🤖 YourAgent\n@osy.agent"]
    E["✅ EvaluatorAgent\nscores & retries"]
    O(["📄 Output"])

    J --> P
    P --> T1 & T2 & T3
    T1 & T2 & T3 --> E
    E --> O
```

Each agent has access to 20 built-in tools (web search, file I/O, HTTP, Python eval…), your `@osy.tool` functions, and shared memory — all observable in real time from the dashboard.

---

## Three concepts

### 1 — Turn any function into an agent tool

```python
from osymandias import osy

@osy.tool
def fetch_pricing(company: str) -> dict:
    """Fetch live pricing from internal database."""
    return db.query(company)
```

Schema inferred from type hints. No YAML. No registration. Just `osy serve`.

---

### 2 — Plug in any framework as an agent

```python
from osymandias import osy, OsyContext

@osy.agent("ResearchAgent", framework="langchain", llm_model="qwen2.5:7b")
def research(task: str, ctx: OsyContext) -> dict:
    ctx.emit_event("TASK_PROGRESS", {"step": "searching"})
    return {"summary": my_chain.invoke(task)}
```

LangChain · CrewAI · LlamaIndex · Smolagents · OpenAI Agents SDK · plain Python — all work the same way. The PlannerAgent discovers and routes to your agents automatically on `osy serve`.

---

### 3 — Orchestrate from inside an agent

```python
@osy.agent("OrchestratorAgent")
def orchestrate(task: str, ctx: OsyContext) -> dict:
    ids = ctx.spawn_tasks([
        {"title": "Research", "agent_type": "ResearchAgent", "description": task},
        {"title": "Analyse",  "agent_type": "AnalystAgent",  "description": task},
    ])
    results = ctx.wait_for_tasks(ids)       # parallel, Redis pub/sub — no polling
    ctx.write_memory("combined", results)   # shared across all agents in the job
    return results
```

---

## Production controls

The hard part of agents isn't getting them to answer — it's making them safe to run unattended.

- **Token budget caps** — set `max_tokens` on a job; it halts with `BUDGET_EXCEEDED` before a runaway loop burns your quota.
- **Human-in-the-loop gates** — mark a task `requires_approval`; it waits in `HUMAN_REVIEW` until you approve it via the API.
- **Lifecycle webhooks** — register a URL and get a POST on `JOB_COMPLETED` / `JOB_FAILED` / `BUDGET_EXCEEDED`.
- **Real cost & token tracking** — per-agent and per-tool breakdown, priced via LiteLLM.
- **Execution traces** — the full reasoning chain (events, tool calls, conversation) for any task.
- **Response cache** — opt-in deterministic LLM cache that cuts cost on retries and replays.

```bash
# Budget-capped job that pauses for approval
curl -X POST localhost:47760/api/v1/jobs -d '{"title":"...","max_tokens":50000}'
curl -X POST localhost:47760/api/v1/jobs/$ID/tasks/$TASK/approve
```

---

## Dashboard

![OSymandias dashboard](assets/dashboard_preview.png)

> *Illustrative — actual UI may differ.*

Real-time event stream via SSE. Sub-task tree. Output preview while the job runs. Resubmit any job with one click.

---

## Supported LLM providers

OpenAI · Anthropic · DeepSeek · Groq · Gemini · **Ollama (local, no key needed)**

Switch models per-agent from the dashboard — no restart required.

---

<details>
<summary>No Docker? External services?</summary>

```bash
# .env — uncomment and point to your own instances
OSY_NO_DOCKER=1
OSY_POSTGRES_URL=postgresql+asyncpg://user:pass@host:5432/osymandias
OSY_REDIS_URL=redis://host:6379/0
OSY_RABBITMQ_URL=amqp://user:pass@host:5672/
OSY_QDRANT_URL=http://host:6333

osy serve --no-docker
```

</details>

<details>
<summary>Scale to multiple machines</summary>

```bash
# Node A — API + scheduler
osy serve

# Node B — extra agent workers (point to shared broker/redis)
OSY_RABBITMQ_URL=amqp://... OSY_REDIS_URL=redis://... \
  osy workers --queues agents,tools --concurrency 8
```

</details>

---

<div align="center">
<sub>Built with FastAPI · Next.js · Celery · PostgreSQL · Redis · RabbitMQ · Qdrant · LiteLLM</sub>
</div>
