# WeDash

Minimal TUI to auto-discover microservices (dirs with both `.we.pid` and `Makefile`) and follow their logs by default.

Install (recommended):

- Using uv tool: `uv tool install --from git+https://github.com/amitskidrow/we-dash.git@migration/new-arch we-dash`
- Using pipx: `pipx install git+https://github.com/amitskidrow/we-dash.git@migration/new-arch`

Quick start (dev):

- Create venv: `uv venv && source .venv/bin/activate`
- Install: `uv pip install -e .`
- Run (minimal columns): `we-dash --root /path/to/repo`
- Run (full columns): `we-dash --columns full`
 - Select terminal backend: `we-dash --terminal-backend auto|native|tmux` (default auto)

Key bindings: F/Enter follow, U/D/R up/down/restart, J journal, L last logs, T terminal (toggle), Ctrl+C send SIGINT, Ctrl+L clear, Ctrl+R refresh, Q quit.

Header tabs filter by Active/Failed/All. Search matches name | unit | project (substring, case-insensitive).

Optional embedded terminal:
- Install extras: `uv pip install -e .[terminal]` (dev) or `pipx inject we-dash textual-terminal`
- Toggle in-app terminal with `T`. If the backend is missing, a placeholder shows instead.
- Multiple sessions: a tab per service appears when opened; switch within the terminal pane.
- Send SIGINT with Ctrl+C when the terminal pane is active.

Tmux backend (optional):
- Enable with `--terminal-backend tmux` (requires `tmux` and `libtmux`).
- Commands run in tmux panes per service; content is snapshotted in the UI.
- Recommended for resilience; native terminal is preferred for full interactivity.
