# Backend

FastAPI + Celery multi-agent runtime.

## Stack

| Layer | Technology |
|-------|-----------|
| API | FastAPI, Pydantic v2, SQLAlchemy (async) |
| Workers | Celery 5 — 4 queues: `scheduler`, `agents`, `evaluator`, `tools` |
| Database | PostgreSQL 16 + pgvector |
| Vector store | Qdrant |
| Message broker | RabbitMQ + Redis (pub/sub for SSE) |
| LLM routing | LiteLLM (Ollama, OpenAI, Anthropic, DeepSeek, Groq, Gemini) |

## Structure

```
backend/
├── aios/
│   ├── main.py              # FastAPI app + router registration
│   ├── config.py            # Settings via Pydantic (reads .env)
│   ├── models/              # SQLAlchemy ORM models
│   ├── api/routers/         # REST endpoints + SSE
│   ├── agents/              # Agent loop (base_agent.py)
│   ├── tools/               # Syscall registry + webhook executor
│   ├── memory/              # Embedding + Qdrant vector store
│   ├── llm/                 # LiteLLM client + cost tracker
│   ├── workers/             # Celery tasks (scheduler, agent, evaluator, beat)
│   ├── core/                # Event emitter (Redis pub/sub + DB)
│   └── db/                  # Sessions, init/seed
└── alembic/versions/        # DB migrations (0001 → 0005)
```

## LLM providers

| Provider | Model string | Env var |
|----------|-------------|---------|
| `ollama` | `ollama/{model}` | `OLLAMA_BASE_URL` |
| `openai` | `{model}` | `OPENAI_API_KEY` |
| `anthropic` | `{model}` | `ANTHROPIC_API_KEY` |
| `deepseek` | `deepseek/{model}` | `DEEPSEEK_API_KEY` |
| `groq` | `groq/{model}` | `GROQ_API_KEY` |
| `gemini` | `gemini/{model}` | `GEMINI_API_KEY` |

## Migrations

```bash
# Apply all pending
docker compose run --rm migrate

# Create new migration after model changes
docker compose run --rm backend alembic revision --autogenerate -m "description"
```

## Extending

**Add an agent type:**
1. Add `AgentDefinition(...)` in `db/init_db.py → seed()`
2. Map the name in `workers/agent_tasks.py → _AGENT_TYPE_MAP`
3. Rebuild: `docker compose build worker-agents && docker compose up -d --no-deps worker-agents`

**Add a built-in syscall:**
1. Implement in `tools/registry.py`
2. Seed in `db/init_db.py`
3. Rebuild `worker-agents`

**Add a webhook syscall:** use the UI at `/tools` — no code needed.
