import asyncio
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Optional

import typer
from dbus_next import Variant

from . import __version__
from .systemd_bus import (
    build_execstart_variant,
    connect_user_bus,
    get_main_pid,
    get_unit_path,
    list_units,
    get_unit_status,
    reset_failed_unit,
    restart_unit,
    start_transient,
    stop_unit,
)
from .util import (
    PY_IGNORES,
    ResolvedTarget,
    build_watchfiles_exec,
    env_list,
    is_tty,
    json_line,
    resolve_target,
    to_slug,
    unit_name_from_slug,
)
from .util import _resolve_uvx_bin


app = typer.Typer(
    name="ww",
    add_completion=False,
    no_args_is_help=True,
    help=(
        "watchfiles + systemd (user) — minimal process manager for Python dev.\n\n"
        "Usage:\n"
        "  ww <path>                  Start service from file/dir (live reload)\n"
        "  ww ps                      List active services (tab-separated)\n"
        "  ww logs <ident> [-n N|-f]  Show logs (journalctl)\n"
        "  ww status|pid <ident>      Show status / print PID\n"
        "  ww restart|stop|rm <ident> Restart / stop / remove unit\n"
        "  ww dash [opts]             Open Textual dashboard (ww units)\n\n"
        "Identifier (<ident>): friendly name from `ww ps`, a PID, or unit name (ww-*.service)."
    ),
    context_settings={"help_option_names": ["-h", "--help"]},
)


@app.callback()
def _root(
    version: Optional[bool] = typer.Option(
        None,
        "--version",
        help="Show version and exit",
        is_eager=True,
    )
):
    if version:
        typer.echo(__version__)
        raise typer.Exit()


def _ensure_tools():
    # Ensure uvx exists at runtime; advise if missing.
    uvx_bin = _resolve_uvx_bin()
    ok = bool(shutil.which(uvx_bin) or os.path.exists(uvx_bin))
    if not ok:
        typer.echo(
            "uvx not found. Install uv (Astral) or set WW_UV_BIN to absolute path.",
            err=True,
        )


def _friendly_from_unit(unit_name: str) -> str:
    n = unit_name
    if n.endswith(".service"):
        n = n[: -len(".service")]
    if n.startswith("ww-"):
        n = n[len("ww-") :]
    return n


async def _iter_ww_units(bus):
    units = await list_units(bus)
    return [u for u in units if u["Name"].startswith("ww-")]


async def _resolve_identifier(bus, ident: str) -> str:
    # 1) Exact unit name
    if ident.endswith(".service") or ident.startswith("ww-"):
        unit = ident if ident.endswith(".service") else f"{ident}.service"
        path = await get_unit_path(bus, unit)
        if not path:
            raise RuntimeError(f"Unit not found: {unit}")
        return unit

    # 2) Numeric PID
    if ident.isdigit():
        pid_target = int(ident)
        for u in await _iter_ww_units(bus):
            try:
                st = await get_unit_status(bus, u["Path"])
                if int(st.get("MainPID") or 0) == pid_target:
                    return u["Name"]
            except Exception:
                continue
        raise RuntimeError(f"No ww-* unit with PID {pid_target}")

    # 3) Friendly name (derived from unit)
    matches = []
    for u in await _iter_ww_units(bus):
        if _friendly_from_unit(u["Name"]) == ident:
            matches.append(u["Name"])
    if len(matches) == 1:
        return matches[0]
    if len(matches) > 1:
        opts = ", ".join(matches)
        raise RuntimeError(f"Ambiguous name '{ident}'. Candidates: {opts}")
    raise RuntimeError(f"Not found: {ident}")


async def _pick_free_name(bus, base_slug: str) -> str:
    # Try ww-<slug>.service, then ww-<slug>-2.service, etc.
    i = 1
    while True:
        suffix = "" if i == 1 else f"-{i}"
        name = unit_name_from_slug(f"{base_slug}{suffix}")
        path = await get_unit_path(bus, name)
        if path is None:
            return name
        i += 1


def _properties_for_target(target: ResolvedTarget, unit_name: str) -> list[tuple[str, Variant]]:
    inner = build_watchfiles_exec(target.argv, target.watch_paths)
    execstart = build_execstart_variant(inner)
    env = env_list(os.getenv("WW_IGNORE"))
    props = [
        ["Description", Variant("s", f"ww:{unit_name}")],
        ["WorkingDirectory", Variant("s", str(target.workdir))],
        ["Environment", Variant("as", env)],
        ["ExecStart", execstart],
        ["Restart", Variant("s", "on-failure")],
        ["RestartUSec", Variant("t", 3_000_000)],  # 3s
        ["StandardOutput", Variant("s", "journal")],
        ["StandardError", Variant("s", "journal")],
        ["KillMode", Variant("s", "control-group")],
        ["Type", Variant("s", "simple")],
    ]
    return props


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def version():
    """Show CLI version (semver)."""
    typer.echo(__version__)


@app.command("ps")
def ps():
    """List active services. Prints: name\tpid\tstate\tunit"""
    async def _ps():
        bus = await connect_user_bus()
        units = await list_units(bus)
        rows = []
        for u in units:
            name = u["Name"]
            if not name.startswith("ww-"):
                continue
            path = u["Path"]
            try:
                st = await get_unit_status(bus, path)
                act = st.get("ActiveState", "unknown")
                sub = st.get("SubState", "unknown")
                pid = int(st.get("MainPID") or 0)
                # Derive a clearer, human-friendly state
                if act == "failed":
                    state = "failed"
                elif act == "activating":
                    if sub == "auto-restart":
                        state = "flapping"
                    elif pid > 0:
                        state = f"activating({sub})"
                    else:
                        state = "activating"
                elif act == "active":
                    state = f"active({sub})" if sub and sub != "running" else "active"
                else:
                    state = act
            except Exception:
                state = u.get("ActiveState", "unknown")
                pid = 0
            friendly = _friendly_from_unit(name)
            rows.append((friendly, pid, state, name))
        for friendly, pid, state, unit in rows:
            typer.echo(f"{friendly}\t{pid}\t{state}\t{unit}")

    asyncio.run(_ps())


@app.command()
def status(name: str):
    """Show detailed status for a unit. Accepts friendly name, PID, or unit."""
    async def _status():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)
        path = await get_unit_path(bus, unit)
        if not path:
            typer.echo(f"Unit not found: {unit}", err=True)
            raise typer.Exit(code=1)
        st = await get_unit_status(bus, path)
        state = st.get("ActiveState", "unknown")
        sub = st.get("SubState", "unknown")
        pid_val = int(st.get("MainPID") or 0)
        restarts = st.get("NRestarts")
        result = st.get("Result")
        typer.echo(f"name: {unit}")
        typer.echo(f"state: {state} ({sub})")
        typer.echo(f"pid: {pid_val}")
        if isinstance(restarts, int):
            typer.echo(f"restarts: {restarts}")
        if isinstance(result, str) and result:
            typer.echo(f"result: {result}")
        typer.echo(f"log: ww logs {unit} -f")

    asyncio.run(_status())


@app.command()
def pid(name: str):
    """Print MainPID for a unit (integer only)."""
    async def _pid():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)
        path = await get_unit_path(bus, unit)
        if not path:
            raise typer.Exit(code=1)
        pid_val = await get_main_pid(bus, path)
        typer.echo(str(pid_val))

    asyncio.run(_pid())


@app.command()
def logs(
    name: str,
    n: int = typer.Option(100, "-n"),
    follow: bool = typer.Option(False, "-f"),
    all: bool = typer.Option(
        False, "-a", "--all", help="Show full history (not just since last start)"
    ),
):
    """Show journald logs for a unit. Use -f to follow.\n\nDefault: only since last start (use --all for full history)."""
    async def _logs():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)

        cmd = [
            "journalctl",
            "--user",
            "-u",
            unit,
            "-n",
            str(n),
        ]
        if not follow and not all:
            try:
                path = await get_unit_path(bus, unit)
                if path:
                    st = await get_unit_status(bus, path)
                    ts = int(st.get("ActiveEnterTimestamp") or 0)
                    if ts > 0:
                        secs = ts // 1_000_000
                        cmd.extend(["--since", f"@{secs}"])
            except Exception:
                pass
        if follow:
            cmd.append("-f")
        try:
            subprocess.run(cmd, check=False)
        except FileNotFoundError:
            typer.echo("journalctl not found. Ensure systemd-journald is available.", err=True)

    asyncio.run(_logs())


@app.command()
def restart(name: str):
    """Restart a unit (starts if inactive)."""
    async def _restart():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)
        await restart_unit(bus, unit)
        typer.echo(f"restarted {unit}")

    asyncio.run(_restart())


@app.command()
def stop(name: str):
    """Stop a unit."""
    async def _stop():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)
        await stop_unit(bus, unit)
        typer.echo(f"stopped {unit}")

    asyncio.run(_stop())


@app.command("rm")
def rm(name: str):
    """Stop and remove one unit (reset failed state)."""
    async def _rm():
        bus = await connect_user_bus()
        try:
            unit = await _resolve_identifier(bus, name)
        except RuntimeError as e:
            typer.echo(str(e), err=True)
            raise typer.Exit(code=1)
        await stop_unit(bus, unit)
        await reset_failed_unit(bus, unit)
        typer.echo(f"removed {unit}")

    asyncio.run(_rm())


def _iter_my_units_sync():
    async def _inner():
        bus = await connect_user_bus()
        units = await list_units(bus)
        return [u for u in units if u["Name"].startswith("ww-")]

    return asyncio.run(_inner())


@app.command("restart-all")
def restart_all():
    """Restart all ww-* units."""
    async def _restart_all():
        bus = await connect_user_bus()
        for u in await list_units(bus):
            name = u["Name"]
            if name.startswith("ww-"):
                await restart_unit(bus, name)
        typer.echo("restarted all ww-* units")

    asyncio.run(_restart_all())


@app.command("stop-all")
def stop_all():
    """Stop all ww-* units."""
    async def _stop_all():
        bus = await connect_user_bus()
        for u in await list_units(bus):
            name = u["Name"]
            if name.startswith("ww-"):
                await stop_unit(bus, name)
        typer.echo("stopped all ww-* units")

    asyncio.run(_stop_all())


@app.command("rm-all")
def rm_all():
    """Stop and remove all ww-* units."""
    async def _rm_all():
        bus = await connect_user_bus()
        for u in await list_units(bus):
            name = u["Name"]
            if name.startswith("ww-"):
                await stop_unit(bus, name)
                await reset_failed_unit(bus, name)
        typer.echo("removed all ww-* units")

    asyncio.run(_rm_all())


@app.command()
def doctor():
    """Diagnose systemd user bus, journald, and linger."""
    async def _doctor():
        ok_dbus = False
        try:
            bus = await connect_user_bus()
            # try simple manager introspection
            await list_units(bus)
            ok_dbus = True
        except Exception:
            ok_dbus = False

        # journalctl check
        ok_journal = False
        try:
            r = subprocess.run(["journalctl", "--user", "-n", "1"], stdout=subprocess.DEVNULL)
            ok_journal = r.returncode == 0
        except FileNotFoundError:
            ok_journal = False

        # linger check
        linger_hint = ""
        try:
            user = os.environ.get("USER") or subprocess.check_output(["whoami"]).decode().strip()
            out = subprocess.check_output(["loginctl", "show-user", user, "-p", "Linger"], stderr=subprocess.DEVNULL).decode()
            if "Linger=no" in out:
                linger_hint = "loginctl enable-linger $USER"
        except Exception:
            # Non-fatal
            pass

        # uvx + watchfiles checks (best-effort)
        uvx_bin = _resolve_uvx_bin()
        uvx_ok, uvx_ver = False, ""
        try:
            r = subprocess.run([uvx_bin, "--version"], capture_output=True, text=True)
            uvx_ok = r.returncode == 0
            uvx_ver = (r.stdout or r.stderr).strip().splitlines()[:1]
            uvx_ver = uvx_ver[0] if uvx_ver else ""
        except Exception:
            uvx_ok = False

        wf_spec = "watchfiles"
        if os.getenv("WW_WF_VERSION"):
            wf_spec = f"watchfiles=={os.getenv('WW_WF_VERSION')}"
        wf_ok = False
        try:
            r = subprocess.run([uvx_bin, "--from", wf_spec, "python", "-m", "watchfiles", "--help"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=15)
            wf_ok = r.returncode == 0
        except subprocess.TimeoutExpired:
            wf_ok = False
        except Exception:
            wf_ok = False

        typer.echo(f"user D-Bus: {'ok' if ok_dbus else 'FAIL'}")
        typer.echo(f"journalctl --user: {'ok' if ok_journal else 'FAIL'}")
        typer.echo(f"uvx: {'ok' if uvx_ok else 'FAIL'} {('(' + uvx_ver + ')') if uvx_ver else ''}")
        typer.echo(f"watchfiles via uvx: {'ok' if wf_ok else 'FAIL'}")
        if linger_hint:
            typer.echo(f"linger: off (enable via: {linger_hint})")
        else:
            typer.echo("linger: ok or unknown")

    asyncio.run(_doctor())


@app.command()
def dash(
    root: list[str] = typer.Option([], "--root", help="Root(s) to label projects by path prefix", show_default=False),
    max_depth: int = typer.Option(5, "--max-depth", help="Ignored (for parity only)"),
    columns: str = typer.Option("minimal", "--columns", help="Columns: minimal|full"),
    terminal_backend: str = typer.Option("auto", "--terminal-backend", help="Terminal backend: auto|native|tmux"),
):
    """Open the WW dashboard (Textual UI) over ww-* units."""
    try:
        import textual  # noqa: F401
    except Exception:
        typer.echo(
            "Dashboard requires 'textual'. Install extras: 'uv tool install --from <REPO_URL> ww[dash]' or 'pip install watchfiles-systemd[dash]'.",
            err=True,
        )
        raise typer.Exit(code=1)

    # Lazy import to avoid importing Textual at module import time
    try:
        from .dash.app import run_dash
    except Exception as e:
        typer.echo(f"Failed to load dashboard: {e}", err=True)
        raise typer.Exit(code=1)

    roots = [Path(r) for r in (root or [str(Path.cwd())])]
    run_dash(roots=roots, max_depth=max_depth, last=200, columns=columns, terminal_backend=terminal_backend)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def main(
    path: str = typer.Argument(..., help="File or directory to run with live reload"),
):
    """Start background job as a transient user unit with live reload."""
    _ensure_tools()
    p = Path(path)
    try:
        target = resolve_target(p)
    except FileNotFoundError as e:
        typer.echo(str(e), err=True)
        raise typer.Exit(code=2)

    async def _start():
        bus = await connect_user_bus()
        base_slug = to_slug(target.default_name)
        unit_name = await _pick_free_name(bus, base_slug)
        props = _properties_for_target(target, unit_name)
        try:
            await start_transient(bus, unit_name, props)
        except Exception as e:
            typer.echo(f"Failed to start unit: {e}", err=True)
            raise typer.Exit(code=1)

        # Report status, pid and hint (use live properties)
        path = await get_unit_path(bus, unit_name)
        pid_val = 0
        state = "unknown"
        sub = ""
        if path:
            try:
                st = await get_unit_status(bus, path)
                pid_val = int(st.get("MainPID") or 0)
                state = st.get("ActiveState", "unknown")
                sub = st.get("SubState", "")
            except Exception:
                pass

        hint = f"ww logs {unit_name} -f"
        # Human-friendly output
        typer.echo(f"name: {unit_name}")
        typer.echo(f"pid: {pid_val}")
        if sub and sub != "running":
            typer.echo(f"state: {state} ({sub})")
        else:
            typer.echo(f"state: {state}")
        typer.echo(f"log: {hint}")
        # Machine-tail line if non-TTY
        if not is_tty():
            print(json_line({"name": unit_name, "pid": pid_val, "state": state, "log_hint": hint}))

    asyncio.run(_start())
