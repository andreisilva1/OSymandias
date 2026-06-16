from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from aios.observability.logging import setup_logging
from aios.observability.tracing import setup_tracing


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    setup_tracing(app)
    # Seed builtin agents and tools on startup
    from aios.db.init_db import seed
    await seed()
    yield


app = FastAPI(
    title="OSymandias",
    description="Multi-agent runtime with OS-inspired primitives",
    version="0.1.0",
    lifespan=lifespan,
)

from aios.config import settings as _settings  # noqa: E402

app.add_middleware(
    CORSMiddleware,
    allow_origins=_settings.cors_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "Accept", "Origin"],
)

# Routers
from aios.api.routers import jobs, agents, tools, metrics, events, memory, providers  # noqa: E402

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
