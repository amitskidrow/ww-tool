from __future__ import annotations

import argparse
import asyncio
from asyncio import Task
from contextlib import suppress
from pathlib import Path
from typing import Iterable

from textual import on
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Container, Horizontal
from textual.widgets import DataTable, Footer, Input, Tabs, Tab, RichLog, Label, ContentSwitcher
from textual.timer import Timer

from .discovery_ww import discover_services_ww
from .models import AppState, Service
from .commands_ww import (
    follow_argv,
    last_logs_argv,
    up_argv,
    down_argv,
    restart_sequence,
    run_command,
    probe_status,
)
from .terminals import TerminalRegistry, terminal_supported
from .tmux_support import TmuxSession  # type: ignore


class WWDashApp(App):
    CSS_PATH = Path(__file__).with_name("app.tcss")
    BINDINGS = [
        Binding("enter", "do_follow", "Follow"),
        Binding("f", "do_follow", "Follow"),
        Binding("u", "do_up", "Up"),
        Binding("d", "do_down", "Down"),
        Binding("r", "do_restart", "Restart"),
        Binding("j", "do_journal", "Journal"),
        Binding("l", "do_last", "Last logs"),
        Binding("/", "focus_search", "Search"),
        Binding("t", "focus_terminal", "Terminal"),
        Binding("tab", "term_next", "Next Tab"),
        Binding("shift+tab", "term_prev", "Prev Tab"),
        Binding("ctrl+c", "term_sigint", "SIGINT"),
        Binding("ctrl+l", "term_clear", "Clear"),
        Binding("ctrl+r", "do_refresh", "Refresh"),
        Binding("q", "quit", "Quit"),
    ]

    def __init__(self, state: AppState, last: int = 200, columns: str = "minimal", terminal_backend: str = "auto") -> None:
        super().__init__()
        self.state = state
        self.last = last
        self.columns_mode = columns
        self.terminal_backend = terminal_backend
        self.table: DataTable | None = None
        # Avoid clashing with Textual App.log (read-only property)
        self.log_widget: RichLog | None = None
        self.term_container: Container | None = None
        self._terminals = TerminalRegistry(backend=self.terminal_backend)  # type: ignore[arg-type]
        self._show_terminal: bool = False
        self._term_tabs: dict[str, Tab] = {}
        self._rows: list[int] = []  # maps row index -> service index
        self._follow_task: Task | None = None
        self._status_task: Task | None = None
        self._search_timer: Timer | None = None
        self._follow_current: tuple[str | None, bool] = (None, False)  # (unit, journal?)
        self._tmux_refresh_timer: Timer | None = None
        self._tmux_refresh_key: str | None = None

    def compose(self) -> ComposeResult:
        with Container(id="header"):
            with Horizontal():
                yield Label("WW Dash", id="title")
                yield Tabs(
                    Tab("All", id="tab-all"),
                    Tab("Active", id="tab-active"),
                    Tab("Failed", id="tab-failed"),
                    id="tabs",
                    active="tab-all",
                )
                yield Input(placeholder="Search name|unit|project", id="search")

        with Container(id="content-left"):
            self.table = DataTable(zebra_stripes=True, cursor_type="row")
            if self.columns_mode == "full":
                self.table.add_columns("Status", "Service", "PID", "Unit", "Project", "Updated")
            else:
                self.table.add_columns("Status", "Service", "PID")
            yield self.table

        with Container(id="content-right"):
            # Terminal pane: tabs + content switcher (hidden by default)
            self.term_container = Container(id="term-container")
            if not terminal_supported():
                self.term_container.display = False
            with self.term_container:
                yield Tabs(id="term-tabs")
                yield ContentSwitcher(initial=None, id="term-switcher")

            # Log view (default)
            self.log_widget = RichLog(highlight=False, markup=False, wrap=False)
            self.log_widget.write("WW Dash — select a service to follow logs…")
            yield self.log_widget

        yield Footer(id="footer")

    async def on_mount(self) -> None:
        # Populate table
        self._rebuild_table(select_same=False)
        if self.state.services:
            self._select_row(0)
            await self._start_follow(self.state.services[0])
        # Periodic status refresher
        self._status_task = asyncio.create_task(self._periodic_status_refresh())

    async def on_unmount(self) -> None:
        if self._follow_task and not self._follow_task.done():
            self._follow_task.cancel()
            with suppress(Exception):
                await self._follow_task
        if self._status_task and not self._status_task.done():
            self._status_task.cancel()
            with suppress(Exception):
                await self._status_task

    def _rebuild_table(self, select_same: bool = True) -> None:
        assert self.table
        cur_idx = self.state.selected_index
        self.table.clear(columns=False)
        self._rows = []
        for idx in self._visible_indices():
            svc = self.state.services[idx]
            self._add_row(idx, svc)
            self._rows.append(idx)
        # try keep selection
        if select_same and self._rows:
            try:
                row = self._rows.index(cur_idx)
            except ValueError:
                row = 0
            self._select_row(row)

    def _select_row(self, row_index: int) -> None:
        assert self.table
        if 0 <= row_index < len(self._rows):
            self.table.cursor_coordinate = (row_index, 0)
            self.state.selected_index = self._rows[row_index]

    def _selected_service(self) -> Service | None:
        if not self.table:
            return None
        row = self.table.cursor_row
        if row is None:
            return None
        if 0 <= row < len(self._rows):
            svc_idx = self._rows[row]
            return self.state.services[svc_idx]
        return None

    async def action_do_follow(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        if self._show_terminal:
            self._ensure_terminal_for_service(svc, activate=True)
            sess = self._terminals.get_or_create(svc.unit, cwd=svc.dir)
            argv = follow_argv(svc)
            if not sess.run_argv(argv, cwd=svc.dir):
                await self._start_follow(svc)
        else:
            await self._start_follow(svc)

    @on(DataTable.RowHighlighted)
    async def _on_row_highlighted(self, event: DataTable.RowHighlighted) -> None:
        # Update selected index
        row = getattr(event, "row_index", None)
        if row is None:
            row = getattr(event, "cursor_row", None)
        if row is None and self.table is not None:
            row = self.table.cursor_row
        if row is None:
            return
        if not (0 <= row < len(self._rows)):
            return
        idx = self._rows[row]
        self.state.selected_index = idx
        # Probe and update status lazily
        if 0 <= idx < len(self.state.services):
            svc = self.state.services[idx]
            active, pid = await probe_status(svc)
            if active:
                svc.active = active
                if pid is not None:
                    svc.pid = pid
            # Update table row
            self._update_row_by_row(row, svc)
            # Auto-follow when moving selection
            await self._start_follow(svc)
            # If terminal view is active, switch to this service's session
            if self._show_terminal:
                self._ensure_terminal_for_service(svc, activate=True)
                try:
                    self._maybe_enable_tmux_refresh(svc.unit)
                except Exception:
                    pass

    def _add_row(self, idx: int, svc: Service) -> None:
        assert self.table
        status = svc.active or "?"
        if self.columns_mode == "full":
            self.table.add_row(status, svc.name, str(svc.pid), svc.unit, svc.project or "-", self._format_updated(svc))
        else:
            self.table.add_row(status, svc.name, str(svc.pid))

    def _update_row_by_row(self, row: int, svc: Service) -> None:
        assert self.table
        status = svc.active or "?"
        self.table.update_cell_at((row, 0), status)
        self.table.update_cell_at((row, 1), svc.name)
        self.table.update_cell_at((row, 2), str(svc.pid))
        if self.columns_mode == "full":
            self.table.update_cell_at((row, 3), svc.unit)
            self.table.update_cell_at((row, 4), svc.project or "-")
            self.table.update_cell_at((row, 5), self._format_updated(svc))

    async def action_do_last(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        argv = last_logs_argv(svc, last=self.last)
        await self._run_one_shot(argv, svc)

    async def action_do_journal(self) -> None:
        svc = self._selected_service()
        if svc:
            await self._start_follow(svc, force_journal=True)

    async def action_do_up(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        await self._run_one_shot(up_argv(svc), svc)

    async def action_do_down(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        await self._run_one_shot(down_argv(svc), svc)

    async def action_do_restart(self) -> None:
        svc = self._selected_service()
        if not svc:
            return
        seq = await restart_sequence(svc)
        if not seq:
            self._toast("Restart not supported")
            return
        for argv in seq:
            rc = await self._run_one_shot(argv, svc)
            if rc != 0:
                break

    async def action_focus_search(self) -> None:
        try:
            search = self.query_one('#search', Input)
            search.focus()
            try:
                search.action_select_all()  # type: ignore[attr-defined]
            except Exception:
                pass
        except Exception:
            self._toast("Search input not available")

    async def action_focus_terminal(self) -> None:
        if not self.term_container:
            return
        svc = self._selected_service()
        if not svc:
            return
        if not self._show_terminal:
            self._ensure_terminal_for_service(svc, activate=True)
            self.term_container.display = True
            if self.log_widget:
                self.log_widget.display = False
            self._show_terminal = True
            try:
                self._maybe_enable_tmux_refresh(svc.unit)
            except Exception:
                pass
        else:
            self.term_container.display = False
            if self.log_widget:
                self.log_widget.display = True
            self._show_terminal = False
            self._stop_tmux_refresh()

    async def action_do_refresh(self) -> None:
        # Re-discover services and refresh table
        self.state.services = await discover_services_ww(self.state.roots)
        self._rebuild_table(select_same=True)
        if self.state.services and not self._rows:
            self._select_row(0)
        # When terminal view is active, rebind the active session to the new selection
        if self._show_terminal:
            svc = self._selected_service()
            if svc:
                self._ensure_terminal_for_service(svc, activate=True)
                try:
                    self._maybe_enable_tmux_refresh(svc.unit)
                except Exception:
                    pass

    async def action_term_sigint(self) -> None:
        if not self._show_terminal:
            return
        svc = self._selected_service()
        if not svc:
            return
        sess = self._terminals.get_or_create(svc.unit, cwd=svc.dir)
        try:
            send = getattr(sess, "_send", None)
            if callable(send):
                send("\x03")  # Ctrl-C
        except Exception:
            pass

    async def action_term_clear(self) -> None:
        if not self._show_terminal:
            return
        svc = self._selected_service()
        if not svc:
            return
        sess = self._terminals.get_or_create(svc.unit, cwd=svc.dir)
        try:
            send = getattr(sess, "_send", None)
            if callable(send):
                send("\x0c")  # Ctrl-L
                return
        except Exception:
            pass
        # If no backend, just clear the log view
        if self.log_widget:
            self.log_widget.clear()

    def _ensure_terminal_for_service(self, svc: Service, activate: bool = True) -> None:
        try:
            tabs = self.query_one('#term-tabs', Tabs)
            switcher = self.query_one('#term-switcher', ContentSwitcher)
        except Exception:
            return
        key = svc.unit
        if key not in self._term_tabs:
            tab = Tab(label=svc.name, id=key)
            self._term_tabs[key] = tab
            tabs.add_tab(tab)
            # Build or reuse session widget
            sess = self._terminals.get_or_create(key, cwd=svc.dir)
            w = getattr(sess, "widget", None)
            if w is None:
                w = Label("Terminal not available")
            w.id = key  # type: ignore[attr-defined]
            switcher.add(w)
        if activate:
            try:
                tabs.active = key  # type: ignore[assignment]
                switcher.current = key  # type: ignore[assignment]
            except Exception:
                pass

    def _maybe_enable_tmux_refresh(self, key: str) -> None:
        # Enable periodic tmux snapshot refresh when the terminal pane is visible
        if not self._show_terminal:
            self._stop_tmux_refresh()
            return
        try:
            sess = self._terminals.get_or_create(key)
            if isinstance(sess, TmuxSession):
                # Start or switch the refresh target
                self._tmux_refresh_key = key
                if self._tmux_refresh_timer is not None:
                    try:
                        self._tmux_refresh_timer.stop()
                    except Exception:
                        pass
                def _tick() -> None:
                    try:
                        if self._tmux_refresh_key == key:
                            sess.widget.refresh_snapshot()
                    except Exception:
                        pass
                self._tmux_refresh_timer = self.set_interval(1.0, _tick)
            else:
                self._stop_tmux_refresh()
        except Exception:
            self._stop_tmux_refresh()

    def _stop_tmux_refresh(self) -> None:
        if self._tmux_refresh_timer is not None:
            try:
                self._tmux_refresh_timer.stop()
            except Exception:
                pass
        self._tmux_refresh_timer = None
        self._tmux_refresh_key = None

    @on(Input.Changed)
    def _on_search_changed(self, event: Input.Changed) -> None:
        if event.input.id == "search":
            # Update state immediately but debounce expensive rebuilds
            self.state.search = event.value
            if self._search_timer is not None:
                try:
                    self._search_timer.stop()
                except Exception:
                    pass
            # Debounce table rebuild to reduce churn during typing
            def _apply():
                try:
                    self._rebuild_table(select_same=True)
                except Exception:
                    return
            self._search_timer = self.set_timer(0.2, _apply)

    async def action_term_next(self) -> None:
        if not self._show_terminal:
            return
        try:
            tabs = self.query_one('#term-tabs', Tabs)
            ids = [t.id for t in tabs.query(Tab) if getattr(t, 'id', None)]
            if not ids:
                return
            cur = getattr(tabs, 'active', None) or ids[0]
            try:
                i = ids.index(cur)
            except ValueError:
                i = 0
            nxt = ids[(i + 1) % len(ids)]
            tabs.active = nxt  # type: ignore[assignment]
            try:
                switcher = self.query_one('#term-switcher', ContentSwitcher)
                switcher.current = nxt  # type: ignore[assignment]
            except Exception:
                pass
            try:
                self._maybe_enable_tmux_refresh(nxt)  # type: ignore[arg-type]
            except Exception:
                pass
        except Exception:
            pass

    async def action_term_prev(self) -> None:
        if not self._show_terminal:
            return
        try:
            tabs = self.query_one('#term-tabs', Tabs)
            ids = [t.id for t in tabs.query(Tab) if getattr(t, 'id', None)]
            if not ids:
                return
            cur = getattr(tabs, 'active', None) or ids[0]
            try:
                i = ids.index(cur)
            except ValueError:
                i = 0
            prv = ids[(i - 1) % len(ids)]
            tabs.active = prv  # type: ignore[assignment]
            try:
                switcher = self.query_one('#term-switcher', ContentSwitcher)
                switcher.current = prv  # type: ignore[assignment]
            except Exception:
                pass
            try:
                self._maybe_enable_tmux_refresh(prv)  # type: ignore[arg-type]
            except Exception:
                pass
        except Exception:
            pass

    async def _start_follow(self, svc: Service, force_journal: bool = False) -> None:
        # Cancel previous task; guard against redundant restarts
        if (self._follow_current[0] == svc.unit) and (self._follow_current[1] == force_journal) and self._follow_task and not self._follow_task.done():
            return

        if self._follow_task and not self._follow_task.done():
            self._follow_task.cancel()
            with suppress(Exception):
                await self._follow_task

        assert self.log_widget
        self.log_widget.clear()
        if force_journal:
            argv = ["journalctl", "--user", "-f", "-u", svc.unit]
        else:
            argv = follow_argv(svc)
        self.log_widget.write(f"$ {' '.join(argv)}\n")
        self._follow_current = (svc.unit, force_journal)

        async def _runner():
            def _out(line: str):
                assert self.log_widget
                self.log_widget.write(line.rstrip("\n"))

            def _err(line: str):
                assert self.log_widget
                self.log_widget.write(line.rstrip("\n"))

            try:
                rc = await run_command(argv, cwd=svc.dir, on_stdout_line=_out, on_stderr_line=_err)
                self.log_widget.write(f"\n[exit {rc}]")
            except asyncio.CancelledError:
                pass
            except Exception as e:
                self.log_widget.write(f"\n[error: {e}]")

        self._follow_task = asyncio.create_task(_runner())

    async def _run_one_shot(self, argv: list[str], svc: Service) -> int:
        assert self.log_widget
        self.log_widget.write(f"$ {' '.join(argv)}\n")

        lines: list[str] = []

        def _out(line: str):
            lines.append(line.rstrip("\n"))

        def _err(line: str):
            lines.append(line.rstrip("\n"))

        rc = await run_command(argv, cwd=svc.dir, on_stdout_line=_out, on_stderr_line=_err)
        for ln in lines:
            self.log_widget.write(ln)
        self.log_widget.write(f"\n[exit {rc}]")
        return rc

    def _toast(self, msg: str) -> None:
        assert self.log_widget
        self.log_widget.write(f"[note] {msg}")

    def _visible_indices(self) -> list[int]:
        # Compute visible based on filter + search
        def matches_search(svc: Service) -> bool:
            q = self.state.search.strip().lower()
            if not q:
                return True
            hay = " ".join(filter(None, [svc.name, svc.unit, svc.project or ""]))
            return q in hay.lower()

        def matches_filter(svc: Service) -> bool:
            f = self.state.filter
            a = (svc.active or "").lower()
            if f == "all":
                return True
            if f == "active":
                return a == "active"
            if f == "failed":
                return a == "failed"
            return True

        return [i for i, s in enumerate(self.state.services) if matches_search(s) and matches_filter(s)]

    def _format_updated(self, svc: Service) -> str:
        import time
        if not svc.updated_at:
            return "-"
        return time.strftime("%H:%M:%S", time.localtime(svc.updated_at))

    async def _periodic_status_refresh(self) -> None:
        import time
        while True:
            try:
                await asyncio.sleep(10)
                rows = list(range(len(self._rows)))
                sem = asyncio.Semaphore(4)

                async def probe_row(row: int):
                    async with sem:
                        idx = self._rows[row]
                        svc = self.state.services[idx]
                        active, pid = await probe_status(svc)
                        changed = False
                        if active and active != svc.active:
                            svc.active = active
                            changed = True
                        if pid is not None and pid != svc.pid:
                            svc.pid = pid
                            changed = True
                        if changed:
                            svc.updated_at = time.time()
                            self._update_row_by_row(row, svc)

                await asyncio.gather(*(probe_row(r) for r in rows))
            except asyncio.CancelledError:
                break
            except Exception:
                continue


def run_dash(roots: Iterable[Path], max_depth: int = 5, last: int = 200, columns: str = "minimal", terminal_backend: str = "auto") -> None:
    del max_depth  # ww discovery is global; we keep the flag for parity only
    state = AppState(roots=[Path(r) for r in roots])
    # Synchronous pre-discovery (best-effort)
    try:
        # Run an initial discovery within the current event loop
        async def _init():
            state.services = await discover_services_ww(state.roots)
        asyncio.run(_init())
    except Exception:
        state.services = []
    app = WWDashApp(state=state, last=last, columns=columns, terminal_backend=terminal_backend)
    app.run()

