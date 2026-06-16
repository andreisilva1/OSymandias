<div align="center">

<img src="banner.svg" width="100%"/>

*"Look on my works, ye Mighty, and dispatch."*

**Multi-agent runtime. Spawn jobs. Watch agents think. Build your own tools.**

[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688?style=flat-square&logo=fastapi)](https://fastapi.tiangolo.com)
[![Next.js](https://img.shields.io/badge/Next.js-14-000000?style=flat-square&logo=next.js)](https://nextjs.org)
[![Celery](https://img.shields.io/badge/Celery-5-37814A?style=flat-square&logo=celery)](https://docs.celeryq.dev)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-4169E1?style=flat-square&logo=postgresql)](https://postgresql.org)
[![Docker](https://img.shields.io/badge/Docker-Compose-2496ED?style=flat-square&logo=docker)](https://docs.docker.com/compose)
[![Tests](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml/badge.svg)](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml)
![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)

</div>

---

## What is this?

**OSymandias** is a multi-agent runtime that treats AI workloads like an operating system treats processes.

You submit a **job** — a goal in natural language. A PlannerAgent breaks it into tasks. Specialized agents (researcher, writer, analyst) execute each task in parallel or in sequence, calling tools, writing to shared memory, and streaming every event back to a live dashboard.

The result: you see exactly what the agents are thinking, which tools they called, how many tokens they spent — and you can extend the system with your own tools without writing any agent code.

---

## Core concepts

```
Job        →  A user-submitted goal ("research and write a report on X")
  └── Task ×N  →  Subtask assigned to a specific agent type
        └── AgentInstance  →  A running agent loop (LLM + tools + memory)
              └── ToolCall  →  A syscall invocation (web_search, your webhook, ...)
```

**Syscalls** are tools agents can invoke. Built-ins (Python functions) live in the registry. **User-defined syscalls** are webhook endpoints — register a URL and agents will POST to it transparently, no code changes needed.

---

## Architecture

```mermaid
graph TB
    subgraph UI["Dashboard — Next.js 14 + TanStack Query"]
        D[Pages: jobs / agents / tools / memory / events]
        SSE[SSE live event stream]
    end

    subgraph API["FastAPI :8000"]
        R[REST endpoints]
        STREAM["SSE /jobs/{id}/events"]
    end

    subgraph Workers["Celery Workers"]
        SCHED[scheduler — DAG resolution]
        AGENT[agents — LLM loops]
        EVAL[evaluator — scoring]
        BEAT[beat — metrics/60s]
    end

    subgraph LLMs["LLM Providers via LiteLLM"]
        OL[Ollama\nlocal] --- OP[OpenAI]
        AN[Anthropic] --- DS[DeepSeek]
        GR[Groq] --- GE[Gemini]
    end

    subgraph Storage
        PG[(Postgres\n+ pgvector)]
        RD[(Redis\npub/sub)]
        RB[(RabbitMQ)]
        QD[(Qdrant\nvectors)]
    end

    UI -->|REST| API
    SSE -.->|EventSource| STREAM
    API --> RB --> SCHED & AGENT & EVAL
    AGENT --> LLMs
    AGENT --> PG & QD
    AGENT -->|publish| RD -->|subscribe| STREAM
```

---

## Quick start

**Prerequisites:** Docker, Docker Compose, and one LLM provider.

```bash
# 1. Clone
git clone https://github.com/andreisilva1/OSymandias && cd OSymandias

# 2. Configure
cp .env.example .env
# Edit .env — set at least one provider (see below)

# 3. If using Ollama (local, free) — do this BEFORE docker compose up
#    Install from https://ollama.com, then:
ollama serve          # must be running in the background
ollama pull llama3.2  # pull the default model

# 4. Start everything
docker compose up -d

# 5. Open the dashboard
open http://localhost:3001
```

> **Ollama users — common pitfall:** if you skip `ollama serve` + `ollama pull llama3.2` before starting Docker, every job will get stuck in **PLANNING** with an `APIConnectionError` in the worker logs. The Docker workers reach Ollama on the host via `host.docker.internal:11434`, so Ollama must be running on the host before the containers start.

### Choosing a provider

| Provider | Setup |
|----------|-------|
| **Ollama** (local, free) | 1. Install [ollama.com](https://ollama.com) · 2. Run `ollama serve` · 3. Run `ollama pull llama3.2` · 4. Set `LLM_DEFAULT_PROVIDER=ollama` in `.env` |
| **OpenAI** | Set `OPENAI_API_KEY=sk-...` |
| **Anthropic** | Set `ANTHROPIC_API_KEY=sk-ant-...` |
| **DeepSeek** | Set `DEEPSEEK_API_KEY=sk-...` |
| **Groq** | Set `GROQ_API_KEY=gsk_...` |
| **Gemini** | Set `GEMINI_API_KEY=AI...` |

> Add a key once, restart Docker once. After that, switch individual agents between providers freely from the UI — no restart needed.

---

## Spawning your first job

Navigate to **Processes** (`/jobs`) and click **SPAWN** in the top-right corner. A modal opens with four fields:

| Field | Purpose | Example |
|-------|---------|---------|
| **Title** | Short label shown in the process list | `Market Research Report` |
| **Description** | The actual goal — the more detail, the better the plan | `Research the EV market in Europe in 2024. Summarize key players, market share, and trends. Write a structured report.` |
| **Priority** | `HIGH` jumps the queue; `NORMAL` / `LOW` are scheduled in order | `NORMAL` |
| **Input Payload** | Optional JSON the agents can read via `input_payload` key | `{}` or `{"region": "EU", "year": 2024}` |

> **Tip — writing good descriptions:** The PlannerAgent reads the description verbatim to decompose the job into tasks. Be explicit about the output format you want (`"write a markdown report"`, `"produce a comparison table"`), the data sources to use, and any constraints (`"use only sources from 2024"`). Vague descriptions produce generic plans; specific descriptions produce targeted pipelines.

Click **SPAWN** and switch to the **Live Event Stream** tab to watch agents spin up in real time, call `web_search` and `read_url`, write findings to shared memory, and hand off results to each other. The aggregated output appears under **Processes → [job] → OUTPUT** when the job completes.

---

## Agent flow

```mermaid
sequenceDiagram
    participant U as You
    participant P as PlannerAgent
    participant R as ResearchAgent
    participant W as WriterAgent

    U->>P: Job: "Write a report on X"
    P->>P: LLM → task list JSON
    P-->>R: Task: "Research X"
    R->>R: web_search("X market 2024")
    R->>R: read_url(top results)
    R-->>W: Task: "Write report" + research findings
    W->>W: LLM → structured markdown
    W-->>U: OUTPUT: { "Write report": { "content": "..." } }
```

---

## Building a custom syscall (webhook)

No code needed. Register any HTTP endpoint as a tool agents can call:

**1. Register in the UI** (`/tools` → REGISTER):

```
Name:         search_products
Description:  Search the internal product catalog
Webhook URL:  https://your-api.com/ai-tools
Input Schema: { "type": "object", "properties": { "query": { "type": "string" } } }
```

**2. Your server receives:**

```json
POST https://your-api.com/ai-tools
{
  "tool": "search_products",
  "input": { "query": "blue sneakers size 42" }
}
```

**3. Respond with:**

```json
{ "results": [ { "id": "SKU-123", "name": "..." } ] }
```

**4. Assign to an agent** in the Agent Registry → edit panel → Allowed Syscalls.

That's it. Agents call your tool exactly like any built-in.

---

## Dashboard pages

| Page | Path | Description |
|------|------|-------------|
| Dashboard | `/` | Live queue, process table, event stream, resource gauges |
| Processes | `/jobs` | Full job list with status filter. Click → detail view |
| Process detail | `/jobs/{id}` | OVERVIEW · TIMELINE · CALL_GRAPH · EVENT_LOG · SYSCALLS · OUTPUT |
| Agent Registry | `/agents` | Manage agents: system prompts, provider/model, allowed tools |
| Syscall Registry | `/tools` | Built-in and webhook tools |
| Memory Layer | `/memory` | Browse TASK/JOB/GLOBAL memory entries with JSON viewer |
| Event Stream | `/events` | Global audit log with event type filter |
| Metrics | `/metrics` | Aggregated tokens, cost, success rate, job durations |

---

## Useful endpoints

```bash
# Spawn a job
curl -X POST http://localhost:8000/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"title":"My Job","description":"Do X","priority":"NORMAL","input_payload":{}}'

# List available models for a provider (live API query)
curl http://localhost:8000/api/v1/providers/openai/models
curl http://localhost:8000/api/v1/providers/ollama/models

# Register a webhook syscall
curl -X POST http://localhost:8000/api/v1/tools \
  -H "Content-Type: application/json" \
  -d '{"name":"my_tool","description":"...","webhook_url":"https://...","input_schema":{},"output_schema":{}}'
```

Full API reference: **http://localhost:8000/docs**

---

## Troubleshooting

| Symptom | Cause | Fix |
|---------|-------|-----|
| Job stays PLANNING indefinitely | Ollama not running or model not pulled | Run `ollama serve` on the host, then `ollama pull llama3.2`. Confirm with `docker compose logs worker-agents --tail=20` — look for `APIConnectionError` |
| Job stays PLANNING indefinitely | Worker not consuming queue | `docker compose logs worker-scheduler --tail=30` |
| `APIConnectionError` in worker logs | Ollama unreachable from container | Start `ollama serve` on the host (not inside Docker). The workers connect via `host.docker.internal:11434` |
| Tokens show as 0 | Beat worker hasn't run yet (60s cycle) | Wait 60s and refresh |
| `Vector dimension error` | Embedding model mismatch | `docker compose run --rm migrate` (applies migration 0005) |
| `MaxIterationsExceeded` | Agent looped without producing JSON | Reduce `max_iterations` or improve system prompt |

---

## Repo structure

```
OSymandias/
├── backend/          Python — FastAPI + Celery + agents
│   ├── aios/         Application code
│   └── alembic/      DB migrations (0001 → 0005)
├── frontend/         TypeScript — Next.js 14 dashboard
│   └── src/
├── docker-compose.yml
├── .env.example
└── README.md         ← you are here
```

See [`backend/README.md`](backend/README.md) and [`frontend/README.md`](frontend/README.md) for deeper technical documentation.

---

<div align="center">
<sub>Built with FastAPI · Next.js · Celery · PostgreSQL · Redis · RabbitMQ · Qdrant · LiteLLM</sub>
</div>
