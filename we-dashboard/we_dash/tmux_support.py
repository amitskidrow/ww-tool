from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import subprocess

from textual.widgets import RichLog


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _has_tmux_bin() -> bool:
    try:
        cp = _run(["tmux", "-V"])
        return cp.returncode == 0
    except Exception:
        return False


def _libtmux_server():
    import libtmux  # type: ignore
    return libtmux.Server()


def _tmux_session(server, session_name: str):
    sess = None
    try:
        sess = server.find_where({"session_name": session_name})
    except Exception:
        sess = None
    if sess is None:
        sess = server.new_session(session_name=session_name, attach=False, kill_session=False)
    return sess


def ensure_tmux_pane(session_name: str, window_name: str, cwd: Optional[Path] = None):
    """
    Ensure a tmux session/window/pane exists and return the pane.
    """
    if not _has_tmux_bin():
        raise RuntimeError("tmux binary not found")
    server = _libtmux_server()
    sess = _tmux_session(server, session_name)
    win = sess.find_where({"window_name": window_name})
    if win is None:
        win = sess.new_window(window_name=window_name, attach=False)
    pane = win.panes[0]
    if cwd is not None:
        try:
            pane.send_keys(f"cd {str(cwd)} && clear", enter=True)
        except Exception:
            pass
    return pane


class TmuxMirrorWidget(RichLog):
    """
    Minimal mirror that snapshots tmux pane content on demand.
    Call refresh_snapshot() to update the content.
    """

    def __init__(self, session_name: str, window_name: str) -> None:
        super().__init__(highlight=False, markup=False, wrap=False)
        self._session_name = session_name
        self._window_name = window_name
        self.write("tmux mirror — press T to toggle; actions run here when terminal is active")

    def refresh_snapshot(self) -> None:
        try:
            server = _libtmux_server()
            sess = _tmux_session(server, self._session_name)
            win = sess.find_where({"window_name": self._window_name})
            if win is None:
                return
            pane = win.panes[0]
            # Capture pane content
            out = pane.capture_pane(start=-200)  # last 200 lines
            self.clear()
            for ln in out:
                self.write(ln)
        except Exception:
            # Non-fatal; leave existing content
            pass


@dataclass
class TmuxSession:
    widget: TmuxMirrorWidget
    pane: any
    cwd: Optional[Path] = None

    def run_argv(self, argv: list[str], cwd: Optional[Path] = None) -> bool:
        try:
            cmd = " ".join(_shell_quote(a) for a in argv)
            prefix = ""
            if cwd:
                prefix = f"cd {_shell_quote(str(cwd))} && "
            self.pane.send_keys(prefix + cmd, enter=True)
            try:
                self.widget.refresh_snapshot()
            except Exception:
                pass
            return True
        except Exception:
            return False


def _shell_quote(s: str) -> str:
    import shlex
    return shlex.quote(s)

