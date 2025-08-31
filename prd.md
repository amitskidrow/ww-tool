# PRD — `ww`: Zero-config background runner with live reload (Combo A)

## 1) Purpose & scope

Build a **universal Linux** CLI that starts any Python target in the background as a **systemd user** transient service, with **zero per-project configuration**, **recursive live reload**, and **journald** logging. The tool must work cleanly for humans and for LLM/agentic CLIs. Key foundations: systemd D-Bus `StartTransientUnit` for process lifecycle, `watchfiles` for reload, `journalctl --user` for logs, and `uvx` for tool invocation without global installs. ([Freedesktop][1], [watchfiles.helpmanual.io][2], [Man7][3], [Astral Docs][4])

---

## 2) Users

* **Primary:** Developers and agentic CLIs that need deterministic PID truth, backgrounding past logout, live reload, and historical + live logs with minimal ceremony.
* **Environment:** Linux distros with systemd user sessions (e.g., Arch). Persistent user journals recommended for `journalctl --user`. ([ArchWiki][5], [Freedesktop][6])

---

## 2.5) Installation (uvx or pipx via Git)

- Preferred runners are `uvx` (no global install; runs tools from a Git repo) or `pipx` (global install from Git).
- Reference: see `watchexec-systemd/commands.md` for the overall pattern; here we standardize on uvx/pipx and Git-based installs.

Quick options (replace `<REPO_URL>` with the Git URL for this project’s repo):

- uvx (no global install):
  - `uvx --from <REPO_URL> ww --help`
  - `uvx --from <REPO_URL> ww --version`

- pipx (global):
  - Install: `pipx install git+<REPO_URL>`
  - Upgrade: `pipx upgrade git+<REPO_URL>`
  - Run: `ww --help`

Notes:
- `uvx` is the `uv` tool runner (isolated, ephemeral environments). It’s ideal for CI, agents, or trying the tool without polluting the system.
- `pipx` installs a stable, global `ww` entrypoint into `~/.local/bin`.
- The service runtime continues to use `uvx` to run `watchfiles` inside the transient unit, so end-users do not need to manage Python environments for reload behavior.

---

## 3) Product goals

1. **One command, one arg:** `ww <path>` where `<path>` is either a file or a directory.
2. **No config files, no unit files on disk:** Always use **transient** user units.
3. **Live reload by default:** Wrap the user command with **watchfiles**; recursive when `<path>` is a directory; single-file when `<path>` is a file. CLI executes `watchfiles` via **uvx** so users don’t manage environments. ([watchfiles.helpmanual.io][2], [Astral Docs][4])
4. **Full observability:** Unit-scoped journald logs (history + follow) and immediate PID truth via D-Bus. ([Man7][7])
5. **Headless longevity:** Offer one-liner to enable *linger* so user units survive logout. ([ArchWiki][5])

---

## 4) Non-goals (v1)

* No `.path` units, timers, sockets, watchdog matrices, or hardening presets by default.
* No support for non-systemd init systems.
* No per-project YAML/INI files.

---

## 5) CLI design (Combo A)

### 5.1 Commands (final surface)

* `ww <path>` — Start background job.

  * If `<path>` is a **file**: run `python <file>` with **file-scoped** reload.
  * If `<path>` is a **directory** (e.g., `.`): infer an entrypoint and run with **recursive** reload.
  * On success, print: **unit name**, **MainPID**, short **log hint**.
* `ww ps` — List managed units with `Name`, `ActiveState`, `MainPID`.
* `ww pid <name>` — Print `Service.MainPID`.
* `ww logs <name> [-n N] [-f]` — Show history / follow via journald.
* `ww restart <name>` · `ww stop <name>` · `ww rm <name>` — Control one job.
* `ww restart-all` · `ww stop-all` · `ww rm-all` — Bulk actions across `ww-*`.
* `ww doctor` — Diagnose user D-Bus reachability, journald availability, and whether **linger** is needed; print the fix when applicable. ([Man7][3], [ArchWiki][5])

### 5.2 Argument/flag policy

* **No flags** needed for normal use.
* Future (optional) env-switches (not v1 flags):

  * `WW_NAME` (override unit slug), `WW_IGNORE` (additional ignore globs), `WW_WF_VERSION` (pin `watchfiles` version).
* Output auto-adapts: if stdout is non-TTY, append a one-line JSON summary (`name`, `pid`, `state`, `log_hint`) for machine callers.

---

## 6) Behavior & defaults

### 6.1 Path mode detection

* **File mode:** If `<path>` is a regular file, run `python <file>`; watch **only that file** (restart on close-after-write).
* **Directory mode:** If `<path>` is a directory, pick the first match:

  1. `<dir>/__main__.py` → `python -m <dir_basename>`
  2. `<dir>/main.py` → `python main.py`
  3. `<dir>/app.py` → `python app.py`
     Else: fail fast with clear suggestions (use a specific file; or add `__main__.py`).

### 6.2 Live reload engine

* `ExecStart` wraps the chosen command with **watchfiles** in **restart** mode:

  * File: `watchfiles --restart --filter python -- python <file>`
  * Dir:  `watchfiles --restart --filter python -- <resolved command>`
* `watchfiles` is executed via **`uvx`** so no global install is required and it runs in an isolated temp venv. The `uvx` alias maps to `uv tool run`. ([watchfiles.helpmanual.io][2], [Astral Docs][4])

### 6.3 Systemd unit (transient, user)

* Created with D-Bus **`StartTransientUnit`**. Minimal properties:

  * `Description="ww:<name>"`, `WorkingDirectory=<root>`, `Environment=[…]`
  * `ExecStart` as D-Bus signature **`a(sasb)`** (path, argv\[], ignore\_failure).
  * `Restart="on-failure"`, `RestartSec="3s"`, `StandardOutput="journal"`, `StandardError="journal"`.
    The `ExecStart` signature requirement is a key gotcha; it must be structured, not a single string. ([Gist][8], [Stack Overflow][9])

### 6.4 Logs

* All stdout/stderr goes to **journald** and is retrievable with `journalctl --user -u <unit> [-n/-f]`.
* `USER_UNIT=`/`UNIT=` journal fields scope queries to a unit.
* Note: **per-user journal** visibility may depend on persistent journal storage settings. Document the knob. ([Man7][3], [Freedesktop][6])

### 6.5 Naming & collisions

* Default unit name: `ww-<slug>` derived from file or folder basename. If taken, suffix with `-2`, `-3`, …

### 6.6 Headless longevity

* If the user requests “keep running past logout”, print one-time guidance to enable **linger**:
  `loginctl enable-linger $USER` (with link to docs). ([ArchWiki][5])

### 6.7 Ignores & scale

* Built-in ignores for dir mode: `.git/`, `__pycache__/`, `.venv/`, `env/`, `.tox/`, `.pytest_cache/`, `.mypy_cache/`, `node_modules/`, `dist/`, `build/`, `.idea/`, `.vscode/`.
* If kernel watch limits are exceeded (very large trees), detect the error and print a one-liner to raise inotify limits. (Both `watchfiles` and other watchers rely on kernel notifications.) ([watchfiles.helpmanual.io][10])

---

## 7) System architecture

### 7.1 Process model

* **One unit per app**. `systemd` supervises the **watchfiles** wrapper; **watchfiles** supervises the target command. If the app crashes, systemd restarts it (backoff via `RestartSec`); if files change, **watchfiles** restarts the child. ([watchfiles.helpmanual.io][2])

### 7.2 D-Bus operations

* Start: `StartTransientUnit(name, mode="fail", properties=[…])`.
* Inspect: `GetUnit` → `org.freedesktop.systemd1.Unit`; then `org.freedesktop.systemd1.Service` → `MainPID`, `ExecMainStatus`, `ActiveState`.
* List: `ListUnits()` → filter `ww-*`.
* Control: `StopUnit`, `StartUnit`, `RestartUnit`, `ResetFailed`.
* Subscribe: listen to `PropertiesChanged` for liveness/state updates. (All via systemd D-Bus API.) ([Freedesktop][1])

---

## 8) UX & output

### 8.1 Success start (TTY)

* Show **unit**, **MainPID**, **state=active**, and **how to see logs**:

  * e.g., `ww logs ww-api -f` (follows live logs), `ww logs ww-api -n 200` (tail). ([Man7][3])

### 8.2 Success start (non-TTY / machine)

* Print a final JSON line: `{"name":"ww-api","pid":12345,"state":"active","log_hint":"ww logs ww-api -f"}`.

### 8.3 Failure modes

* **No user D-Bus / no user manager:** fail fast with an explanation and link to requirements.
* **No directory entrypoint found:** show two concrete fixes (choose a file, or add `__main__.py`).
* **Journald not persistent / `--user` not available:** print a note and link to `journald.conf(5)` storage setting. ([Freedesktop][6])
* **Watch limit exceeded:** print remediation hint.

---

## 9) Performance & reliability

* Minimal overhead: two processes (systemd-supervised wrapper + app).
* Restart policy: `Restart=on-failure` at systemd layer; **watchfiles** handles code change restarts.
* Journald provides indexed, durable logs with robust `-f` follow. ([Man7][3])

---

## 10) Security & isolation

* Defaults: `Type=simple`, `KillMode=control-group`, TERM→KILL sequence handled by systemd.
* No sandboxing in v1 (keep frictionless). Document that users can wrap their command with their own virtualenvs/containers if needed. ([Freedesktop][1])

---

## 11) Telemetry (optional, off by default)

* A single **opt-in** counter for starts/stops (no file paths, no command bodies). Respect `NO_COLOR`/`WW_NO_TELEMETRY`.

---

## 12) Acceptance criteria (must-pass)

1. **Start & PID truth**
   `ww main.py` prints unit + `MainPID`; `ww pid <name>` returns a live PID; `ww ps` shows `ActiveState=active`. (D-Bus `Service.MainPID`.) ([Freedesktop][1])

2. **Zero-config live reload (file)**
   Edit `main.py`; process restarts automatically; logs show a clean stop/start sequence. (Reload behavior via `watchfiles` CLI.) ([watchfiles.helpmanual.io][2])

3. **Zero-config live reload (directory)**
   `ww .` in a package dir with `__main__.py`; any `.py` change triggers restart; ignores apply. ([watchfiles.helpmanual.io][2])

4. **Logging**
   `ww logs <name> -n 100` returns historical logs; `-f` follows; unit-scoped via `--user -u`. `USER_UNIT`/`UNIT` fields exist. ([Man7][3])

5. **Bulk orchestration**
   Run two jobs, then `ww restart-all` restarts both; `ww rm-all` stops and deletes both transient units; `ww ps` shows none.

6. **Headless longevity**
   After `loginctl enable-linger $USER`, a job started with `ww` continues running post-logout/login. Provide the exact command if not enabled. ([ArchWiki][5])

7. **No global installs required**
   `watchfiles` is executed via `uvx` and works on a host with no prior Python env setup. `uvx` is documented alias for `uv tool run`. ([Astral Docs][4])

---

## 13) Implementation notes (dev handoff)

* **D-Bus client:** Any language is fine; for Python, `dbus-next` is suitable. Ensure `ExecStart` is encoded as **`a(sasb)`** (array of `(string path, array argv, bool ignore_failure)`). Many libraries trip on this—follow examples. ([Stack Overflow][9])
* **Entry point resolver:**

  * File: pass exactly as given.
  * Dir: probe `__main__.py` → `main.py` → `app.py`; choose first match; else error with suggestions.
* **`ExecStart` construction:** use `/usr/bin/env` to locate `uvx`, then run `watchfiles` with `--restart --filter python -- …`.
* **Journal integration:** shell to `journalctl --user -u <unit>`; support `-n` and `-f`. If storage is volatile, print note and point to `journald.conf` `Storage=`. ([Freedesktop][6])
* **Doctor:**

  * Check user bus: attempt to introspect `org.freedesktop.systemd1`.
  * Check `journalctl --user` availability.
  * Check linger status; if off, print `loginctl enable-linger $USER` + doc link. ([ArchWiki][5])

---

## 14) Risks & mitigations

* **Per-user journal unavailable:** Provide clear guidance to enable persistent storage or run as rootless user with appropriate config. ([Freedesktop][6])
* **Incorrect `ExecStart` shape:** Include unit tests that assert D-Bus marshaling for `a(sasb)`; link an example. ([Stack Overflow][9])
* **Heuristic mis-detects dir entrypoint:** Keep the error message actionable and short-circuit to file mode when specified explicitly.
* **Linger assumptions:** Document that “linger keeps user manager alive” and provide the canonical `loginctl` command + Arch guidance. ([ArchWiki][5])

---

## 15) Rollout & docs

* A single README page with: quick start (`ww <file>`, `ww .`), logs, ps/pid, bulk ops, linger note, and troubleshooting (watch limits, journald storage). Link to upstream docs for `watchfiles`, `journalctl`, `uvx`, and systemd D-Bus. ([watchfiles.helpmanual.io][2], [Man7][3], [Astral Docs][4], [Freedesktop][1])

---

## 16) Deploy workflow

- A `deploy.sh` script (mirrors the one in `watchexec-systemd`) will:
  - Optionally bump patch version in `pyproject.toml` if present.
  - Commit and push to `main`.
  - Verify remote install using `uvx --from <origin_url> ww --version`.
  - Optionally verify `pipx` global install if `pipx` is available.
- This keeps release steps consistent across both repos while using Git-based distribution for installs.

---

### Key references (primary)

* **Systemd service / D-Bus / Exec semantics (incl. `a(sasb)`)**. ([Freedesktop][1], [Stack Overflow][9])
* **Journald / journalctl usage & journal fields**. ([Man7][3])
* **User services & lingering** (keep jobs alive across logout). ([ArchWiki][5])
* **watchfiles CLI (restart a process on changes)**. ([watchfiles.helpmanual.io][2])
* **UV `uvx` tool runner (no-install execution)**. ([Astral Docs][4])

If you want, I can now draft the exact `StartTransientUnit` property map and the two `ExecStart` argv vectors (file vs dir) in the required `a(sasb)` shape for immediate implementation.

[1]: https://www.freedesktop.org/software/systemd/man/systemd.service.html?utm_source=chatgpt.com "systemd.service"
[2]: https://watchfiles.helpmanual.io/cli/?utm_source=chatgpt.com "CLI - watchfiles - helpmanual.io"
[3]: https://man7.org/linux/man-pages/man8/systemd-journald.service.8.html?utm_source=chatgpt.com "systemd-journald.service(8) - Linux manual page"
[4]: https://docs.astral.sh/uv/concepts/tools/?utm_source=chatgpt.com "Tools | uv - Astral Docs"
[5]: https://wiki.archlinux.org/title/Systemd/User?utm_source=chatgpt.com "systemd/User - ArchWiki - Arch Linux"
[6]: https://www.freedesktop.org/software/systemd/man/journald.conf.html?utm_source=chatgpt.com "journald.conf"
[7]: https://man7.org/linux/man-pages/man7/systemd.journal-fields.7.html?utm_source=chatgpt.com "systemd.journal-fields(7) - Linux manual page"
[8]: https://gist.github.com/daharon/c088b3ede0d72fd20ac400b3060cca2d?utm_source=chatgpt.com "Calling systemd's StartTransientUnit via DBus"
[9]: https://stackoverflow.com/questions/59963333/howto-create-systemd-transient-timer-and-service-via-python-and-dbus-systemd-ru?utm_source=chatgpt.com "Howto create systemd transient timer and service via ..."
[10]: https://watchfiles.helpmanual.io/?utm_source=chatgpt.com "watchfiles"
