import sys
from typing import List

from .cli import app, main as start_command


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

    # Default command: ww <path>
    if argv and not argv[0].startswith("-") and argv[0] not in SUBCOMMANDS:
        # Call the start command directly (runs the same logic as 'ww <path>')
        return start_command(argv[0])

    # Otherwise, dispatch to Typer app (subcommands / flags)
    app()
