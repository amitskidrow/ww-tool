import sys
from typing import List

from .cli import app, main as start_command
from . import cli as _cli


SUBCOMMANDS = {
    "ps",
    "pid",
    "logs",
    "restart",
    "stop",
    "rm",
    "restart-all",
    "stop-all",
    "rm-all",
    "doctor",
    "version",
    "--version",
    "-V",
    "-h",
    "--help",
}


def main(argv: List[str] | None = None):
    if argv is None:
        argv = sys.argv[1:]

    # Handle version early to avoid Click group error
    if argv and argv[0] in {"--version", "-V"}:
        from . import __version__
        print(__version__)
        return

    # Shorthand: allow "ww <unit> <action>" (unit-first)
    # Examples:
    #   ww ww-foo.service logs
    #   ww ww-foo.service follow
    #   ww ww-foo.service pid|restart|stop|rm
    if argv:
        first = argv[0]
        is_unit_like = first.startswith("ww-") or first.endswith(".service")
        if is_unit_like:
            unit = first
            action = argv[1] if len(argv) > 1 else None
            rest = argv[2:] if len(argv) > 2 else []

            # Map common actions; "follow" is a friendly alias for logs -f
            if action in {"logs", "log"}:
                return _cli.logs(unit)  # type: ignore[arg-type]
            if action in {"follow", "f"}:
                return _cli.logs(unit, follow=True)  # type: ignore[arg-type]
            if action == "pid":
                return _cli.pid(unit)  # type: ignore[arg-type]
            if action == "restart":
                return _cli.restart(unit)  # type: ignore[arg-type]
            if action == "stop":
                return _cli.stop(unit)  # type: ignore[arg-type]
            if action == "rm":
                return _cli.rm(unit)  # type: ignore[arg-type]

            # If only a unit was provided, default to showing logs
            if action is None:
                return _cli.logs(unit)

            # Unknown action after a unit name; fall through to app() which will print help

    # Default command: ww <path>
    if argv and not argv[0].startswith("-") and argv[0] not in SUBCOMMANDS:
        # Call the start command directly (runs the same logic as 'ww <path>')
        return start_command(argv[0])

    # Otherwise, dispatch to Typer app (subcommands / flags)
    app()
