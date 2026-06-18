from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from osymandias.runtime.observability.logging import setup_logging

# Paths that never require authentication
_AUTH_EXEMPT = {"/health", "/docs", "/redoc", "/openapi.json"}


class ApiKeyMiddleware(BaseHTTPMiddleware):
    """Static API key gate. Inactive when osy_api_key is empty."""

    def __init__(self, app, api_key: str) -> None:
        super().__init__(app)
        self._key = api_key

    async def dispatch(self, request: Request, call_next):
        if request.url.path in _AUTH_EXEMPT or request.method == "OPTIONS":
            return await call_next(request)

        auth = request.headers.get("Authorization", "")
        x_key = request.headers.get("X-Api-Key", "")

        provided = auth[7:].strip() if auth.startswith("Bearer ") else x_key.strip()

        if provided != self._key:
            return JSONResponse(
                {"detail": "Invalid or missing API key. Pass Authorization: Bearer <key> or X-Api-Key: <key>."},
                status_code=401,
                headers={"WWW-Authenticate": "Bearer"},
            )

        return await call_next(request)


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
    allow_headers=["Content-Type", "Authorization", "Accept", "X-Api-Key", "Origin"],
)

if _settings.osy_api_key:
    app.add_middleware(ApiKeyMiddleware, api_key=_settings.osy_api_key)

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
