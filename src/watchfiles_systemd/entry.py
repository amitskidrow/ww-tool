import sys
from typing import List

from .cli import app, run as start_command
from . import cli as _cli


SUBCOMMANDS = {
    "ps",
    "pid",
    "status",
    "logs",
    "restart",
    "stop",
    "rm",
    "restart-all",
    "stop-all",
    "rm-all",
    "doctor",
    "dash",
    "run",
    "main",
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
                sys.argv = ["ww", "logs", unit] + rest
                return app()
            if action in {"follow", "f"}:
                sys.argv = ["ww", "logs", unit, "-f"] + rest
                return app()
            if action == "pid":
                sys.argv = ["ww", "pid", unit] + rest
                return app()
            if action == "restart":
                sys.argv = ["ww", "restart", unit] + rest
                return app()
            if action == "stop":
                sys.argv = ["ww", "stop", unit] + rest
                return app()
            if action == "rm":
                sys.argv = ["ww", "rm", unit] + rest
                return app()
            if action == "status":
                sys.argv = ["ww", "status", unit] + rest
                return app()

            # If only a unit was provided, default to showing logs
            if action is None:
                sys.argv = ["ww", "logs", unit] + rest
                return app()

            # Unknown action after a unit name; fall through to app() which will print help

    # Default command: ww <path>
    if argv and not argv[0].startswith("-") and argv[0] not in SUBCOMMANDS:
        # Call the start command directly (runs the same logic as 'ww <path>')
        return start_command(argv[0])

    # Otherwise, dispatch to Typer app (subcommands / flags)
    app()
