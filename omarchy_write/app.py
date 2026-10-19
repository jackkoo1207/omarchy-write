"""Main window for Omarchy Write."""
from __future__ import annotations

import os
import signal
import sys
import time

from PySide6.QtCore import QEvent, Qt, QSocketNotifier, QThread, QTimer, Signal
from PySide6.QtWidgets import (
    QApplication,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from .canvas import StrokeCanvas
from .insert import insert_text
from .recognizer import Recognizer
from .touchpad import TouchpadReader

PIDFILE = os.path.expanduser("~/.config/omarchy-write/run.pid")

# Editing keys forwarded to the target app (so they edit the text entry box,
# not the panel). Candidate selection is Up/Down instead.
_KEY_FORWARD = {
    Qt.Key.Key_Left: "Left",
    Qt.Key.Key_Right: "Right",
    Qt.Key.Key_Backspace: "BackSpace",
    Qt.Key.Key_Delete: "Delete",
    Qt.Key.Key_Home: "Home",
    Qt.Key.Key_End: "End",
}


class ModelLoader(QThread):
    loaded = Signal(str)  # '' on success, else error message

    def __init__(self, recognizer: Recognizer, parent=None):
        super().__init__(parent)
        self._rec = recognizer

    def run(self):
        self._rec.load("cht")
        self.loaded.emit(self._rec.error or "")


class HeaderBar(QFrame):
    """Draggable header. Moves the window via Hyprland's native move dispatcher,
    since Qt's startSystemMove() doesn't grab under the nofocus window rule."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(38)
        self.setCursor(Qt.CursorShape.OpenHandCursor)
        self._dragging = False
        self._last_global = None
        self._acc_dx = 0.0
        self._acc_dy = 0.0
        self._move_timer = QTimer(self)
        self._move_timer.setInterval(40)
        self._move_timer.timeout.connect(self._flush_move)

    def make_draggable(self, widget):
        """Let a child widget (e.g. the title label) also start a window drag."""
        widget.installEventFilter(self)

    def eventFilter(self, obj, event):
        if (
            event.type() == QEvent.Type.MouseButtonPress
            and event.button() == Qt.MouseButton.LeftButton
        ):
            self._begin(event.globalPosition())
            return True
        return super().eventFilter(obj, event)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._begin(e.globalPosition())
            return
        super().mousePressEvent(e)

    def mouseMoveEvent(self, e):
        if self._dragging:
            gp = e.globalPosition()
            if self._last_global is not None:
                self._acc_dx += gp.x() - self._last_global.x()
                self._acc_dy += gp.y() - self._last_global.y()
            self._last_global = gp
        super().mouseMoveEvent(e)

    def mouseReleaseEvent(self, e):
        if self._dragging and e.button() == Qt.MouseButton.LeftButton:
            self._end()
        super().mouseReleaseEvent(e)

    def _begin(self, gp):
        self._dragging = True
        self._last_global = gp
        self._acc_dx = 0.0
        self._acc_dy = 0.0
        self.grabMouse()
        self._move_timer.start()

    def _end(self):
        self._dragging = False
        self._move_timer.stop()
        self._flush_move()
        self.releaseMouse()

    def _flush_move(self):
        dx, dy = self._acc_dx, self._acc_dy
        self._acc_dx = 0.0
        self._acc_dy = 0.0
        if abs(dx) < 0.5 and abs(dy) < 0.5:
            return
        px, py = int(round(dx)), int(round(dy))
        if px == 0 and py == 0:
            return
        try:
            import subprocess

            subprocess.run(
                [
                    "hyprctl",
                    "dispatch",
                    f"hl.dsp.window.move({{ x = {px}, y = {py}, relative = true, "
                    f"window = 'class:omarchy-write' }})",
                ],
                timeout=1,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Omarchy Handwrite board")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        # Fixed size: prevents the floating window from resizing (and the canvas
        # from reflowing/shifting) when the candidate row appears or disappears.
        self.setFixedSize(470, 430)

        self.recognizer = Recognizer()

        # Touchpad handwriting state.
        self._tp = TouchpadReader()
        self._tp_capture = True  # grab touchpad while the panel is visible
        self._tp_active = False
        self._tp_down_t = 0.0
        self._tp_moved = 0.0
        self._tp_last = None
        self._top_candidate = None
        self._cands: list = []  # current recognition candidates [(text, score), ...]
        self._sel_index = 0     # which candidate is highlighted (arrow keys move it)
        self._cand_buttons: list = []
        self._prev_addr = None  # Hyprland address of the last-focused non-mine window

        self._build_ui()
        self._setup_signals()
        self._write_pidfile()

        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(700)
        self._debounce.timeout.connect(self._recognize_current)
        self.canvas.strokeFinished.connect(self._debounce.start)
        self.canvas.strokeStarted.connect(self._on_stroke_started)

        # Auto-fill: after recognition, if the user doesn't intervene (arrows /
        # Super+Z), the highlighted candidate is inserted automatically.
        self._autofill = QTimer(self)
        self._autofill.setSingleShot(True)
        self._autofill.setInterval(1200)
        self._autofill.timeout.connect(self._confirm_selection)

        self._tp_timer = QTimer(self)
        self._tp_timer.setInterval(10)
        self._tp_timer.timeout.connect(self._poll_touchpad)

        self._focus_timer = QTimer(self)
        self._focus_timer.setInterval(500)
        self._focus_timer.timeout.connect(self._track_focus)
        self._focus_timer.start()

        self._loader = ModelLoader(self.recognizer, self)
        self._loader.loaded.connect(self._on_model_loaded)
        self._loader.start()
        self._set_status("載入辨識模型中…")

    # -- UI ------------------------------------------------------------
    def _build_ui(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        card = QFrame(self)
        card.setObjectName("card")
        outer.addWidget(card)

        lay = QVBoxLayout(card)
        lay.setContentsMargins(14, 10, 14, 14)
        lay.setSpacing(10)

        # Header
        header = QHBoxLayout()
        header.setSpacing(8)
        self.title = QLabel("⠿ Omarchy Handwrite board · 繁簡手寫")
        self.title.setStyleSheet("color: #cdd6f4; font-weight: 600;")
        self.title.setCursor(Qt.CursorShape.OpenHandCursor)
        header.addWidget(self.title)
        header.addStretch(1)

        self.tp_btn = QPushButton("✍")
        self.tp_btn.setFixedSize(34, 28)
        self.tp_btn.setCheckable(True)
        self.tp_btn.setChecked(True)
        self.tp_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.tp_btn.setToolTip("觸控板寫字開/關")
        self.tp_btn.toggled.connect(self._toggle_touchpad_capture)
        header.addWidget(self.tp_btn)

        self.clear_btn = QPushButton("清")
        self.clear_btn.setFixedSize(34, 28)
        self.clear_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.clear_btn.setToolTip("清除")
        self.clear_btn.clicked.connect(self._clear)
        header.addWidget(self.clear_btn)

        self.close_btn = QPushButton("✕")
        self.close_btn.setFixedSize(34, 28)
        self.close_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self.close_btn.clicked.connect(self.hide)
        header.addWidget(self.close_btn)

        hdr = HeaderBar()
        hdr.setLayout(header)
        hdr.make_draggable(self.title)
        lay.addWidget(hdr)

        # Canvas
        self.canvas = StrokeCanvas()
        lay.addWidget(self.canvas, 1)

        # Status + candidates. Fixed heights keep the canvas from reflowing
        # (and the ink shifting) when candidates appear/disappear mid-writing.
        self.status = QLabel(" ")
        self.status.setStyleSheet("color: #a6adc8; font-size: 12px;")
        self.status.setFixedHeight(18)
        lay.addWidget(self.status)

        self.cand_row = QHBoxLayout()
        self.cand_row.setSpacing(8)
        cand_holder = QWidget()
        cand_holder.setFixedHeight(50)
        cand_holder.setLayout(self.cand_row)
        lay.addWidget(cand_holder)

        self._apply_style()

    def _apply_style(self):
        self.setStyleSheet(
            """
            #card { background: rgba(30,30,46,0.96); border-radius: 16px; }
            QPushButton {
                background: #313244; color: #cdd6f4; border: none;
                border-radius: 8px; font-size: 13px;
            }
            QPushButton:hover { background: #45475a; }
            QPushButton#cand {
                background: #45475a; color: #f5e0dc;
                font-size: 20px; padding: 6px 12px; border-radius: 10px;
            }
            QPushButton#cand:hover { background: #585b70; }
            QPushButton#cand_sel {
                background: #89b4fa; color: #1e1e2e;
                font-size: 20px; padding: 6px 12px; border-radius: 10px;
            }
            """
        )

    # -- status / candidates -------------------------------------------
    def _set_status(self, text: str):
        self.status.setText(text)

    def _clear_candidates(self):
        self._cands = []
        self._cand_buttons = []
        self._sel_index = 0
        while self.cand_row.count():
            item = self.cand_row.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()

    def _show_candidates(self, cands):
        self._clear_candidates()
        self._cands = cands
        self._sel_index = 0
        self._top_candidate = cands[0][0] if cands else None
        if not cands:
            self._set_status("未辨識到（再寫一次，或點「清」重來）")
            return
        for text, _score in cands[:6]:
            b = QPushButton(text)
            b.setObjectName("cand")
            b.setFocusPolicy(Qt.FocusPolicy.NoFocus)
            b.setFixedHeight(44)  # room for the full CJK glyph (clips otherwise)
            b.clicked.connect(lambda _=False, t=text: self._insert(t))
            self._cand_buttons.append(b)
            self.cand_row.addWidget(b)
        self.cand_row.addStretch(1)
        self._highlight_selection()
        self._focus_self()  # ensure the panel has focus so Up/Down work
        self._autofill.start()  # auto-insert the highlighted candidate shortly

    # -- actions --------------------------------------------------------
    def _insert(self, text: str):
        self._autofill.stop()
        insert_text(text, self._prev_addr)
        self._set_status(f"已插入：{text}")
        self.canvas.clear()
        self._clear_candidates()
        self._top_candidate = None
        # NOTE: focus is deliberately left on the target app after inserting, so
        # the user's Left/Right/Backspace keys edit the text entry box.

    def _focus_self(self):
        """Focus this panel (so arrow keys keep working) via Hyprland."""
        try:
            import subprocess

            subprocess.run(
                ["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:omarchy-write' })"],
                timeout=2,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:  # noqa: BLE001
            pass

    def _confirm_selection(self):
        """Insert the currently-highlighted candidate (auto-fill or explicit)."""
        self._autofill.stop()
        if 0 <= self._sel_index < len(self._cands):
            self._insert(self._cands[self._sel_index][0])

    def _move_selection(self, delta: int):
        if not self._cands:
            return
        n = min(len(self._cands), 6)
        self._sel_index = (self._sel_index + delta) % n
        self._highlight_selection()
        self._autofill.start()  # restart the auto-fill grace period

    def _highlight_selection(self):
        for i, b in enumerate(self._cand_buttons):
            b.setObjectName("cand_sel" if i == self._sel_index else "cand")
            b.style().unpolish(b)
            b.style().polish(b)
        if self._cands:
            sel = self._cands[self._sel_index][0]
            self._set_status(f"選：{sel}  ↑↓選字 · Super+Z 確認")

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Up:
            self._move_selection(-1)
        elif e.key() == Qt.Key.Key_Down:
            self._move_selection(1)
        else:
            self._forward_key(e)

    def _forward_key(self, e):
        """Forward editing keys (Left/Right/Backspace/…) to the target app so
        the user can move the cursor / delete text in the entry box directly."""
        keyname = _KEY_FORWARD.get(e.key())
        if keyname is None:
            return
        self._autofill.stop()  # editing cancels any pending auto-fill
        try:
            import subprocess

            addr = self._prev_addr
            if addr:
                subprocess.run(
                    ["hyprctl", "dispatch", f"hl.dsp.focus({{ window = 'address:{addr}' }})"],
                    timeout=2, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
            time.sleep(0.08)  # let the focus change settle
            subprocess.run(["wtype", "-k", keyname], timeout=3)
        except Exception:  # noqa: BLE001
            pass

    def _track_focus(self):
        """Remember the address of the last-focused non-mine window, so we can
        refocus it (and paste into it) after the panel steals focus on click."""
        self._capture_target()

    def _capture_target(self):
        """Snapshot the currently-focused window as the paste target (unless it
        is this panel)."""
        try:
            import json
            import subprocess

            out = subprocess.run(
                ["hyprctl", "activewindow", "-j"],
                capture_output=True, text=True, timeout=1,
            )
            d = json.loads(out.stdout)
            if d.get("class") != "omarchy-write" and d.get("address"):
                self._prev_addr = d["address"]
        except Exception:  # noqa: BLE001
            pass

    def _clear(self):
        self._autofill.stop()
        self.canvas.clear()
        self._clear_candidates()
        self._top_candidate = None
        self._set_status(" ")

    def _recognize_current(self):
        if not self.canvas.has_strokes():
            return
        if not self.recognizer.ready:
            self._set_status("模型尚未載入完成…")
            return
        cands = self.recognizer.recognize_strokes(self.canvas.normalized_strokes())
        self._show_candidates(cands)

    def _on_stroke_started(self):
        # A new stroke means the user is still writing — cancel any pending
        # recognition. If a previous character is still pending (candidates
        # showing), commit it now so its ink doesn't pile onto the new one.
        self._debounce.stop()
        if self._cands:
            text = self._cands[self._sel_index][0]
            self._autofill.stop()
            # Clear the pending character's ink/candidates synchronously so the
            # new stroke draws on a clean canvas.
            self.canvas.clear()
            self._clear_candidates()
            self._top_candidate = None
            self._sel_index = 0
            # Defer the paste (refocus target + Ctrl+V) to the next event-loop
            # tick so it doesn't race the current mouse/touch event's own focus
            # handling.
            QTimer.singleShot(80, lambda: self._insert(text))
        else:
            self._autofill.stop()

    def _on_model_loaded(self, err: str):
        if err:
            self._set_status(f"模型載入失敗：{err}")
        elif self._tp.error:
            self._set_status(f"就緒。觸控板需權限：{self._tp.error}（滑鼠仍可繪畫）")
        elif self._tp.running:
            self._set_status("就緒。觸控板寫字中：寫字後輕點插入")
        else:
            self._set_status("就緒。在白色區域寫字（滑鼠/觸控板按住拖曳）")

    # -- toggle / confirm via signals -----------------------------------
    # SIGUSR1 toggles show/hide; SIGUSR2 confirms (inserts) the currently
    # highlighted candidate. The wakeup fd writes one byte per signal = the
    # signal number, so a single pipe carries both actions.
    def _setup_signals(self):
        self._pipe_r, self._pipe_w = os.pipe()
        os.set_blocking(self._pipe_r, False)
        os.set_blocking(self._pipe_w, False)
        # A no-op Python handler overrides each signal's default (terminate)
        # action while keeping Python's C-level signal machinery alive;
        # set_wakeup_fd then writes the signal number to the pipe
        # (async-signal-safe), waking the Qt event loop via QSocketNotifier.
        signal.signal(signal.SIGUSR1, lambda *_: None)
        signal.signal(signal.SIGUSR2, lambda *_: None)
        signal.set_wakeup_fd(self._pipe_w)
        self._notifier = QSocketNotifier(self._pipe_r, QSocketNotifier.Type.Read)
        self._notifier.activated.connect(self._on_signal)

    def _on_signal(self):
        try:
            data = os.read(self._pipe_r, 4096)
        except OSError:
            return
        for byte in data:
            sig = int(byte)
            if sig == int(signal.SIGUSR1):
                if self.isVisible():
                    self.hide()
                else:
                    self._capture_target()  # snapshot the target before we steal focus
                    self.show()
            elif sig == int(signal.SIGUSR2):
                self._confirm_selection()

    # -- touchpad handwriting ------------------------------------------
    def showEvent(self, e):
        super().showEvent(e)
        if self._tp_capture:
            self._start_touchpad()
        # Focus the panel so the left/right arrow keys reach it.
        QTimer.singleShot(80, self._focus_self)

    def hideEvent(self, e):
        super().hideEvent(e)
        self._stop_touchpad()

    def _start_touchpad(self):
        if self._tp.running:
            return
        if not self._tp.start():
            # Non-fatal: mouse/stylus drawing still works.
            self._set_status(f"觸控板無法使用（{self._tp.error}）")
            return
        self._tp_timer.start()
        self._set_status("觸控板寫字中：在觸控板上寫字，輕點插入候選字")

    def _stop_touchpad(self):
        self._tp_timer.stop()
        self._tp.stop()
        self._tp_active = False

    def _toggle_touchpad_capture(self, checked: bool):
        self._tp_capture = checked
        if checked and self.isVisible():
            self._start_touchpad()
        elif not checked:
            self._stop_touchpad()
            self._set_status("觸控板寫字已停用（滑鼠仍可繪畫）")

    def _poll_touchpad(self):
        if self.canvas is None:
            return
        events = self._tp.poll()
        cw = max(self.canvas.width(), 1)
        ch = max(self.canvas.height(), 1)
        for kind, x, y in events:
            px = None if x is None else x * cw
            py = None if y is None else y * ch
            if kind == "down":
                self._tp_active = True
                self._tp_down_t = time.monotonic()
                self._tp_moved = 0.0
                self._tp_last = None
                if px is not None and py is not None:
                    self.canvas.remote_move(px, py)
                    self._tp_last = (px, py)
            elif kind == "move":
                if not self._tp_active:
                    self._tp_active = True
                    self._tp_down_t = time.monotonic()
                    self._tp_moved = 0.0
                if px is not None and py is not None:
                    self.canvas.remote_move(px, py)
                    if self._tp_last is not None:
                        dx = px - self._tp_last[0]
                        dy = py - self._tp_last[1]
                        self._tp_moved += (dx * dx + dy * dy) ** 0.5
                    self._tp_last = (px, py)
            elif kind == "up":
                if not self._tp_active:
                    continue
                dur = time.monotonic() - self._tp_down_t
                self._tp_active = False
                is_tap = dur < 0.25 and self._tp_moved < 12
                if is_tap:
                    self.canvas.remote_end(commit=False)
                    self._confirm_selection()
                else:
                    self.canvas.remote_end(commit=True)

    def _write_pidfile(self):
        os.makedirs(os.path.dirname(PIDFILE), exist_ok=True)
        with open(PIDFILE, "w") as f:
            f.write(str(os.getpid()))

    def closeEvent(self, e):
        self._stop_touchpad()
        try:
            os.remove(PIDFILE)
        except OSError:
            pass
        super().closeEvent(e)


def main() -> int:
    app = QApplication(sys.argv)
    app.setApplicationName("omarchy-write")
    app.setApplicationDisplayName("Omarchy Handwrite board")
    # Deterministic Wayland app_id (Hyprland "class") regardless of PySide6
    # version or how the console script is invoked (python3 vs. script name).
    app.setDesktopFileName("omarchy-write")
    app.setQuitOnLastWindowClosed(False)  # keep running when hidden
    win = MainWindow()
    win.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
