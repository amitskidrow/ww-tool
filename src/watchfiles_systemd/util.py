import json
import os
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional


def is_tty() -> bool:
    try:
        return sys.stdout.isatty()
    except Exception:
        return False


def to_slug(name: str) -> str:
    s = name.strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s)
    return s.strip("-")


def unit_name_from_slug(slug: str) -> str:
    if not slug.endswith(".service"):
        return f"ww-{slug}.service"
    return slug


def json_line(obj: dict) -> str:
    return json.dumps(obj, separators=(",", ":"))


@dataclass
class ResolvedTarget:
    mode: str  # "file" or "dir"
    workdir: Path
    argv: list[str]
    default_name: str  # without .service
    watch_paths: list[str]


PY_IGNORES: tuple[str, ...] = (
    ".git/",
    "__pycache__/",
    ".venv/",
    "env/",
    ".tox/",
    ".pytest_cache/",
    ".mypy_cache/",
    "node_modules/",
    "dist/",
    "build/",
    ".idea/",
    ".vscode/",
)


def resolve_target(path: Path) -> ResolvedTarget:
    p = path.resolve()
    if p.is_file():
        workdir = p.parent
        argv = ["python", str(p.name)]
        name = to_slug(p.stem)
        return ResolvedTarget("file", workdir, argv, name, [str(p)])

    if p.is_dir():
        # Directory mode: __main__.py -> python -m <pkg> with workdir=parent
        main_pkg = p / "__main__.py"
        main_py = p / "main.py"
        app_py = p / "app.py"
        if main_pkg.exists():
            workdir = p.parent
            argv = ["python", "-m", p.name]
            name = to_slug(p.name)
            return ResolvedTarget("dir", workdir, argv, name, [str(p)])
        elif main_py.exists():
            workdir = p
            argv = ["python", "main.py"]
            name = to_slug(p.name)
            return ResolvedTarget("dir", workdir, argv, name, [str(p)])
        elif app_py.exists():
            workdir = p
            argv = ["python", "app.py"]
            name = to_slug(p.name)
            return ResolvedTarget("dir", workdir, argv, name, [str(p)])
        else:
            raise FileNotFoundError(
                f"No entrypoint found under '{p}'. Try a file, or add __main__.py / main.py / app.py."
            )
    raise FileNotFoundError(f"Path not found: {p}")


def _resolve_uvx_bin() -> str:
    """Resolve uvx binary path. Honors WW_UV_BIN, falls back to PATH lookup."""
    prefer = os.getenv("WW_UV_BIN", "uvx").strip()
    if os.path.sep in prefer:
        return prefer
    import shutil

    which = shutil.which(prefer)
    return which or prefer


def build_watchfiles_exec(inner_argv: Iterable[str], watch_paths: Optional[list[str]] = None) -> list[str]:
    # Use uvx + python -m watchfiles to avoid console-script resolution pitfalls
    wf_version = os.getenv("WW_WF_VERSION")
    spec = "watchfiles" if not wf_version else f"watchfiles=={wf_version}"
    # Built-in python filter; target is a single shell command string
    import shlex

    target = " ".join(shlex.quote(a) for a in inner_argv)
    uvx_bin = _resolve_uvx_bin()
    base = [
        uvx_bin,
        "--from",
        spec,
        "python",
        "-m",
        "watchfiles",
        "--filter",
        "python",
        "--target-type",
        "command",
        target,
    ]

    # Combine ignore paths: built-ins plus optional WW_IGNORE (comma-separated)
    extra = os.getenv("WW_IGNORE", "").strip()
    ignores = [p.rstrip("/") for p in PY_IGNORES]
    if extra:
        # split on comma, strip whitespace and trailing slashes
        ignores.extend(x.strip().rstrip("/") for x in extra.split(",") if x.strip())
    # de-dupe while preserving order
    seen = set()
    ignores = [x for x in ignores if not (x in seen or seen.add(x))]
    if ignores:
        base.extend(["--ignore-paths", ",".join(ignores)])

    if watch_paths:
        base.extend(watch_paths)
    return base


def env_list(extra_ignores: Optional[str] = None) -> list[str]:
    env = []
    if extra_ignores:
        env.append(f"WW_IGNORE={extra_ignores}")
    # Inherit PATH/HOME so systemd environment can resolve tools and caches
    path = os.environ.get("PATH")
    home = os.environ.get("HOME")
    if path:
        env.append(f"PATH={path}")
    if home:
        env.append(f"HOME={home}")
    # Pass-through overrides for visibility/debugging
    uv_bin = os.environ.get("WW_UV_BIN")
    if uv_bin:
        env.append(f"WW_UV_BIN={uv_bin}")
    wf_version = os.environ.get("WW_WF_VERSION")
    if wf_version:
        env.append(f"WW_WF_VERSION={wf_version}")
    return env
