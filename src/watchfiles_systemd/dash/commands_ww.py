from __future__ import annotations

import asyncio
from asyncio.subprocess import PIPE
from pathlib import Path

from .models import Service
from ..systemd_bus import connect_user_bus, get_unit_status


def follow_argv(service: Service) -> list[str]:
    """Always use ww logs -f for live follow."""
    return ["ww", "logs", service.unit, "-f"]


def last_logs_argv(service: Service, last: int = 200) -> list[str]:
    return ["ww", "logs", service.unit, "-n", str(last)]


def up_argv(service: Service) -> list[str]:
    # Restart is idempotent; starts if inactive
    return ["ww", "restart", service.unit]


def down_argv(service: Service) -> list[str]:
    return ["ww", "stop", service.unit]


async def restart_sequence(service: Service) -> list[list[str]] | None:
    return [["ww", "restart", service.unit]]


async def run_command(
    argv: list[str],
    cwd: Path,
    on_stdout_line: callable | None = None,
    on_stderr_line: callable | None = None,
) -> int:
    """Run a command streaming output via provided callbacks."""
    proc = await asyncio.create_subprocess_exec(
        *argv, cwd=str(cwd), stdout=PIPE, stderr=PIPE
    )

    async def _stream(reader, cb):
        if cb is None:
            # Drain
            while True:
                b = await reader.readline()
                if not b:
                    break
        else:
            while True:
                b = await reader.readline()
                if not b:
                    break
                try:
                    cb(b.decode(errors="ignore"))
                except Exception:
                    pass

    await asyncio.gather(_stream(proc.stdout, on_stdout_line), _stream(proc.stderr, on_stderr_line))
    return await proc.wait()


async def probe_status(service: Service) -> tuple[str | None, int | None]:
    """Return (ActiveState, MainPID) via D‑Bus show.

    On error, returns (None, None).
    """
    try:
        bus = await connect_user_bus()
        # We need the object path for the unit; run a fast snapshot via unit status
        # The caller updates only two fields from this method.
        # Since we don't have the path here, let ww caller keep prior state when this fails.
        # Optimization: could fetch and cache unit paths if needed later.
        # Here we just attempt to find PID/Active from a properties snapshot.
        # NOTE: Without the exact DBus object path we cannot fetch; so fallback to systemctl if needed.
        # However, our discovery stores unit names only; to avoid extra list_units roundtrip here,
        # we accept a minor inefficiency: reuse discovery approach later if optimizing.
        # For now, do a subprocess call as a safe fallback when path resolution isn't present.
        # But to keep pure D‑Bus, we do a light list_units scan.
        from ..systemd_bus import list_units
        for u in await list_units(bus):
            if u.get("Name") == service.unit:
                path = u.get("Path")
                if path:
                    st = await get_unit_status(bus, path)
                    active = st.get("ActiveState")
                    pid = int(st.get("MainPID") or 0)
                    return active, pid
        return None, None
    except Exception:
        return None, None

