# ww — watchfiles + systemd (user)

Zero‑config background runner with live reload. Starts your Python target as a transient user service via systemd D‑Bus and wraps it with watchfiles for restarts on code changes.

- Start: `ww <path>` (file or directory)
- Logs: `ww logs <name> -n 100` or `ww logs <name> -f`
  - By default, shows logs since the last successful start; add `-a/--all` for full history.
- List: `ww ps`
- Status: `ww status <name|pid|unit>`
- PID: `ww pid <name|pid|unit>`
- Control: `ww restart|stop|rm <name|pid|unit>` or `ww restart-all|stop-all|rm-all`
- Doctor: `ww doctor`
- Dashboard: `ww dash [--columns full] [--root PATH ...]`

Install via uvx (no global installs): `uvx --from <REPO_URL> ww --help`

Global install (preferred via uv):
- Install/upgrade: `uv tool install --force --from <REPO_URL> ww`
- Ensure `~/.local/bin` is on your `PATH` and run: `ww --version`

Alternative with pipx:
- Install/upgrade: `pipx install --force --spec git+<REPO_URL>@main watchfiles-systemd`

Local dev with uv:
- Create env: `uv venv`
- Install: `uv pip install -e .`
- Run: `.venv/bin/ww --help`

See `prd.md` for detailed behavior and acceptance criteria.

## Test With test/test.py

- Start the example in the background: `ww test/test.py`
  - The command prints the unit name (for example `ww-test.service`), PID, and a log hint.
- Follow logs: use the printed hint, e.g. `ww logs ww-test.service -f`
- Verify live reload: edit `test/test.py` and save; the process restarts and logs continue incrementing.
- List running jobs: `ww ps`
  - Shows friendly name, PID, state, and the raw unit name. The friendly name hides the `ww-` prefix and `.service` suffix (e.g. `test`).
  - State shows `active`, `active(running)`, or `flapping` when auto‑restarting.
- Stop/remove when done: `ww rm ww-test.service` (or `ww rm-all` to clean everything)

Addressing services by name or PID:
- Commands accept a friendly name (from `ww ps`), a PID, or the full unit name.
- Examples: `ww stop 31244`, `ww logs test -f`, `ww status ww-test.service`.

Tip: if `ww` is not globally installed, you can run the same test without installing globally via `uvx`:
- `uvx --from <REPO_URL> ww test/test.py`
- Then follow logs as above.

Troubleshooting:
- `ww doctor` checks user D‑Bus, journald, uvx availability, and watchfiles via uvx.
- Ensure `PATH` and `HOME` are available to systemd user services. `ww` injects them automatically.
- Env vars:
  - `WW_UV_BIN`: absolute path or name of `uvx` to use.
  - `WW_WF_VERSION`: pin watchfiles version, e.g. `==0.22.0`.
  - `WW_IGNORE`: extra ignore paths (comma‑separated) merged with built‑ins.

## Dashboard (ww dash)

Open a Textual TUI listing all `ww-*` units for the current user. No project files are required; discovery uses systemd D‑Bus and journald.

- Open: `ww dash`
- Options:
  - `--columns minimal|full` (default minimal)
  - `--root PATH` (repeatable) to label “Project” by path prefix
  - `--terminal-backend auto|native|tmux` for an optional embedded terminal
- Actions: Enter/F follow, J journal, L last logs, U/D/R up/down/restart, `/` search, T toggle terminal.
- Dependencies: Dashboard is included by default (Textual installs with ww). Optional extras for embedded terminals: `uv tool install --from <REPO_URL> ww[dash-terminal]` and/or `ww[dash-tmux]` (or `pip install watchfiles-systemd[dash-terminal]` / `[dash-tmux]`).
