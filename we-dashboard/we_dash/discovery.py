from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path
import os
from typing import Iterable

from .models import Service


_SERVICE_RE = re.compile(r"^SERVICE\s*[:]?=\s*(?P<name>[^\s#]+)")


def _read_service_name(makefile: Path, fallback: str) -> str:
    try:
        # Read small portion to avoid huge files
        for line in makefile.read_text(errors="ignore").splitlines():
            m = _SERVICE_RE.match(line.strip())
            if m:
                return m.group("name").strip()
    except Exception:
        pass
    return fallback


def _hash8(path: Path) -> str:
    h = hashlib.sha1(str(path.resolve()).encode())
    return h.hexdigest()[:8]


def _read_pid(pid_file: Path) -> int:
    try:
        text = pid_file.read_text().strip()
        return int(text)
    except Exception:
        return 0


def _runlog_path(service_dir: Path, service_name: str) -> Path | None:
    p = service_dir / ".we" / service_name / "run.log"
    return p if p.exists() else None


def discover_services(roots: Iterable[Path], max_depth: int = 5) -> list[Service]:
    """Discover services under roots by presence of `.we.pid` and `Makefile`.

    - Searches recursively to at most `max_depth` levels from each root.
    - A directory qualifies if both files exist directly inside it.
    """
    services: list[Service] = []
    roots = [Path(r).resolve() for r in roots]

    for root in roots:
        if not root.exists():
            continue
        # Walk manually to enforce depth limit
        for dirpath in _walk_limited(root, max_depth):
            pid_file = dirpath / ".we.pid"
            makefile = dirpath / "Makefile"
            if not (pid_file.exists() and makefile.exists() and dirpath.is_dir()):
                continue

            fallback_name = dirpath.name
            name = _read_service_name(makefile, fallback=fallback_name)
            unit = f"we-{name}-{_hash8(dirpath)}"
            pid = _read_pid(pid_file)
            runlog = _runlog_path(dirpath, name)
            project = _infer_project(dirpath, roots)
            services.append(Service(name=name, dir=dirpath, pid=pid, unit=unit, runlog=runlog, project=project))

    # Stable sort: by name then path
    services.sort(key=lambda s: (s.name.lower(), str(s.dir)))
    return services


IGNORE_DIRS = {".git", ".hg", ".svn", ".venv", "venv", "node_modules", "dist", "build", "target", "__pycache__"}


def _walk_limited(root: Path, max_depth: int):
    """Yield directories up to max_depth relative to root (0 means root only).

    Uses os.walk with topdown traversal so we can prune ignored or too-deep directories
    without stat-ing every nested path.
    """
    root = root.resolve()
    max_depth = max(0, int(max_depth))
    base_depth = len(root.parts)
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        cur_path = Path(dirpath)
        # Prune ignored directories in-place
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        # Compute depth relative to root
        depth = len(Path(dirpath).parts) - base_depth
        if depth > max_depth:
            # Stop descending further by clearing dirnames
            dirnames[:] = []
            continue
        yield cur_path


def _infer_project(service_dir: Path, roots: list[Path]) -> str | None:
    for root in roots:
        try:
            rel = service_dir.resolve().relative_to(root)
        except Exception:
            continue
        if rel.parts:
            return rel.parts[0]
        else:
            return root.name
    return None
