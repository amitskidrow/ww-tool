# ww — watchfiles + systemd (user)

Zero‑config background runner with live reload. Starts your Python target as a transient user service via systemd D‑Bus and wraps it with watchfiles for restarts on code changes.

- Start: `ww <path>` (file or directory)
- Logs: `ww logs <name> -n 100` or `ww logs <name> -f`
- List: `ww ps`
- PID: `ww pid <name>`
- Control: `ww restart|stop|rm <name>` or `ww restart-all|stop-all|rm-all`
- Doctor: `ww doctor`

Install via uvx (no global installs): `uvx --from <REPO_URL> ww --help`

Global install (preferred via uv):
- Install/upgrade: `uv tool install --force --from <REPO_URL> ww`
- Ensure `~/.local/bin` is on your `PATH` and run: `ww --version`

Alternative with pipx:
- Install/upgrade: `pipx install --force --spec git+<REPO_URL>@main ww`

Local dev with uv:
- Create env: `uv venv`
- Install: `uv pip install -e .`
- Run: `.venv/bin/ww --help`

See `prd.md` for detailed behavior and acceptance criteria.
