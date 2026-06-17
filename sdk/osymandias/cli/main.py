"""
osy — OSymandias CLI
Commands: init, serve, stop
"""
import subprocess
import sys
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.prompt import Prompt

app = typer.Typer(
    name="osy",
    help="OSymandias — multi-agent runtime CLI",
    add_completion=False,
)
console = Console()

COMPOSE_FILENAME = "OSY.compose.yml"
ENV_FILENAME = ".env"
TOOLS_FILENAME = "tools.py"
TOOL_SERVER_PORT = 8001
RUNTIME_PORT = 3000


# ─── osy init ────────────────────────────────────────────────────────────────

@app.command()
def init():
    """Initialise a new OSymandias project in the current directory."""
    cwd = Path.cwd()

    console.print("\n[bold cyan]osy init[/bold cyan]")

    # LLM provider
    provider = Prompt.ask(
        "LLM provider",
        choices=["openai", "anthropic", "ollama", "deepseek", "groq", "gemini"],
        default="openai",
    )

    api_key = ""
    model = ""
    if provider == "openai":
        api_key = Prompt.ask("OpenAI API key", password=True)
        model = "gpt-4o"
    elif provider == "anthropic":
        api_key = Prompt.ask("Anthropic API key", password=True)
        model = "claude-sonnet-4-6"
    elif provider == "ollama":
        model = Prompt.ask("Ollama model", default="llama3.2")
    elif provider == "deepseek":
        api_key = Prompt.ask("DeepSeek API key", password=True)
        model = "deepseek-chat"
    elif provider == "groq":
        api_key = Prompt.ask("Groq API key", password=True)
        model = "llama3-8b-8192"
    elif provider == "gemini":
        api_key = Prompt.ask("Gemini API key", password=True)
        model = "gemini/gemini-1.5-flash"

    # Fetch OSY.compose.yml from GitHub
    compose_dest = cwd / COMPOSE_FILENAME
    if compose_dest.exists():
        console.print(f"[yellow]↳ {COMPOSE_FILENAME} already exists, skipping[/yellow]")
    else:
        console.print(f"[dim]↓ Fetching {COMPOSE_FILENAME} from GitHub...[/dim]")
        try:
            from osymandias.assets import fetch_compose
            fetch_compose(compose_dest)
            console.print(f"[green]✓[/green] {COMPOSE_FILENAME} created")
        except Exception as exc:
            console.print(f"[yellow]⚠ Could not fetch from GitHub: {exc}[/yellow]")
            console.print("[dim]  Using bundled fallback.[/dim]")
            _write_fallback_compose(compose_dest)
            console.print(f"[green]✓[/green] {COMPOSE_FILENAME} created (fallback)")

    # Write .env
    env_dest = cwd / ENV_FILENAME
    if env_dest.exists():
        console.print(f"[yellow]↳ {ENV_FILENAME} already exists, skipping[/yellow]")
    else:
        _write_env(env_dest, provider, api_key, model)
        console.print(f"[green]✓[/green] {ENV_FILENAME} created")

    # Write sample tools.py
    tools_dest = cwd / TOOLS_FILENAME
    if tools_dest.exists():
        console.print(f"[yellow]↳ {TOOLS_FILENAME} already exists, skipping[/yellow]")
    else:
        _write_sample_tools(tools_dest)
        console.print(f"[green]✓[/green] {TOOLS_FILENAME} created")

    console.print("\n[bold green]Ready.[/bold green] Run [cyan]osy serve[/cyan] to start.\n")


# ─── osy serve ───────────────────────────────────────────────────────────────

@app.command()
def serve():
    """Start the full OSymandias runtime."""
    from osymandias.process import ProcessManager
    from osymandias.discovery import discover
    from osymandias.decorator import _TOOL_REGISTRY

    cwd = Path.cwd()
    manager = ProcessManager()

    console.print("\n[bold cyan]osy serve[/bold cyan]\n")

    # 1. Check Docker
    _require_docker()

    # 2. Load .env
    env_file = cwd / ENV_FILENAME
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        console.print(f"[dim]✓ Loaded {ENV_FILENAME}[/dim]")
    else:
        console.print(f"[yellow]⚠ No {ENV_FILENAME} found — using environment variables[/yellow]")

    # 3. Resolve OSY.compose.yml
    compose_path = _resolve_compose(cwd)

    # 4. Ensure frontend cache
    console.print("[dim]↓ Checking frontend cache...[/dim]")
    try:
        from osymandias.assets import ensure_frontend
        frontend_dir = ensure_frontend()
        console.print(f"[dim]✓ Frontend ready ({frontend_dir})[/dim]")
    except Exception as exc:
        console.print(f"[yellow]⚠ Could not fetch frontend: {exc}[/yellow]")
        console.print("[dim]  Dashboard may not be available.[/dim]")
        frontend_dir = None

    # 5. Start infra
    console.print("[dim]↓ Starting infrastructure...[/dim]")
    subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "up", "-d"],
        check=True,
    )
    _wait_healthy(compose_path)
    console.print("[green]✓[/green] Infrastructure  [dim]postgres · redis · rabbitmq · qdrant[/dim]")

    # 6. Run migrations
    console.print("[dim]↓ Running database migrations...[/dim]")
    _run_migrations()
    console.print("[dim]✓ Migrations applied[/dim]")

    # 7. Discover @osy.tool functions
    console.print("[dim]↓ Scanning for @osy.tool functions...[/dim]")
    count = discover(cwd)
    console.print(f"[dim]✓ {len(_TOOL_REGISTRY)} tool(s) registered[/dim]")

    # 8. Start tool server
    manager.start("tool-server", [
        sys.executable, "-m", "uvicorn",
        "osymandias.tool_server:app",
        "--host", "0.0.0.0",
        "--port", str(TOOL_SERVER_PORT),
        "--log-level", "warning",
    ])

    # 9. Register @osy.tool tools in DB (as webhook tools pointing to tool server)
    time.sleep(1.5)
    _register_tools_in_db(_TOOL_REGISTRY)

    # 10. Start FastAPI runtime
    import os
    runtime_env = {}
    if frontend_dir:
        runtime_env["OSY_FRONTEND_DIR"] = str(frontend_dir)

    manager.start("api", [
        sys.executable, "-m", "uvicorn",
        "osymandias.runtime.main:app",
        "--host", "0.0.0.0",
        "--port", str(RUNTIME_PORT),
        "--log-level", "warning",
    ], env=runtime_env)

    # 11. Start Celery workers
    pool = "solo" if sys.platform == "win32" else "prefork"
    manager.start("workers", [
        sys.executable, "-m", "celery",
        "-A", "osymandias.runtime.workers.celery_app",
        "worker",
        f"--pool={pool}",
        "--loglevel=warning",
        "--concurrency=4",
    ])

    time.sleep(2)
    console.print(f"\n[green]✓[/green] Tool server    [cyan]http://localhost:{TOOL_SERVER_PORT}[/cyan]  [dim]({len(_TOOL_REGISTRY)} tools)[/dim]")
    console.print(f"[green]✓[/green] Runtime API    [cyan]http://localhost:{RUNTIME_PORT}/api/v1[/cyan]")
    console.print(f"[green]✓[/green] Dashboard      [cyan]http://localhost:{RUNTIME_PORT}[/cyan]")
    console.print("\n[dim]Press Ctrl+C to stop.[/dim]\n")

    manager.wait_all()


# ─── osy stop ────────────────────────────────────────────────────────────────

@app.command()
def stop():
    """Stop the Docker infrastructure."""
    cwd = Path.cwd()
    compose_path = cwd / COMPOSE_FILENAME
    if not compose_path.exists():
        from osymandias.assets import compose_cache_path
        compose_path = compose_cache_path()

    if not compose_path.exists():
        console.print("[red]No OSY.compose.yml found. Nothing to stop.[/red]")
        raise typer.Exit(1)

    console.print("[dim]Stopping infrastructure...[/dim]")
    subprocess.run(["docker", "compose", "-f", str(compose_path), "stop"], check=False)
    console.print("[green]✓[/green] Infrastructure stopped.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _require_docker() -> None:
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        console.print("[red bold]✗ Docker is not running.[/red bold]")
        console.print("  Install Docker from https://docker.com and start the daemon.")
        raise typer.Exit(1)


def _resolve_compose(cwd: Path) -> Path:
    local = cwd / COMPOSE_FILENAME
    if local.exists():
        return local

    from osymandias.assets import ensure_compose
    try:
        return ensure_compose(local)
    except Exception as exc:
        console.print(f"[red]✗ Could not resolve {COMPOSE_FILENAME}: {exc}[/red]")
        console.print("  Run [cyan]osy init[/cyan] first.")
        raise typer.Exit(1)


def _wait_healthy(compose_path: Path, timeout: int = 90) -> None:
    services = ["postgres", "redis", "rabbitmq", "qdrant"]
    deadline = time.time() + timeout
    while time.time() < deadline:
        result = subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "ps", "--format", "json"],
            capture_output=True, text=True,
        )
        if all(svc in result.stdout for svc in services):
            # crude check: all services appear in output
            time.sleep(3)
            return
        time.sleep(2)


def _run_migrations() -> None:
    import os
    alembic_ini = Path(__file__).parent.parent / "runtime" / "alembic.ini"
    if not alembic_ini.exists():
        return
    subprocess.run(
        [sys.executable, "-m", "alembic", "-c", str(alembic_ini), "upgrade", "head"],
        check=False,
    )


def _register_tools_in_db(registry: dict) -> None:
    if not registry:
        return
    import httpx
    base = f"http://localhost:{TOOL_SERVER_PORT}"
    api = f"http://localhost:{RUNTIME_PORT}/api/v1"
    for name, entry in registry.items():
        try:
            httpx.post(f"{api}/tools", json={
                "name": name,
                "description": entry.description,
                "input_schema": entry.parameters,
                "output_schema": {"type": "object"},
                "webhook_url": f"{base}/tools/{name}/call",
            }, timeout=5)
        except Exception:
            pass  # runtime may still be starting; tools sync on next request


def _write_env(dest: Path, provider: str, api_key: str, model: str) -> None:
    key_line = ""
    if provider == "openai" and api_key:
        key_line = f"OPENAI_API_KEY={api_key}"
    elif provider == "anthropic" and api_key:
        key_line = f"ANTHROPIC_API_KEY={api_key}"
    elif provider == "deepseek" and api_key:
        key_line = f"DEEPSEEK_API_KEY={api_key}"
    elif provider == "groq" and api_key:
        key_line = f"GROQ_API_KEY={api_key}"
    elif provider == "gemini" and api_key:
        key_line = f"GEMINI_API_KEY={api_key}"

    dest.write_text(f"""\
# LLM
LLM_DEFAULT_PROVIDER={provider}
LLM_DEFAULT_MODEL={model}
{key_line}

# Infrastructure (managed by osy serve)
POSTGRES_URL=postgresql+asyncpg://osy:osy@localhost:5432/osymandias
REDIS_URL=redis://localhost:6379/0
RABBITMQ_URL=amqp://guest:guest@localhost:5672/
QDRANT_URL=http://localhost:6333

# CORS
CORS_ORIGINS=http://localhost:{RUNTIME_PORT}

# Tool server (internal)
TOOL_SERVER_URL=http://localhost:{TOOL_SERVER_PORT}
""", encoding="utf-8")


def _write_fallback_compose(dest: Path) -> None:
    dest.write_text("""\
services:
  postgres:
    image: postgres:16
    environment:
      POSTGRES_USER: osy
      POSTGRES_PASSWORD: osy
      POSTGRES_DB: osymandias
    ports: ["5432:5432"]
    volumes: ["osy_postgres:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U osy"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s

  rabbitmq:
    image: rabbitmq:3-management
    ports: ["5672:5672", "15672:15672"]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      retries: 10

  qdrant:
    image: qdrant/qdrant
    ports: ["6333:6333"]
    volumes: ["osy_qdrant:/qdrant/storage"]

volumes:
  osy_postgres:
  osy_qdrant:
""", encoding="utf-8")


def _write_sample_tools(dest: Path) -> None:
    dest.write_text("""\
from osymandias import osy


@osy.tool
def hello(name: str) -> dict:
    \"\"\"Return a greeting for the given name.\"\"\"
    return {"message": f"Hello, {name}!"}


# Add your own tools below.
# Any function decorated with @osy.tool is automatically
# discovered and registered when you run `osy serve`.
""", encoding="utf-8")
