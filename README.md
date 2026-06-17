<div align="center">

<img src="banner.svg" width="100%"/>

*"Look on my works, ye Mighty, and dispatch."*

**Multi-agent runtime for Python developers. One command to start everything.**

[![PyPI](https://img.shields.io/pypi/v/osymandias?style=flat-square&color=C8A040)](https://pypi.org/project/osymandias)
[![Python](https://img.shields.io/badge/python-3.11+-blue?style=flat-square)](https://python.org)
[![License](https://img.shields.io/badge/license-MIT-green?style=flat-square)](LICENSE)
[![Tests](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml/badge.svg)](https://github.com/andreisilva1/OSymandias/actions/workflows/tests.yml)
![Status](https://img.shields.io/badge/status-in%20development-orange?style=flat-square)

</div>

---

## What is this?

**OSymandias** is a Python library and CLI that turns your project into a full multi-agent runtime.

```bash
pip install osymandias
osy init
osy serve
```

That's it. PostgreSQL, Redis, RabbitMQ, Qdrant — managed internally via Docker. Dashboard at `localhost:47759`. Four Celery workers ready.

Your Python functions become agent tools with a single decorator:

```python
from osymandias import osy

@osy.tool
def analyze_sentiment(text: str, language: str = "en") -> dict:
    """Analyze the sentiment of a text. Returns score and label."""
    return your_implementation(text, language)
```

Schema inferred from type hints. Tools registered automatically on `osy serve`. No YAML. No config files.

---

## How it works

```
Job        →  A user-submitted goal ("research and write a report on X")
  └── Task ×N  →  Subtask assigned to a specific agent type
        └── AgentInstance  →  A running agent loop (LLM + tools + memory)
              └── ToolCall  →  web_search / @osy.tool / webhook / ...
```

Jobs are decomposed into tasks by a PlannerAgent. Tasks execute in parallel across specialized agents. An EvaluatorAgent scores outputs and retries if confidence is below threshold. Results are structured, per-task, ready to download.

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

---

## Adding your own tools

Define `@osy.tool` functions anywhere in your project — `osy serve` scans all `.py` files automatically. `osy_tools.py` (created by `osy init`) is just a starting point:

```python
from osymandias import osy

@osy.tool
def fetch_competitor_data(company: str, metrics: list[str]) -> dict:
    """Fetch competitor metrics from internal database."""
    # your implementation
    return {"company": company, "data": [...]}

@osy.tool
def send_slack_message(channel: str, text: str) -> dict:
    """Send a message to a Slack channel."""
    # your implementation
    return {"ok": True}
```

Restart `osy serve` — any `.py` file in your project that imports `osymandias` is scanned and tools are registered automatically. Assign them to agents from the dashboard (`/tools`).

---

## Three ways to give agents tools

| | What | How |
|---|---|---|
| **Built-in** | `web_search`, `read_url`, `http_request`, `write_to_job_memory`, `search_memory`, `python_eval`, `run_shell`, `read_file`, `write_file`, `send_message`, `spawn_agent` … (20 total) | Zero config — always available |
| **`@osy.tool`** | Your Python functions | Decorate + `osy serve` |
| **Webhook** | Any HTTP endpoint | Register URL in the dashboard |

---

## Dashboard pages

| Page | Path | Description |
|------|------|-------------|
| Jobs | `/jobs` | Job list with search, filter, pagination |
| Job detail | `/jobs/{id}` | Output, events, tasks, timeline |
| Agents | `/agents` | Builder: system prompt, model, tools, output schema |
| Tools | `/tools` | Built-in and user tools |
| Memory | `/memory` | Search, filter by scope, delete entries |
| Events | `/events` | Live event stream with pause/resume |
| Metrics | `/metrics` | 7-day chart, tokens, cost, success rate |

---

## Spawning a job via API

```bash
curl -X POST http://localhost:47760/api/v1/jobs \
  -H "Content-Type: application/json" \
  -d '{"title":"My Job","description":"Research the EV market in Europe in 2024.","priority":"NORMAL","input_payload":{}}'
```

Full API reference: **http://localhost:47760/api/v1/docs**

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

## Repo structure

```
OSymandias/
├── sdk/                  Python package — osymandias + osy CLI
│   └── osymandias/
│       ├── cli/          osy init / serve / stop
│       ├── runtime/      FastAPI + Celery + agents (adapted from backend/)
│       ├── decorator.py  @osy.tool
│       ├── discovery.py  directory scanner
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
