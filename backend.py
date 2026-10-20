#!/usr/bin/env python3
"""Headless backend for the Omarchy Handwrite board Quickshell plugin.

Captures the touchpad, runs PaddleOCR recognition, inserts recognized text
into the previously focused window, and talks to the QML panel over stdio
using newline-delimited JSON.

Commands (stdin, QML -> backend):
  {"type": "show"}                     panel visible: grab touchpad
  {"type": "hide"}                     panel hidden: release touchpad
  {"type": "select", "index": N}       highlight candidate N (0-based)
  {"type": "confirm"}                  commit the highlighted candidate now
  {"type": "clear"}                    clear ink + candidates
  {"type": "stroke", "phase": "...", "x": f, "y": f}   synthetic stroke (mouse)

Events (stdout, backend -> QML):
  {"type": "ready"}                              model loaded
  {"type": "down", "x": f, "y": f}               pen down (normalized 0..1)
  {"type": "move", "x": f, "y": f}               pen move
  {"type": "up"}                                 pen lift
  {"type": "candidates", "chars": [..]}          recognition results
  {"type": "inserted", "text": ".."}             a character was committed
  {"type": "clear_surface"}                      clear the canvas
  {"type": "status", "text": ".."}               status line
"""

from __future__ import annotations

import json
import os
import select
import subprocess
import sys
import threading
import time

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from omarchy_write.touchpad import TouchpadReader  # noqa: E402
from omarchy_write.recognizer import Recognizer  # noqa: E402
from omarchy_write import insert as insert_mod  # noqa: E402

PANEL_TITLE = "Omarchy Handwrite board"
DEBOUNCE_S = 0.7
AUTOFILL_S = 1.2
HOTKEY_HINT = "Super+A 選左 · Super+D 選右 · Super+Z 確認"


def _emit(obj: dict) -> None:
    sys.stdout.write(json.dumps(obj, ensure_ascii=False) + "\n")
    sys.stdout.flush()


class Backend:
    def __init__(self) -> None:
        self.reader = TouchpadReader()
        self.rec = Recognizer()

        self.strokes: list[list[tuple[float, float]]] = []
        self.current: list[tuple[float, float]] | None = None

        self.cands: list[str] = []
        self.sel = 0
        self.target_addr: str | None = None

        self.debounce_deadline: float | None = None
        self.autofill_deadline: float | None = None
        self._last_touch = 0.0
        self._last_focus = 0.0
        self._last_tp_watch = 0.0
        self._shown = False
        self._grab_on = False
        self._running = True

        threading.Thread(target=self._load_model, daemon=True).start()
        threading.Thread(target=self._focus_loop, daemon=True).start()

    # -- model ----------------------------------------------------------
    def _load_model(self) -> None:
        self.rec.load()
        if self.rec.ready:
            _emit({"type": "ready"})
            _emit({"type": "status", "text": f"可開始書寫 · {HOTKEY_HINT}" if self._shown else "就緒"})
        else:
            _emit({"type": "status", "text": f"模型載入失敗：{self.rec.error}"})

    # -- commands -------------------------------------------------------
    def handle(self, obj: dict) -> None:
        t = obj.get("type")
        if t == "show":
            self._shown = True
            self._grab_on = True
            self._track_focus()  # capture target before the panel takes focus
            _emit({"type": "status", "text": f"可開始書寫 · {HOTKEY_HINT}" if self.rec.ready else "模型載入中…"})
            if not self.reader.running:
                self.reader.start()
        elif t == "hide":
            self._shown = False
            self._grab_on = False
            self.reader.stop()
            self._reset(True)
        elif t == "select":
            self.sel = int(obj.get("index", 0))
            # Restart the auto-fill timer so the newly-selected candidate
            # fills after a short pause unless the user keeps choosing.
            self.autofill_deadline = time.monotonic() + AUTOFILL_S
            _emit({"type": "status", "text": self._sel_status()})
        elif t == "confirm":
            self._commit(self.sel)
        elif t == "clear":
            self._reset(True)
            _emit({"type": "status", "text": f"可開始書寫 · {HOTKEY_HINT}" if self.rec.ready else "模型載入中…"})
        elif t == "toggle_grab":
            if self._grab_on:
                self._grab_on = False
                self.reader.stop()
            else:
                self._grab_on = True
                if not self.reader.running:
                    self.reader.start()
            self._emit_grab_state()
        elif t == "stroke":
            phase = obj.get("phase")
            x = float(obj.get("x", 0.0))
            y = float(obj.get("y", 0.0))
            self._on_touch(phase, x, y)

    def _sel_status(self) -> str:
        if 0 <= self.sel < len(self.cands):
            return f"選：{self.cands[self.sel]} · {HOTKEY_HINT}"
        return f"可開始書寫 · {HOTKEY_HINT}"

    def _emit_grab_state(self) -> None:
        on = self._grab_on
        _emit({"type": "grab_state", "on": on})
        _emit(
            {
                "type": "status",
                "text": (
                    f"觸控板抓取中 · {HOTKEY_HINT}"
                    if on
                    else f"觸控板已釋放 · Super+U 重新抓取"
                ),
            }
        )

    # -- touchpad -------------------------------------------------------
    def _on_touch(self, kind: str, x: float, y: float) -> None:
        if kind == "down":
            # A new stroke while a character is pending commits it first, so
            # ink from the previous character doesn't pile up.
            self.debounce_deadline = None
            if self.cands:
                self._commit(self.sel)
            self.current = [(x, y)]
            _emit({"type": "down", "x": x, "y": y})
        elif kind == "move":
            if self.current is None:
                return
            self.current.append((x, y))
            _emit({"type": "move", "x": x, "y": y})
        elif kind == "up":
            if self.current is None:
                return
            self.strokes.append(self.current)
            self.current = None
            _emit({"type": "up"})
            self.debounce_deadline = time.monotonic() + DEBOUNCE_S

    # -- recognition ----------------------------------------------------
    def _recognize(self) -> None:
        if not self.strokes:
            return
        if not self.rec.ready:
            # Model still loading — retry shortly instead of dropping the ink.
            self.debounce_deadline = time.monotonic() + 0.4
            return
        threading.Thread(
            target=self._recognize_worker, args=(list(self.strokes),), daemon=True
        ).start()

    def _recognize_worker(self, strokes) -> None:
        try:
            cands = self.rec.recognize_strokes(strokes)
        except Exception as e:  # noqa: BLE001
            _emit({"type": "status", "text": f"辨識錯誤：{e}"})
            return
        self.cands = [c for c, _ in cands]
        self.sel = 0
        self.autofill_deadline = time.monotonic() + AUTOFILL_S
        _emit({"type": "candidates", "chars": self.cands})
        _emit(
            {
                "type": "status",
                "text": self._sel_status() if self.cands else "未辨識到字，請重寫",
            }
        )

    # -- insert ---------------------------------------------------------
    def _commit(self, idx: int) -> None:
        if not (0 <= idx < len(self.cands)):
            return
        text = self.cands[idx]
        target = self.target_addr
        # Clear the surface immediately so the panel stays responsive; do the
        # clipboard + refocus + paste in the background (it can block ~0.3s).
        self._reset(True)
        threading.Thread(
            target=self._insert_worker, args=(text, target), daemon=True
        ).start()

    def _insert_worker(self, text: str, target: str | None) -> None:
        insert_mod.insert_text(text, target)
        _emit({"type": "inserted", "text": text})
        _emit({"type": "status", "text": f"已插入「{text}」· {HOTKEY_HINT}"})

    def _reset(self, clear_surface: bool) -> None:
        self.strokes = []
        self.current = None
        self.cands = []
        self.sel = 0
        self.debounce_deadline = None
        self.autofill_deadline = None
        if clear_surface:
            _emit({"type": "clear_surface"})

    # -- focus tracking -------------------------------------------------
    def _track_focus(self) -> None:
        # The panel steals focus when summoned, so `activewindow` only ever
        # reports the panel. Instead, find the previously-focused app via
        # Hyprland's focusHistoryID: the highest-ID window that isn't the panel.
        try:
            out = subprocess.run(
                ["hyprctl", "clients", "-j"],
                capture_output=True, text=True, timeout=1,
            )
            clients = json.loads(out.stdout)
            best = None
            best_fh = -1
            for c in clients:
                if c.get("title") == PANEL_TITLE:
                    continue
                fh = c.get("focusHistoryID", -1)
                if c.get("address") and fh > best_fh:
                    best_fh = fh
                    best = c
            if best:
                self.target_addr = best["address"]
        except Exception:  # noqa: BLE001
            pass

    def _focus_loop(self) -> None:
        while self._running:
            self._track_focus()
            time.sleep(0.5)

    # -- main loop ------------------------------------------------------
    def run(self) -> None:
        while self._running:
            # stdin (non-blocking)
            r, _, _ = select.select([sys.stdin], [], [], 0)
            if r:
                line = sys.stdin.readline()
                if not line:  # stdin closed -> QML went away
                    break
                line = line.strip()
                if line:
                    try:
                        self.handle(json.loads(line))
                    except Exception as e:  # noqa: BLE001
                        _emit({"type": "status", "text": f"訊息錯誤：{e}"})

            now = time.monotonic()

            # touchpad poll
            if self._shown and now - self._last_touch > 0.01:
                self._last_touch = now
                for ev in self.reader.poll():
                    if ev[0] == "down":
                        self._on_touch("down", ev[1], ev[2])
                    elif ev[0] == "move":
                        self._on_touch("move", ev[1], ev[2])
                    elif ev[0] == "up":
                        self._on_touch("up", None, None)

            # touchpad reader watchdog: re-spawn if the child died
            if self._shown and self._grab_on and now - self._last_tp_watch > 1.0:
                self._last_tp_watch = now
                if not self.reader.alive():
                    self.reader.stop()
                    self.reader.start()

            # timers
            if self.debounce_deadline and now >= self.debounce_deadline:
                self.debounce_deadline = None
                self._recognize()
            if self.autofill_deadline and now >= self.autofill_deadline:
                self.autofill_deadline = None
                if self.cands:
                    self._commit(self.sel)

            time.sleep(0.005)

        self.reader.stop()


def main() -> int:
    Backend().run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
