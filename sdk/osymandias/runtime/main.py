import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from osymandias.runtime.observability.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    from osymandias.runtime.db.init_db import seed
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
    allow_origins=[o.strip() for o in _settings.cors_origins.split(",") if o.strip()],
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


# ─── Static frontend (SPA catch-all) ─────────────────────────────────────────

def _resolve_frontend() -> Path | None:
    env_dir = os.environ.get("OSY_FRONTEND_DIR")
    if env_dir:
        p = Path(env_dir)
        if p.exists():
            return p
    try:
        import osymandias
        candidate = Path.home() / ".osy" / "cache" / osymandias.__version__ / "frontend"
        if candidate.exists():
            return candidate
    except Exception:
        pass
    return None


_FRONTEND_DIR = _resolve_frontend()

if _FRONTEND_DIR:
    @app.get("/{full_path:path}", include_in_schema=False)
    async def serve_spa(full_path: str):
        file = _FRONTEND_DIR / full_path
        if file.is_file():
            return FileResponse(file)
        return FileResponse(_FRONTEND_DIR / "index.html")
