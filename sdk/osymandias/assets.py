"""
Fetches versioned assets from GitHub (OSY.compose.yml, frontend-static.tar.gz)
and caches them in ~/.osy/cache/{version}/.
"""
import tarfile
from pathlib import Path

import httpx

GITHUB_REPO = "andreisilva1/OSymandias"
GITHUB_RAW = f"https://raw.githubusercontent.com/{GITHUB_REPO}"
GITHUB_RELEASES = f"https://github.com/{GITHUB_REPO}/releases/download"


def _version() -> str:
    import osymandias
    return osymandias.__version__


def _tag() -> str:
    return f"v{_version()}"


def cache_dir() -> Path:
    d = Path.home() / ".osy" / "cache" / _version()
    d.mkdir(parents=True, exist_ok=True)
    return d


def frontend_dir() -> Path:
    return cache_dir() / "frontend"


def compose_cache_path() -> Path:
    return cache_dir() / "OSY.compose.yml"


def fetch_compose(dest: Path) -> None:
    url = f"{GITHUB_RAW}/{_tag()}/OSY.compose.yml"
    _download_text(url, dest)
    # also save to cache
    if dest != compose_cache_path():
        import shutil
        shutil.copy2(dest, compose_cache_path())


def ensure_frontend() -> Path:
    fdir = frontend_dir()
    if fdir.exists() and any(fdir.iterdir()):
        return fdir

    url = f"{GITHUB_RELEASES}/{_tag()}/frontend-static.tar.gz"
    tar_path = cache_dir() / "frontend-static.tar.gz"
    _download_binary(url, tar_path)

    fdir.mkdir(parents=True, exist_ok=True)
    with tarfile.open(tar_path, "r:gz") as tf:
        tf.extractall(fdir)
    tar_path.unlink(missing_ok=True)
    return fdir


def nginx_conf_cache_path() -> Path:
    return cache_dir() / "OSY.nginx.conf"


def ensure_nginx_conf(local: Path) -> Path:
    if local.exists():
        return local
    cached = nginx_conf_cache_path()
    if cached.exists():
        return cached
    url = f"{GITHUB_RAW}/{_tag()}/OSY.nginx.conf"
    _download_text(url, local)
    import shutil
    shutil.copy2(local, cached)
    return local


def ensure_compose(local: Path) -> Path:
    if local.exists():
        return local
    cached = compose_cache_path()
    if cached.exists():
        return cached
    # try fetching from GitHub
    fetch_compose(local)
    return local


def _download_text(url: str, dest: Path) -> None:
    try:
        resp = httpx.get(url, follow_redirects=True, timeout=15)
        resp.raise_for_status()
        dest.write_text(resp.text, encoding="utf-8")
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc


def _download_binary(url: str, dest: Path) -> None:
    try:
        with httpx.stream("GET", url, follow_redirects=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(dest, "wb") as f:
                for chunk in resp.iter_bytes(chunk_size=8192):
                    f.write(chunk)
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Failed to download {url}: {exc}") from exc
