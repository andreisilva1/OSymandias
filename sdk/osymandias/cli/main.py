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
NGINX_CONF_FILENAME = "OSY.nginx.conf"
ENV_FILENAME = ".env"
TOOLS_FILENAME = "osy_tools.py"
TOOL_SERVER_PORT = 47761   # internal tool server
RUNTIME_PORT     = 47760   # FastAPI
FRONTEND_PORT    = 47759   # nginx


# ─── osy init ────────────────────────────────────────────────────────────────

@app.command()
def init():
    """Initialise a new OSymandias project in the current directory."""
    cwd = Path.cwd()

    console.print("\n[bold cyan]osy init[/bold cyan]")

    # LLM provider
    provider = Prompt.ask(
        "LLM provider",
        choices=["ollama", "openai", "anthropic", "deepseek", "groq", "gemini"],
        default="ollama",
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

    # Fetch OSY.compose.yml
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
            _write_fallback_compose(compose_dest)
            console.print(f"[green]✓[/green] {COMPOSE_FILENAME} created (fallback)")

    # Fetch OSY.nginx.conf
    nginx_dest = cwd / NGINX_CONF_FILENAME
    if nginx_dest.exists():
        console.print(f"[yellow]↳ {NGINX_CONF_FILENAME} already exists, skipping[/yellow]")
    else:
        console.print(f"[dim]↓ Fetching {NGINX_CONF_FILENAME} from GitHub...[/dim]")
        try:
            from osymandias.assets import ensure_nginx_conf
            ensure_nginx_conf(nginx_dest)
            console.print(f"[green]✓[/green] {NGINX_CONF_FILENAME} created")
        except Exception as exc:
            console.print(f"[yellow]⚠ Could not fetch nginx config: {exc}[/yellow]")
            _write_fallback_nginx_conf(nginx_dest)
            console.print(f"[green]✓[/green] {NGINX_CONF_FILENAME} created (fallback)")

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

    # 4. Resolve frontend + nginx for Docker
    import os as _os
    compose_env = {**_os.environ}
    frontend_dir = _resolve_frontend_dir(cwd)
    with_frontend = False
    if frontend_dir:
        nginx_conf = _resolve_nginx_conf(cwd)
        if nginx_conf:
            compose_env["OSY_FRONTEND_DIR"] = str(frontend_dir)
            compose_env["OSY_NGINX_CONF"]   = str(nginx_conf)
            with_frontend = True
            console.print(f"[dim]✓ Frontend ready → http://localhost:{FRONTEND_PORT}[/dim]")
        else:
            console.print(f"[yellow]⚠ {NGINX_CONF_FILENAME} not found — dashboard unavailable[/yellow]")
    else:
        console.print(f"[yellow]⚠ No frontend build — run [cyan]npm run dev[/cyan] in frontend/ for the dashboard[/yellow]")

    # 5. Start infra (+ nginx if frontend available)
    console.print("[dim]↓ Starting infrastructure...[/dim]")
    compose_cmd = ["docker", "compose", "-f", str(compose_path)]
    if with_frontend:
        compose_cmd += ["--profile", "frontend"]
    compose_cmd += ["up", "-d"]
    subprocess.run(compose_cmd, env=compose_env, check=True)
    _wait_healthy(compose_path)
    infra_note = "postgres · redis · rabbitmq · qdrant" + (" · nginx" if with_frontend else "")
    console.print(f"[green]✓[/green] Infrastructure  [dim]{infra_note}[/dim]")

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
    manager.start("api", [
        sys.executable, "-m", "uvicorn",
        "osymandias.runtime.main:app",
        "--host", "0.0.0.0",
        "--port", str(RUNTIME_PORT),
        "--log-level", "warning",
    ])

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
    if with_frontend:
        console.print(f"[green]✓[/green] Dashboard      [cyan]http://localhost:{FRONTEND_PORT}[/cyan]")
    else:
        console.print(f"[dim]  Dashboard: cd frontend && npm run dev[/dim]")
    console.print("\n[dim]Press Ctrl+C to stop.[/dim]\n")

    manager.wait_all()


# ─── osy stop ────────────────────────────────────────────────────────────────

@app.command()
def stop():
    """Pause the Docker infrastructure (containers stay, data preserved)."""
    compose_path = _find_compose()
    console.print("[dim]Stopping infrastructure...[/dim]")
    subprocess.run(["docker", "compose", "-f", str(compose_path), "stop"], check=False)
    console.print("[green]✓[/green] Infrastructure stopped.  Data preserved.")


# ─── osy down ────────────────────────────────────────────────────────────────

@app.command()
def down():
    """Remove containers but keep volumes (data preserved)."""
    compose_path = _find_compose()
    console.print("[dim]Bringing down containers...[/dim]")
    subprocess.run(["docker", "compose", "-f", str(compose_path), "down"], check=False)
    console.print("[green]✓[/green] Containers removed.  Volumes preserved.")


# ─── osy delete ──────────────────────────────────────────────────────────────

@app.command()
def delete():
    """Remove containers AND volumes — all data will be lost. Asks for confirmation."""
    compose_path = _find_compose()

    console.print("[bold red]WARNING:[/bold red] This will permanently delete all OSymandias data.")
    console.print("[dim]  Volumes: osy_postgres · osy_redis · osy_rabbitmq · osy_qdrant[/dim]\n")

    confirm = typer.prompt("Type  delete  to confirm")
    if confirm.strip() != "delete":
        console.print("[yellow]Aborted.[/yellow]")
        raise typer.Exit(0)

    console.print("[dim]Removing containers and volumes...[/dim]")
    subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "down", "--volumes", "--remove-orphans"],
        check=False,
    )
    console.print("[green]✓[/green] Containers and volumes removed.")


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _require_docker() -> None:
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=10)
    except (subprocess.CalledProcessError, FileNotFoundError, subprocess.TimeoutExpired):
        console.print("[red bold]✗ Docker is not running.[/red bold]")
        console.print("  Install Docker from https://docker.com and start the daemon.")
        raise typer.Exit(1)


def _find_compose() -> Path:
    """Locate OSY.compose.yml: local dir → ~/.osy cache. Exits if not found."""
    local = Path.cwd() / COMPOSE_FILENAME
    if local.exists():
        return local
    try:
        from osymandias.assets import compose_cache_path
        cached = compose_cache_path()
        if cached.exists():
            return cached
    except Exception:
        pass
    console.print(f"[red]✗ {COMPOSE_FILENAME} not found.[/red]")
    console.print("  Run [cyan]osy init[/cyan] first.")
    raise typer.Exit(1)


def _resolve_compose(cwd: Path) -> Path:
    return _find_compose()


def _resolve_frontend_dir(cwd: Path) -> "Path | None":
    try:
        from osymandias.assets import ensure_frontend
        return ensure_frontend()
    except Exception:
        pass
    local_out = cwd / "frontend" / "out"
    if local_out.exists() and any(local_out.iterdir()):
        return local_out
    return None


def _resolve_nginx_conf(cwd: Path) -> "Path | None":
    local = cwd / NGINX_CONF_FILENAME
    try:
        from osymandias.assets import ensure_nginx_conf
        return ensure_nginx_conf(local)
    except Exception:
        pass
    return local if local.exists() else None


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
    from alembic.config import Config
    from alembic import command as alembic_command

    runtime_dir = Path(__file__).parent.parent / "runtime"
    db_url = os.environ.get("POSTGRES_URL", "postgresql+asyncpg://osy:osy@localhost:47762/osymandias")

    cfg = Config()
    cfg.set_main_option("script_location", str(runtime_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)

    try:
        alembic_command.upgrade(cfg, "head")
    except Exception as exc:
        console.print(f"[red]✗ Migrations failed: {exc}[/red]")
        raise typer.Exit(1)


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
POSTGRES_URL=postgresql+asyncpg://osy:osy@localhost:47762/osymandias
REDIS_URL=redis://localhost:47763/0
RABBITMQ_URL=amqp://guest:guest@localhost:47764/
QDRANT_URL=http://localhost:47766

# CORS (frontend on {FRONTEND_PORT}, direct API access on {RUNTIME_PORT})
CORS_ORIGINS=http://localhost:{FRONTEND_PORT},http://localhost:{RUNTIME_PORT}

# Tool server (internal)
TOOL_SERVER_URL=http://localhost:{TOOL_SERVER_PORT}
""", encoding="utf-8")


def _write_fallback_nginx_conf(dest: Path) -> None:
    dest.write_text(f"""\
server {{
    listen 80;
    root /usr/share/nginx/html;
    charset utf-8;

    location ~ ^/api/v1/jobs/.+/events {{
        proxy_pass http://host.docker.internal:{RUNTIME_PORT};
        proxy_http_version 1.1;
        proxy_set_header Connection "";
        proxy_buffering off;
        proxy_cache off;
        proxy_read_timeout 3600s;
    }}

    location /api/ {{
        proxy_pass http://host.docker.internal:{RUNTIME_PORT}/api/;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }}

    location /health {{
        proxy_pass http://host.docker.internal:{RUNTIME_PORT}/health;
    }}

    location / {{
        try_files $uri $uri.html $uri/ /index.html;
    }}
}}
""", encoding="utf-8")


def _write_fallback_compose(dest: Path) -> None:
    dest.write_text(f"""\
services:
  nginx:
    image: nginx:alpine
    profiles: ["frontend"]
    ports:
      - "{FRONTEND_PORT}:80"
    volumes:
      - ${{OSY_FRONTEND_DIR}}:/usr/share/nginx/html:ro
      - ${{OSY_NGINX_CONF}}:/etc/nginx/conf.d/default.conf:ro
    extra_hosts:
      - "host.docker.internal:host-gateway"
    restart: unless-stopped

  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_USER: osy
      POSTGRES_PASSWORD: osy
      POSTGRES_DB: osymandias
    ports: ["47762:5432"]
    volumes: ["osy_postgres:/var/lib/postgresql/data"]
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U osy"]
      interval: 5s
      timeout: 5s
      retries: 10

  redis:
    image: redis:7-alpine
    ports: ["47763:6379"]
    volumes: ["osy_redis:/data"]
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      retries: 10

  rabbitmq:
    image: rabbitmq:3-management-alpine
    ports: ["47764:5672", "47765:15672"]
    volumes: ["osy_rabbitmq:/var/lib/rabbitmq"]
    healthcheck:
      test: ["CMD", "rabbitmq-diagnostics", "ping"]
      interval: 10s
      retries: 10

  qdrant:
    image: qdrant/qdrant:latest
    ports: ["47766:6333"]
    volumes: ["osy_qdrant:/qdrant/storage"]
    healthcheck:
      test: ["CMD-SHELL", "bash -c 'echo > /dev/tcp/localhost/6333' 2>/dev/null"]
      interval: 5s
      retries: 10

volumes:
  osy_postgres:
  osy_redis:
  osy_rabbitmq:
  osy_qdrant:
""", encoding="utf-8")


def _write_sample_tools(dest: Path) -> None:
    dest.write_text("""\
# osy_tools.py — sample file generated by `osy init`
#
# This file is just a starting point. You can define @osy.tool functions
# anywhere in your project — osy serve scans all .py files automatically.

from osymandias import osy


@osy.tool
def hello(name: str) -> dict:
    \"\"\"Return a greeting for the given name.\"\"\"
    return {"message": f"Hello, {name}!"}
""", encoding="utf-8")
