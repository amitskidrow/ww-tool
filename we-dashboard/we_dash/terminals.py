from __future__ import annotations

from pathlib import Path
from typing import Optional, Callable, Any, Literal

from textual.widgets import Label
from textual.widget import Widget
import shlex


def terminal_supported() -> bool:
    try:
        import importlib
        importlib.import_module("textual_terminal")
        return True
    except Exception:
        return False


def _tmux_available() -> bool:
    try:
        import importlib
        import subprocess
        importlib.import_module("libtmux")
        cp = subprocess.run(["tmux", "-V"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return cp.returncode == 0
    except Exception:
        return False


class TerminalSession:
    """Adapter around a terminal widget to send commands/text safely.

    It attempts to discover available APIs on the underlying widget at runtime and
    degrades gracefully if the backend isn't installed.
    """

    def __init__(self, widget: Widget, cwd: Optional[Path] = None) -> None:
        self.widget = widget
        self.cwd = cwd
        # Resolve best-effort callable hooks
        self._send = self._resolve_any(["send_text", "write_text", "write", "feed", "paste"])  # type: ignore
        self._run = self._resolve_any(["run_command"])  # type: ignore
        self._open_shell = self._resolve_any(["open_shell", "open", "open_process"])  # type: ignore
        # Try to ensure a shell is open (best-effort, ignore failures)
        try:
            if callable(self._open_shell):
                # open_shell(cwd=..), others may not accept cwd
                if self._open_shell.__name__ == "open_shell":
                    self._open_shell(cwd=str(cwd) if cwd else None)
                else:
                    self._open_shell()
        except Exception:
            pass

    def _resolve_any(self, names: list[str]) -> Optional[Callable[..., Any]]:
        for n in names:
            fn = getattr(self.widget, n, None)
            if callable(fn):
                return fn
        return None

    def run_argv(self, argv: list[str], cwd: Optional[Path] = None) -> bool:
        """Run argv in the terminal if possible. Returns True if dispatched.

        Falls back to sending a shell-escaped command line with a newline.
        """
        try:
            if callable(self._run):
                # Some implementations may accept a string; prefer argv if supported.
                self._run(argv)  # type: ignore[arg-type]
                return True
        except Exception:
            pass
        try:
            if callable(self._send):
                cmd = shlex.join(argv)
                prefix = ""
                if cwd:
                    prefix = f"cd {shlex.quote(str(cwd))} && "
                self._send(prefix + cmd + "\n")
                return True
        except Exception:
            pass
        return False


def create_terminal_widget(cwd: Path | None = None) -> Widget:
    try:
        from textual_terminal import Terminal  # type: ignore
        return Terminal()  # type: ignore[call-arg]
    except Exception:
        text = "Terminal support not installed (pip install 'textual-terminal' or use extras: we-dash[terminal])"
        if cwd is not None:
            text += f"\nCWD: {cwd}"
        return Label(text)


BackendName = Literal["auto", "native", "tmux"]


class TerminalRegistry:
    def __init__(self, backend: BackendName = "auto") -> None:
        self._store: dict[str, TerminalSession] = {}
        self.backend: BackendName = backend

    def get_or_create(self, key: str, cwd: Optional[Path] = None) -> TerminalSession:
        sess = self._store.get(key)
        if sess is None:
            if self._should_use_tmux():
                sess = self._create_tmux_session(key, cwd)
            else:
                w = create_terminal_widget(cwd)
                sess = TerminalSession(w, cwd=cwd)
            self._store[key] = sess
        return sess

    def _should_use_tmux(self) -> bool:
        if self.backend == "tmux":
            return _tmux_available()
        if self.backend == "native":
            return False
        # auto → prefer native terminal when available; else tmux if available
        if terminal_supported():
            return False
        return _tmux_available()

    def _create_tmux_session(self, key: str, cwd: Optional[Path]) -> TerminalSession:
        # Defer imports and errors; fallback to placeholder on error
        try:
            from .tmux_support import ensure_tmux_pane, TmuxMirrorWidget, TmuxSession
            pane = ensure_tmux_pane(session_name="wedash", window_name=key, cwd=cwd)
            widget = TmuxMirrorWidget(session_name="wedash", window_name=key)
            return TmuxSession(widget=widget, pane=pane, cwd=cwd)
        except Exception:
            w = create_terminal_widget(cwd)
            return TerminalSession(w, cwd=cwd)

    def items(self):
        return self._store.items()
