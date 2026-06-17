# backend/

> **Legacy standalone backend** — kept for reference and direct development.
>
> The production path is now `sdk/osymandias/runtime/` (code adapted from here).
> To run OSymandias as an end user, use `pip install osymandias && osy init && osy serve`.

---

## Running standalone (development only)

```bash
cd backend
cp ../.env.example .env  # edit as needed
docker compose -f ../OSY.compose.yml up -d
pip install -e ".[dev]"
uvicorn aios.main:app --reload --port 47760
```

API docs: http://localhost:47760/docs

## Structure

```
backend/aios/
├── agents/       Agent base class, registry, context builder
├── api/          FastAPI routers + schemas
├── core/         Event emitter
├── db/           SQLAlchemy session, seed data
├── llm/          LiteLLM client, cost tracker
├── memory/       Qdrant + embedding manager
├── models/       SQLAlchemy models
├── observability/ Loguru logging, OpenTelemetry tracing
├── tools/        Tool executor, registry, built-ins
└── workers/      Celery tasks (agent, scheduler, evaluator, beat)
```
