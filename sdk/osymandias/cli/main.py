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

def _version_callback(value: bool) -> None:
    if value:
        import osymandias
        console.print(f"osy {osymandias.__version__}")
        raise typer.Exit()


app = typer.Typer(
    name="osy",
    help="OSymandias — multi-agent runtime CLI",
    add_completion=False,
)
console = Console()


@app.callback()
def _main(
    version: bool = typer.Option(
        False, "--version", "-V",
        callback=_version_callback,
        is_eager=True,
        help="Show version and exit.",
    ),
) -> None:
    pass

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

    # Write osymandias.toml config stub
    osy_toml_dest = cwd / "osymandias.toml"
    if osy_toml_dest.exists():
        console.print(f"[yellow]↳ osymandias.toml already exists, skipping[/yellow]")
    else:
        osy_toml_dest.write_text(
            "# OSymandias project config\n"
            "# List dotted module paths containing @osy.agent decorated functions.\n"
            "# If omitted, osy serve will auto-scan all .py files in this directory.\n"
            "# agent_modules = [\"myapp.agents\", \"myapp.crews\"]\n"
        )
        console.print("[green]✓[/green] osymandias.toml created")

    console.print("\n[bold green]Ready.[/bold green] Run [cyan]osy serve[/cyan] to start.\n")


# ─── osy serve ───────────────────────────────────────────────────────────────

@app.command()
def serve(
    no_docker: bool = typer.Option(
        False, "--no-docker",
        help="Skip Docker — connect to externally managed services via OSY_* env vars.",
        envvar="OSY_NO_DOCKER",
    ),
    concurrency: int = typer.Option(
        4, "--concurrency",
        help="Number of concurrent Celery worker slots (default 4).",
        envvar="OSY_WORKER_CONCURRENCY",
    ),
):
    """Start the full OSymandias runtime."""
    from osymandias.process import ProcessManager
    from osymandias.discovery import discover
    from osymandias.decorator import _TOOL_REGISTRY

    cwd = Path.cwd()
    manager = ProcessManager()

    console.print("\n[bold cyan]osy serve[/bold cyan]\n")

    # 1. Load .env first so OSY_NO_DOCKER and service URLs are available
    env_file = cwd / ENV_FILENAME
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)
        console.print(f"[dim]✓ Loaded {ENV_FILENAME}[/dim]")
    else:
        console.print(f"[yellow]⚠ No {ENV_FILENAME} found — using environment variables[/yellow]")

    # Re-read OSY_NO_DOCKER after .env load (envvar= on the Option handles CLI,
    # but load_dotenv runs after typer parses args, so we check again here)
    import os as _os
    if not no_docker and _os.environ.get("OSY_NO_DOCKER", "").lower() in ("1", "true", "yes"):
        no_docker = True

    if no_docker:
        console.print("[dim]  mode: [bold]no-docker[/bold] — using external services[/dim]")

    # 2. Docker infra (skipped in no-docker mode)
    compose_env: dict = {}
    compose_path = None
    with_frontend = False

    if no_docker:
        # Verify that the external services are reachable before starting workers
        _check_external_services()
    else:
        # 2a. Check Docker daemon
        _require_docker()

        # 2b. Resolve compose file
        compose_path = _resolve_compose(cwd)

        # 2c. Resolve frontend + nginx
        compose_env = {**_os.environ}
        frontend_dir = _resolve_frontend_dir(cwd)
        if frontend_dir:
            nginx_conf = _resolve_nginx_conf(cwd)
            if nginx_conf:
                compose_env["OSY_FRONTEND_DIR"] = str(frontend_dir)
                compose_env["OSY_NGINX_CONF"]   = str(nginx_conf)
                with_frontend = True
            else:
                console.print(f"[yellow]⚠ {NGINX_CONF_FILENAME} not found — dashboard unavailable[/yellow]")
        else:
            console.print(f"[yellow]⚠ No frontend build — run [cyan]npm run dev[/cyan] in frontend/ for the dashboard[/yellow]")

        # 2d. Start infra containers
        console.print("[dim]↓ Starting infrastructure...[/dim]")
        subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "up", "-d"],
            env=compose_env, check=True,
        )
        _wait_healthy(compose_path)
        console.print(f"[green]✓[/green] Infrastructure  [dim]postgres · redis · rabbitmq · qdrant[/dim]")

    # 3. Run migrations
    console.print("[dim]↓ Running database migrations...[/dim]")
    _run_migrations()
    console.print("[dim]✓ Migrations applied[/dim]")

    # 4. Discover @osy.tool functions
    console.print("[dim]↓ Scanning for @osy.tool functions...[/dim]")
    discover(cwd)
    console.print(f"[dim]✓ {len(_TOOL_REGISTRY)} tool(s) registered[/dim]")

    # 4b. Discover @osy.agent functions
    from osymandias.discovery import discover_agents
    from osymandias.decorator import _AGENT_REGISTRY
    agent_count = discover_agents(cwd)
    if agent_count:
        console.print(f"[dim]✓ {agent_count} external agent(s) discovered[/dim]")

    # 5. Start tool server
    manager.start("tool-server", [
        sys.executable, "-m", "uvicorn",
        "osymandias.tool_server:app",
        "--host", "0.0.0.0",
        "--port", str(TOOL_SERVER_PORT),
        "--log-level", "warning",
    ])

    # 6. Register @osy.tool tools in DB
    time.sleep(1.5)
    _register_tools_in_db(_TOOL_REGISTRY)

    # 7. Start FastAPI runtime
    manager.start("api", [
        sys.executable, "-m", "uvicorn",
        "osymandias.runtime.main:app",
        "--host", "0.0.0.0",
        "--port", str(RUNTIME_PORT),
        "--log-level", "warning",
    ])

    # 8. Start nginx (Docker mode only — no-docker users manage their own proxy)
    if with_frontend and compose_path:
        subprocess.run(
            ["docker", "compose", "-f", str(compose_path), "--profile", "frontend", "up", "-d", "nginx"],
            env=compose_env, check=True,
        )

    # 9. Start Celery workers
    pool = "solo" if sys.platform == "win32" else "prefork"
    manager.start("workers", [
        sys.executable, "-m", "celery",
        "-A", "osymandias.runtime.workers.celery_app",
        "worker",
        f"--pool={pool}",
        "--loglevel=warning",
        f"--concurrency={concurrency}",
    ])

    time.sleep(2)
    from rich.panel import Panel
    from rich.text import Text
    lines = Text()
    lines.append(f"  Tool server  ", style="dim")
    lines.append(f"http://localhost:{TOOL_SERVER_PORT}", style="cyan")
    lines.append(f"  ({len(_TOOL_REGISTRY)} tools)\n", style="dim")
    lines.append(f"  API          ", style="dim")
    lines.append(f"http://localhost:{RUNTIME_PORT}/api/v1", style="cyan")
    lines.append("\n")
    if with_frontend:
        lines.append(f"  Dashboard    ", style="dim")
        lines.append(f"http://localhost:{FRONTEND_PORT}", style="bold cyan")
    elif no_docker:
        lines.append(f"  Dashboard    serve frontend/out with your own proxy", style="dim")
    else:
        lines.append(f"  Dashboard    cd frontend && npm run dev", style="dim")
    lines.append("\n\n")
    lines.append("  Press Ctrl+C to stop.", style="dim")
    console.print(Panel(lines, title="[green]OSymandias ready[/green]", border_style="green", padding=(0, 1)))

    manager.wait_all()


# ─── osy logs ────────────────────────────────────────────────────────────────

@app.command()
def logs(
    job_id: str = typer.Argument(None, help="Job ID (or prefix) to tail. Omit for all recent events."),
    follow: bool = typer.Option(False, "--follow", "-f", help="Subscribe to Redis and stream new events in real time."),
    limit: int = typer.Option(50, "--limit", "-n", help="Number of past events to show (default 50)."),
    event_type: str = typer.Option(None, "--type", "-t", help="Filter by event type (e.g. TASK_PROGRESS)."),
):
    """Tail events for a job or the global event stream.

    Examples:\n
        osy logs                        # last 50 events across all jobs\n
        osy logs <job-id>               # last 50 events for a specific job\n
        osy logs <job-id> -f            # live-stream events as they arrive\n
        osy logs <job-id> -f -t TASK_PROGRESS  # live-stream only TASK_PROGRESS
    """
    import os
    import httpx
    from pathlib import Path

    cwd = Path.cwd()
    env_file = cwd / ENV_FILENAME
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)

    api_base = f"http://localhost:{RUNTIME_PORT}/api/v1"

    # ── Resolve full job ID if a prefix was given ────────────────────────────
    resolved_job_id: str | None = None
    if job_id:
        try:
            with httpx.Client(timeout=5) as c:
                jobs = c.get(f"{api_base}/jobs", params={"limit": 200}).json()
            matches = [j for j in jobs if j["id"].startswith(job_id)]
            if not matches:
                console.print(f"[red]✗ No job found matching '{job_id}'[/red]")
                raise typer.Exit(1)
            resolved_job_id = matches[0]["id"]
            if len(matches) > 1:
                console.print(f"[yellow]⚠ Multiple jobs match '{job_id}' — using {resolved_job_id[:8]}[/yellow]")
        except httpx.ConnectError:
            console.print(f"[red]✗ Cannot reach {api_base} — is `osy serve` running?[/red]")
            raise typer.Exit(1)

    # ── Print past events ─────────────────────────────────────────────────────
    _EV_COLOR = {
        "JOB_CREATED": "cyan",    "JOB_STARTED": "cyan",
        "JOB_COMPLETED": "green", "JOB_FAILED": "red",  "JOB_CANCELLED": "yellow",
        "TASK_CREATED": "cyan",   "TASK_STARTED": "blue",
        "TASK_COMPLETED": "green","TASK_FAILED": "red",  "TASK_PROGRESS": "yellow",
        "AGENT_RUNNING": "blue",  "AGENT_TERMINATED": "green",
        "TOOL_CALL_STARTED": "yellow", "TOOL_CALL_COMPLETED": "green",
        "LLM_CALL_STARTED": "dim", "LLM_CALL_COMPLETED": "dim",
        "PLANNER_FALLBACK": "bold red",
    }

    def _print_event(ev: dict) -> None:
        ts = ev.get("timestamp", "")[:19].replace("T", " ")
        etype = ev.get("event_type", "EVENT")
        color = _EV_COLOR.get(etype, "white")
        payload = ev.get("payload") or {}
        task_id = ev.get("task_id", "")
        tid = f"[dim]{task_id[:8]}[/dim] " if task_id else ""
        # Pick most informative payload key
        detail = (
            payload.get("title") or payload.get("tool_name") or
            payload.get("agent_type") or payload.get("step") or
            payload.get("message") or payload.get("reason") or ""
        )
        detail_str = f"  [dim]{detail}[/dim]" if detail else ""
        console.print(f"[dim]{ts}[/dim]  {tid}[{color}]{etype}[/{color}]{detail_str}")

    try:
        with httpx.Client(timeout=10) as c:
            params: dict = {"limit": limit}
            if resolved_job_id:
                params["job_id"] = resolved_job_id
            if event_type:
                params["event_type"] = event_type
            resp = c.get(f"{api_base}/events", params=params)
            resp.raise_for_status()
            past = list(reversed(resp.json()))  # oldest first
    except Exception as exc:
        console.print(f"[red]✗ Failed to fetch events: {exc}[/red]")
        raise typer.Exit(1)

    for ev in past:
        _print_event(ev)

    if not follow:
        console.print(f"\n[dim]{len(past)} event(s). Use -f to stream live.[/dim]")
        return

    # ── Live stream via Redis pub/sub ─────────────────────────────────────────
    import json as _json
    import redis as _redis
    redis_url = os.environ.get("OSY_REDIS_URL", "redis://localhost:47763/0")

    console.print(f"\n[dim]Streaming live events (Ctrl+C to stop)…[/dim]")
    try:
        r = _redis.from_url(redis_url, decode_responses=True)
        pubsub = r.pubsub(ignore_subscribe_messages=True)
        channel = f"events:job:{resolved_job_id}" if resolved_job_id else "events:global"
        pubsub.subscribe(channel)
        for msg in pubsub.listen():
            if msg["type"] != "message":
                continue
            try:
                ev = _json.loads(msg["data"])
            except Exception:
                continue
            if event_type and ev.get("event_type") != event_type:
                continue
            _print_event(ev)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped.[/dim]")
    except Exception as exc:
        console.print(f"[red]✗ Redis error: {exc}[/red]")
        raise typer.Exit(1)


# ─── osy workers ─────────────────────────────────────────────────────────────

@app.command()
def workers(
    queues: str = typer.Option(
        "agents,tools,evaluator",
        "--queues",
        help="Comma-separated list of Celery queues to consume (default: agents,tools,evaluator).",
        envvar="OSY_WORKER_QUEUES",
    ),
    concurrency: int = typer.Option(
        4, "--concurrency",
        help="Number of concurrent worker slots (default 4).",
        envvar="OSY_WORKER_CONCURRENCY",
    ),
    loglevel: str = typer.Option(
        "warning", "--loglevel",
        help="Celery log level (debug|info|warning|error).",
    ),
):
    """Start additional Celery workers for horizontal scaling.

    Run this on any machine that can reach the same RabbitMQ and Redis
    instances (set OSY_RABBITMQ_URL and OSY_REDIS_URL in the environment
    or in a local .env file).  The API server does NOT need to run on
    the same machine.

    Example — two extra worker nodes:\n
        # node-2\n
        OSY_RABBITMQ_URL=amqp://... OSY_REDIS_URL=redis://... osy workers\n\n
        # node-3 (agents only, 8 slots)\n
        osy workers --queues agents --concurrency 8
    """
    cwd = Path.cwd()

    # Load .env if present
    env_file = cwd / ENV_FILENAME
    if env_file.exists():
        from dotenv import load_dotenv
        load_dotenv(env_file, override=True)

    console.print(f"\n[bold cyan]osy workers[/bold cyan]  queues=[cyan]{queues}[/cyan]  concurrency=[cyan]{concurrency}[/cyan]\n")

    pool = "solo" if sys.platform == "win32" else "prefork"
    cmd = [
        sys.executable, "-m", "celery",
        "-A", "osymandias.runtime.workers.celery_app",
        "worker",
        f"--pool={pool}",
        f"--loglevel={loglevel}",
        f"--concurrency={concurrency}",
        f"--queues={queues}",
    ]

    console.print(f"[dim]Starting worker: {' '.join(cmd[2:])}[/dim]")
    try:
        subprocess.run(cmd, check=True)
    except KeyboardInterrupt:
        console.print("\n[dim]Workers stopped.[/dim]")


# ─── osy stop ────────────────────────────────────────────────────────────────

@app.command()
def stop():
    """Pause the Docker infrastructure (containers stay, data preserved)."""
    _kill_local_processes()
    if not _docker_available():
        console.print("[dim]No Docker — local processes stopped.[/dim]")
        return
    try:
        compose_path = _find_compose()
        console.print("[dim]Stopping infrastructure...[/dim]")
        subprocess.run(["docker", "compose", "-f", str(compose_path), "stop"], check=False)
        console.print("[green]✓[/green] Infrastructure stopped.  Data preserved.")
    except SystemExit:
        console.print("[dim]No compose file found — skipping Docker stop.[/dim]")


# ─── osy down ────────────────────────────────────────────────────────────────

@app.command()
def down():
    """Remove containers but keep volumes (data preserved)."""
    _kill_local_processes()
    if not _docker_available():
        console.print("[dim]No Docker — local processes stopped.[/dim]")
        return
    try:
        compose_path = _find_compose()
        console.print("[dim]Bringing down containers...[/dim]")
        subprocess.run(["docker", "compose", "-f", str(compose_path), "down"], check=False)
        console.print("[green]✓[/green] Containers removed.  Volumes preserved.")
    except SystemExit:
        console.print("[dim]No compose file found — skipping Docker down.[/dim]")


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
    # Force-remove containers first so named volumes are not "in use"
    subprocess.run(
        ["docker", "compose", "-f", str(compose_path), "down", "--timeout", "5"],
        check=False,
        capture_output=True,
    )
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
        console.print("  Or use [cyan]osy serve --no-docker[/cyan] to connect to external services.")
        raise typer.Exit(1)


def _check_external_services() -> None:
    """Verify that external Postgres, Redis, and RabbitMQ are reachable."""
    import os
    import socket
    import urllib.parse

    services = {
        "postgres":  os.environ.get("OSY_POSTGRES_URL", ""),
        "redis":     os.environ.get("OSY_REDIS_URL", ""),
        "rabbitmq":  os.environ.get("OSY_RABBITMQ_URL", ""),
    }

    failures: list[str] = []
    for name, url in services.items():
        if not url:
            console.print(f"[yellow]⚠ {name}: OSY_{name.upper()}_URL not set — skipping check[/yellow]")
            continue
        try:
            # Strip scheme variants to get host:port
            normalized = url
            for prefix in ("postgresql+asyncpg://", "postgresql+psycopg2://",
                           "postgresql://", "redis://", "amqp://"):
                if normalized.startswith(prefix):
                    normalized = "tcp://" + normalized[len(prefix):]
                    break
            parsed = urllib.parse.urlparse(normalized)
            host = parsed.hostname or "localhost"
            port = parsed.port or {"postgres": 5432, "redis": 6379, "rabbitmq": 5672}[name]
            sock = socket.create_connection((host, port), timeout=4)
            sock.close()
            console.print(f"[green]✓[/green] {name}  [dim]{host}:{port}[/dim]")
        except Exception as exc:
            console.print(f"[red]✗ {name}[/red]  [dim]{exc}[/dim]")
            failures.append(name)

    if failures:
        console.print(f"\n[red bold]Cannot reach: {', '.join(failures)}[/red bold]")
        console.print("  Update OSY_* URLs in your [cyan].env[/cyan] and ensure the services are running.")
        raise typer.Exit(1)


def _kill_local_processes() -> None:
    """Kill any local Python processes still bound to osy ports (API + tool server)."""
    import signal
    ports = [RUNTIME_PORT, TOOL_SERVER_PORT]
    killed = []
    try:
        import psutil
        for proc in psutil.process_iter(["pid", "connections"]):
            try:
                for conn in proc.connections(kind="inet"):
                    if conn.laddr.port in ports and conn.status == "LISTEN":
                        proc.kill()
                        killed.append(proc.pid)
                        break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
    except ImportError:
        # psutil not available — fall back to platform-specific approach
        if sys.platform == "win32":
            for port in ports:
                result = subprocess.run(
                    ["netstat", "-ano"],
                    capture_output=True, text=True,
                )
                for line in result.stdout.splitlines():
                    if f":{port} " in line and "LISTENING" in line:
                        parts = line.split()
                        pid = parts[-1]
                        if pid.isdigit():
                            subprocess.run(["taskkill", "/F", "/PID", pid], capture_output=True)
                            killed.append(int(pid))
        else:
            for port in ports:
                subprocess.run(
                    ["fuser", "-k", f"{port}/tcp"],
                    capture_output=True,
                )
    if killed:
        console.print(f"[dim]  Stopped local processes: {killed}[/dim]")


def _docker_available() -> bool:
    try:
        subprocess.run(["docker", "info"], capture_output=True, check=True, timeout=5)
        return True
    except Exception:
        return False


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
    # 1. Bundled inside the installed wheel — preferred, works offline
    try:
        import osymandias as _pkg
        bundled = Path(_pkg.__file__).parent / "frontend_dist"
        if bundled.exists() and any(bundled.iterdir()):
            return bundled
    except Exception:
        pass

    # 2. GitHub asset fetch / local dev build
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
    db_url = os.environ.get("OSY_POSTGRES_URL", "postgresql+asyncpg://osy:osy@localhost:47762/osymandias")

    # Alembic env.py uses a sync engine — swap asyncpg for psycopg2 so
    # migrations work on all platforms without an asyncio event loop.
    sync_url = db_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")

    cfg = Config()
    cfg.set_main_option("script_location", str(runtime_dir / "alembic"))
    cfg.set_main_option("sqlalchemy.url", sync_url)

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

# Infrastructure — managed by osy serve (Docker).
# To use external/managed services instead of Docker, set OSY_NO_DOCKER=1
# and point these URLs to your own instances.
# OSY_NO_DOCKER=1
OSY_POSTGRES_URL=postgresql+asyncpg://osy:osy@localhost:47762/osymandias
OSY_REDIS_URL=redis://localhost:47763/0
OSY_RABBITMQ_URL=amqp://guest:guest@localhost:47764/
OSY_QDRANT_URL=http://localhost:47766

# CORS (frontend on {FRONTEND_PORT}, direct API access on {RUNTIME_PORT})
OSY_CORS_ORIGINS=http://localhost:{FRONTEND_PORT},http://localhost:{RUNTIME_PORT}

# Tool server (internal)
OSY_TOOL_SERVER_URL=http://localhost:{TOOL_SERVER_PORT}

# Scaling — number of concurrent Celery worker slots on this node.
# Increase for CPU-bound workloads; run `osy workers` on additional
# machines to scale horizontally.
# OSY_WORKER_CONCURRENCY=4

# Auth (optional) — protect the API with a static key.
# When set, all /api/v1/* requests must include:
#   Authorization: Bearer <key>   or   X-Api-Key: <key>
# Leave empty (or omit) to disable auth entirely.
# OSY_API_KEY=
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

    location ~ ^/jobs/[^/]+$ {{
        try_files $uri $uri.html /jobs/_.html;
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
