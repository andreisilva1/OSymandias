from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from osymandias.runtime.observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from pathlib import Path
    from osymandias.discovery import discover_agents
    from osymandias.runtime.db.init_db import seed
    discover_agents(Path.cwd())
    await seed()
    yield


app = FastAPI(
    title="OSymandias",
    description="Multi-agent runtime with OS-inspired primitives",
    version="0.1.0",
    lifespan=lifespan,
)

from osymandias.runtime.config import settings as _settings  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _settings.osy_cors_origins.split(",") if o.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin"],
)

# Routers
from osymandias.runtime.api.routers import jobs, agents, tools, metrics, events, memory, providers  # noqa: E402

app.include_router(jobs.router)
app.include_router(agents.router)
app.include_router(tools.router)
app.include_router(metrics.router)
app.include_router(events.router)
app.include_router(memory.router)
app.include_router(providers.router)


@app.get("/health")
async def health():
    return {"status": "ok"}
