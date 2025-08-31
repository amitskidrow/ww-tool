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


def build_watchfiles_exec(inner_argv: Iterable[str], watch_paths: Optional[list[str]] = None) -> list[str]:
    # Use uvx to run watchfiles without requiring a global install
    wf_version = os.getenv("WW_WF_VERSION")
    tool = "watchfiles" if not wf_version else f"watchfiles=={wf_version}"
    # Built-in python filter; target is a single shell command string
    import shlex

    target = " ".join(shlex.quote(a) for a in inner_argv)
    base = ["uvx", tool, "--filter", "python", "--target-type", "command", target]
    if watch_paths:
        base.extend(watch_paths)
    return base


def env_list(extra_ignores: Optional[str] = None) -> list[str]:
    env = []
    if extra_ignores:
        env.append(f"WW_IGNORE={extra_ignores}")
    return env
