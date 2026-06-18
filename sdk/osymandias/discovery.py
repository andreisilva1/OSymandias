import ast
import importlib
import importlib.util
import sys
from pathlib import Path

_SKIP_DIRS = {
    "__pycache__", ".git", ".venv", "venv", ".env",
    "node_modules", "site-packages", ".pytest_cache",
    "dist", "build", "*.egg-info",
}


def _imports_osymandias(path: Path) -> bool:
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="ignore"))
    except SyntaxError:
        return False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            if any(alias.name.startswith("osymandias") for alias in node.names):
                return True
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module.startswith("osymandias"):
                return True
    return False


def _import_file(path: Path) -> None:
    module_name = f"_osy_user_{path.stem}_{id(path)}"
    spec = importlib.util.spec_from_file_location(module_name, path)
    if spec is None or spec.loader is None:
        return
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)  # type: ignore[attr-defined]
    except Exception:
        pass


def _load_agent_modules_config(root: Path) -> list[str]:
    """Read agent_modules from osymandias.toml or pyproject.toml [tool.osymandias]."""
    # osymandias.toml takes priority
    osy_toml = root / "osymandias.toml"
    if osy_toml.exists():
        try:
            import tomllib  # Python 3.11+
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                return []
        data = tomllib.loads(osy_toml.read_text())
        return data.get("agent_modules", [])

    # Fallback: pyproject.toml [tool.osymandias]
    pyproject = root / "pyproject.toml"
    if pyproject.exists():
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                return []
        data = tomllib.loads(pyproject.read_text())
        return data.get("tool", {}).get("osymandias", {}).get("agent_modules", [])

    return []


def discover_agents(root: Path) -> int:
    """Import modules listed in agent_modules config to populate _AGENT_REGISTRY.

    Falls back to scanning all .py files that import osymandias if no config found.
    Returns the number of newly registered agents.
    """
    from osymandias.decorator import _AGENT_REGISTRY
    before = len(_AGENT_REGISTRY)

    modules = _load_agent_modules_config(root)
    if modules:
        for dotted in modules:
            try:
                importlib.import_module(dotted)
            except Exception:
                pass
    else:
        # Auto-scan fallback: same approach as discover() for tools
        for path in sorted(root.rglob("*.py")):
            if any(part in _SKIP_DIRS for part in path.parts):
                continue
            if _imports_osymandias(path):
                _import_file(path)

    return len(_AGENT_REGISTRY) - before


def discover(root: Path) -> int:
    from osymandias.decorator import _TOOL_REGISTRY

    before = len(_TOOL_REGISTRY)

    for path in sorted(root.rglob("*.py")):
        if any(part in _SKIP_DIRS for part in path.parts):
            continue
        if _imports_osymandias(path):
            _import_file(path)

    return len(_TOOL_REGISTRY) - before
