from __future__ import annotations

from pathlib import Path
from typing import Iterable

from .models import Service
from ..systemd_bus import connect_user_bus, list_units, get_unit_status


def _friendly_from_unit(unit_name: str) -> str:
    n = unit_name
    if n.endswith(".service"):
        n = n[: -len(".service")]
    if n.startswith("ww-"):
        n = n[len("ww-") :]
    return n


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


async def discover_services_ww(roots: Iterable[Path], max_depth: int = 5) -> list[Service]:
    """Discover ww units via D‑Bus and map to Service rows.

    - roots are used only to compute a 'project' label by path prefix.
    - max_depth is ignored here (ww discovery is global); retained for option parity.
    """
    bus = await connect_user_bus()
    units = await list_units(bus)
    roots_resolved = [Path(r).resolve() for r in roots]

    services: list[Service] = []
    for u in units:
        name = u.get("Name") or ""
        if not name.startswith("ww-"):
            continue
        path = u.get("Path")
        if not path:
            continue
        st = await get_unit_status(bus, path)
        wd = st.get("WorkingDirectory")
        try:
            workdir = Path(wd) if isinstance(wd, str) and wd else Path.cwd()
        except Exception:
            workdir = Path.cwd()
        friendly = _friendly_from_unit(name)
        pid = int(st.get("MainPID") or 0)
        active = st.get("ActiveState") or "unknown"
        proj = _infer_project(workdir, roots_resolved)
        services.append(
            Service(
                name=friendly,
                dir=workdir,
                pid=pid,
                unit=name,
                runlog=None,  # we prefer ww logs/journal, no file reliance
                project=proj,
                active=active,
            )
        )

    # Stable sort by name then path
    services.sort(key=lambda s: (s.name.lower(), str(s.dir)))
    return services

