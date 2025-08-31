# ww — watchfiles + systemd (user)

Zero‑config background runner with live reload. Starts your Python target as a transient user service via systemd D‑Bus and wraps it with watchfiles for restarts on code changes.

- Start: `ww <path>` (file or directory)
- Logs: `ww logs <name> -n 100` or `ww logs <name> -f`
- List: `ww ps`
- PID: `ww pid <name>`
- Control: `ww restart|stop|rm <name>` or `ww restart-all|stop-all|rm-all`
- Doctor: `ww doctor`

Install via uvx (no global installs): `uvx --from <REPO_URL> ww --help`

See `prd.md` for detailed behavior and acceptance criteria.
