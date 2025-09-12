# PRD: Migrate we-dash to an Embedded, Multi-Session Terminal with Persistent State

## 0) Summary
We will add an **in-app terminal** to we-dash that supports:
- Running multiple concurrent shells (≥5) with **state preserved** while switching.
- Full control over process I/O (send keys, Ctrl-C, paste), **resize**, scrollback, and running ncurses tools.
- A minimal, robust baseline that can later upgrade to **tmux-backed persistence** without UI changes.

**Baseline (Phase 1)**: In-process terminal widget using a **VT emulation** layer and **PTY** backend.  
**Optional (Phase 2)**: Swap the backend to **tmux + libtmux** for resilience and multi-pane orchestration.

## 1) Context & Problem
- Today we tail logs / journal from processes but lack an **interactive terminal** inside we-dash.
- We need **low-level control**: programmatic input, explicit resize, per-service terminal sessions, durable state across tab switches, and the ability to run TUI apps (htop, vim, etc.) inside we-dash.
- The solution must fit our **Textual** layout (25% process list | 75% main panel) and keep complexity/tech-debt low.

## 2) Goals (Must-Haves)
1. Embed a **real terminal** in the right pane that supports ANSI/VT and ncurses apps.  
   → Use a **VTXXX-compatible emulator** (Pyte or equivalent) rendering inside Textual. :contentReference[oaicite:0]{index=0}
2. **Multiple terminals (≥5) alive concurrently**; switching must not kill processes.  
   → Use Textual’s **TabbedContent/ContentSwitcher** so only one is visible, others remain running. :contentReference[oaicite:1]{index=1}
3. **PTY-backed** processes (bash/login shell) with programmatic keystrokes, paste, SIGINT, and **resize** (TIOCSWINSZ). :contentReference[oaicite:2]{index=2}
4. Support **per-session CWD/ENV**, so each service terminal starts in its service directory with its own command.
5. **Performance**: hidden terminals continue reading their PTY (no back-pressure) but render throttled to reduce CPU.

## 3) Non-Goals (Now)
- Full web/remote terminal access.
- Multi-user sharing.
- Recording/replay beyond basic scrollback.

## 4) Approach Options

### Option A — In-Process Terminal (Baseline)
- **UI**: a terminal **widget** inside Textual; one widget per session; switch via Tabs. :contentReference[oaicite:3]{index=3}
- **Emulation**: **Pyte** (in-memory VTxxx emulator) for correct rendering of ANSI/VT and ncurses. :contentReference[oaicite:4]{index=4}
- **Backend**: **PTY** via `ptyprocess`/`pexpect` to spawn shells and handle interactive I/O properly. :contentReference[oaicite:5]{index=5}
- **Ready-made**: Prefer a maintained Textual terminal widget (**`textual-terminal`**) which already uses Pyte and integrates with Textual’s event loop. :contentReference[oaicite:6]{index=6}
- **Resize**: propagate Textual size → PTY using **TIOCSWINSZ** semantics (Python’s `pty` implements this). :contentReference[oaicite:7]{index=7}

**Pros**: Minimal deps, in-process simplicity, tight Textual integration.  
**Cons**: Pure-Python emulation can be CPU-heavy under very high throughput (mitigate via render throttling / batching).

### Option B — tmux Backend (Upgrade Path)
- **Engine**: launch one **tmux pane per session**, drive it via **`libtmux`** (send-keys, capture-pane, resize-pane). :contentReference[oaicite:8]{index=8}
- **UI**: keep the same right pane; we mirror the active pane’s content (snapshot/stream) and forward keys.
- **Pros**: Resilient to we-dash restarts, native scrollback, easy orchestration of many sessions.
- **Cons**: External dependency on tmux; small latency on capture/paint.

**Decision**: **Ship Option A in Phase 1**, keep **Option B as drop-in backend** if/when we need hard persistence or heavy parallel tails.

## 5) User Experience (UX)
- Left pane (25%): process list; selecting a row maps to a terminal session.
- Right pane (75%): **Tabs** (Term 1…Term 5) or a per-service tab. Only one terminal is visible; others remain live. :contentReference[oaicite:9]{index=9}
- Keybinds:
  - **Enter** = open/focus terminal for selected service.
  - **Ctrl-C** passthrough to active terminal (send SIGINT).
  - **R** = run service-specific command (`make follow`, `journalctl -f`, etc.) in active terminal.
  - **Tab / Shift-Tab** or `Alt+1…5` = switch terminal tabs instantly.
  - **Ctrl+L** = clear screen; **PgUp/PgDn** = scrollback (widget or tmux copy-mode in Phase 2).

## 6) Functional Requirements
1. Create/destroy terminals on demand; **store session state** (id, cwd, env, PTY handle, size, scrollback).
2. **Switch** terminals in O(1) by flipping the visible Tab/ContentSwitcher child; **do not kill** hidden sessions. :contentReference[oaicite:10]{index=10}
3. Handle **window resize**: recalc rows/cols and apply to PTY (**TIOCSWINSZ**). :contentReference[oaicite:11]{index=11}
4. **Input API**: send bytes/keys (including Ctrl/Meta combos), paste (bracketed if supported).
5. **Output pipeline**: non-blocking reads; throttle paints when hidden to avoid CPU spikes.
6. **Crash safety**: if the child exits, surface status in the tab and allow quick restart.

## 7) Architecture & Data Model

### 7.1 Components
- **TerminalManager**: owns sessions; API: `create`, `focus`, `resize`, `send`, `kill`, `snapshot`.
- **TerminalSession**: `{ id, cwd, env, pty, rows, cols, status, ring_buffer }`.
- **TerminalView**: Textual widget wrapper; binds to a session id and renders either the widget’s framebuffer (Option A) or a tmux snapshot (Option B).

### 7.2 Backend Details
- **Option A (In-Process)**  
  - **Widget**: `textual-terminal` (PyPI). It uses **Pyte** VT emulation under the hood to display a shell inside Textual. :contentReference[oaicite:12]{index=12}  
  - **PTY**: spawn via **`ptyprocess`**/**`pexpect`** to guarantee interactive behavior for ncurses apps (not just pipes). :contentReference[oaicite:13]{index=13}  
  - **Textual plumbing**: use **TabbedContent** / **ContentSwitcher** for fast switches; use **reactive state & workers** for I/O off the UI thread. :contentReference[oaicite:14]{index=14}

- **Option B (tmux)**  
  - **Control**: **`libtmux`** to create/find sessions, split windows, **send-keys**, **capture-pane**, **resize-pane**. :contentReference[oaicite:15]{index=15}  
  - **Semantics**: tmux panes manage active processes; **send-keys** injects input; **capture-pane** returns scrollback; **resize-pane** adjusts terminal size. :contentReference[oaicite:16]{index=16}

### 7.3 Resize Semantics
- On Textual `on_resize`, compute rows/cols → apply to:  
  - **PTY** using TIOCSWINSZ (Python `pty` and ptyprocess honor this), or  
  - **tmux** via `resize-pane`. :contentReference[oaicite:17]{index=17}

### 7.4 Switching Among 5 Terminals
- Maintain an LRU of focused session ids.
- Switching = update `active_session_id` and show its widget/pane.
- Hidden sessions continue reading from PTY; **render throttled** (e.g., coalesce paints to ~20–50 ms).

## 8) Implementation Plan

### Phase 1 — In-Process Terminal (Ship)
1. **Add dependency**: `textual-terminal` (and `pyte`). :contentReference[oaicite:18]{index=18}
2. **Integrate widget**: Replace right-pane log view with a Terminal widget; create **5 pre-allocated sessions** or create on demand.
3. **Session lifecycle**: `create` on first open; keep PTY alive across tab switches; `kill` only on explicit close.
4. **Per-service command**: by default run `bash -lc 'make follow || journalctl -f --user-unit <unit>'`.
5. **Input**: pass we-dash keybinds to terminal (Ctrl-C, etc.).
6. **Resize**: wire Textual resize → terminal widget/PTY (TIOCSWINSZ). :contentReference[oaicite:19]{index=19}
7. **Perf**: throttle paints for hidden sessions; batch large writes.

**Exit Criteria (Phase 1)**
- Run ≥5 terminals concurrently; switch among them with zero process restarts.
- ncurses apps work (e.g., `htop`, `vim`) inside the widget.
- Resize doesn’t break layout; terminal contents adapt immediately.

### Phase 2 — Optional tmux Backend (Persistence & Scale)
1. **Add deps**: `tmux` (system), `libtmux` (Python). :contentReference[oaicite:20]{index=20}
2. **Backer**: Implement a `TmuxBacker` that ensures `{session, window, pane}` per we-dash terminal, with APIs: `ensure(cwd, cmd)`, `send(keys)`, `capture(last=N)`, `resize(rows, cols)`.
3. **UI unchanged**: the right pane now **mirrors** active pane content via `capture-pane`; inputs go via `send-keys`. :contentReference[oaicite:21]{index=21}
4. **Persistence**: Verify terminals survive we-dash restarts; confirm scrollback and copy-mode work.

**Exit Criteria (Phase 2)**
- Killing/restarting we-dash preserves terminals and scrollback.
- Switching among ≥8 terminals remains instant and stable.

## 9) Dependencies
- **Textual** framework and widgets. :contentReference[oaicite:22]{index=22}
- **TabbedContent / ContentSwitcher** for visibility control. :contentReference[oaicite:23]{index=23}
- **textual-terminal** + **Pyte** (Phase 1). :contentReference[oaicite:24]{index=24}
- **ptyprocess / pexpect** (if we need manual PTY mgmt). :contentReference[oaicite:25]{index=25}
- **tmux + libtmux** (Phase 2). :contentReference[oaicite:26]{index=26}

## 10) Observability & Telemetry
- Per-session metrics: bytes/sec read, paint/sec, render queue depth, dropped frames.
- Warnings on back-pressure (pty read backlog), paint starvation.
- Debug commands: “snapshot active terminal”, “dump ring buffer”.

## 11) Security & Sandbox
- Never echo secrets to logs; treat terminal output as sensitive.
- Optionally mask known patterns in the paint path (tokens, keys).
- Respect user umask; do not run elevated shells.

## 12) Testing Strategy
- **Unit**: session lifecycle (create/focus/resize/kill), key injection, exit codes.
- **Integration**: run `htop`, `vim`, `less -S`, wide UTF-8, fast-scroll logs; verify no crashes/flicker.
- **Resize**: rapid window drags; assert columns/rows take effect (TIOCSWINSZ). :contentReference[oaicite:27]{index=27}
- **Load**: tail 3 high-throughput logs + 2 interactive shells; ensure CPU remains within target.
- **Phase 2**: kill we-dash while terminals run; relaunch and reattach; verify state intact via tmux. :contentReference[oaicite:28]{index=28}

## 13) Rollout Plan
1. **Feature flag** `terminal.enabled=true` (default on for dev).
2. **Dev** → **Staging**: validate 5 sessions, throughput, ncurses apps.
3. **Docs**: “How to use in-app terminal” and “Upgrade to tmux backend”.
4. **Post-ship**: monitor metrics, collect feedback; decide on Phase 2 enablement.

## 14) Risks & Mitigations
- **Perf spikes** under heavy output (pure Python emulation) → throttle paints, coalesce, consider Phase 2 tmux.  
- **Resize glitches** → comprehensive tests; ensure TIOCSWINSZ wired correctly. :contentReference[oaicite:29]{index=29}
- **Key passthrough conflicts** → reserve specific chords for the terminal when focused; document overrides.
- **External dep (tmux)** in Phase 2 → check version; gate with feature flag. :contentReference[oaicite:30]{index=30}

## 15) Acceptance Criteria (Go/No-Go)
- [ ] Five terminals live concurrently; switching is instant; sessions persist across tab changes.
- [ ] Running `htop` and `vim` works correctly in the embedded terminal.
- [ ] Resize is applied immediately; no content corruption.
- [ ] Keybinds (Ctrl-C, paste, Enter, R, Tab next/prev) operate as specified.
- [ ] CPU remains acceptable during a 2-minute sustained `tail -F` at 10k lines/min across 3 sessions.

---

## Appendix: Reference Links
- **Textual** overview & widgets (TabbedContent, ContentSwitcher). :contentReference[oaicite:31]{index=31}
- **textual-terminal** (terminal widget for Textual, uses Pyte). :contentReference[oaicite:32]{index=32}
- **Pyte** (VTxxx emulator) docs. :contentReference[oaicite:33]{index=33}
- **PTY** in Python (`pty`, window size/resize). :contentReference[oaicite:34]{index=34}
- **ptyprocess / pexpect** for interactive PTY spawn/control. :contentReference[oaicite:35]{index=35}
- **tmux** basics; **libtmux** control and quickstart. :contentReference[oaicite:36]{index=36}
