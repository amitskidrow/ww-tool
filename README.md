# ww — watchfiles + systemd (user)

Zero‑config background runner with live reload. Starts your Python target as a transient user service via systemd D‑Bus and wraps it with watchfiles for restarts on code changes.

- Start: `ww <path>` (file or directory)
- Logs: `ww logs <name> -n 100` or `ww logs <name> -f`
- List: `ww ps`
- Status: `ww status <name>`
- PID: `ww pid <name>`
- Control: `ww restart|stop|rm <name>` or `ww restart-all|stop-all|rm-all`
- Doctor: `ww doctor`

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
- Stop/remove when done: `ww rm ww-test.service` (or `ww rm-all` to clean everything)

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
