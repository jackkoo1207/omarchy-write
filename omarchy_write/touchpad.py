"""Touchpad capture via a separate reader process.

evdev runs in a child process (``touchpad_reader``) to isolate it from Qt —
sharing the process caused a ``none_dealloc`` refcount crash. This class
spawns the child, reads its stdout in a plain thread (no evdev/Qt), and
exposes normalized events via ``poll()``.
"""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
import time


class TouchpadReader:
    def __init__(self):
        self._proc: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._queue: queue.Queue = queue.Queue()
        self._stop = threading.Event()
        self._ready = False
        self.error: str | None = None

    @property
    def running(self) -> bool:
        return self._proc is not None

    def start(self) -> bool:
        if self._proc is not None:
            return True
        self._ready = False
        self.error = None
        try:
            self._proc = subprocess.Popen(
                [sys.executable, "-m", "omarchy_write.touchpad_reader"],
                stdout=subprocess.PIPE,
                stderr=subprocess.DEVNULL,
                text=True,
                bufsize=1,
            )
        except Exception as e:  # noqa: BLE001
            self.error = f"無法啟動觸控板讀取程序：{e}"
            return False
        self._stop.clear()
        self._thread = threading.Thread(target=self._read, daemon=True)
        self._thread.start()
        # Wait briefly for the child to report ready/error.
        deadline = time.monotonic() + 1.5
        while time.monotonic() < deadline:
            if self._ready:
                return True
            if self.error:
                return False
            time.sleep(0.05)
        return True

    def _read(self):
        try:
            for line in self._proc.stdout:
                if self._stop.is_set():
                    break
                parts = line.strip().split()
                if not parts:
                    continue
                kind = parts[0]
                if kind == "ready":
                    self._ready = True
                elif kind == "down" and len(parts) == 3:
                    self._queue.put(("down", float(parts[1]), float(parts[2])))
                elif kind == "move" and len(parts) == 3:
                    self._queue.put(("move", float(parts[1]), float(parts[2])))
                elif kind == "up":
                    self._queue.put(("up", None, None))
                elif kind == "error":
                    self.error = " ".join(parts[1:])
        except Exception as e:  # noqa: BLE001
            self.error = str(e)

    def stop(self):
        self._stop.set()
        proc, self._proc = self._proc, None
        self._thread = None
        if proc is not None:
            try:
                proc.terminate()
                proc.wait(timeout=2)
            except Exception:  # noqa: BLE001
                try:
                    proc.kill()
                except Exception:  # noqa: BLE001
                    pass

    def poll(self):
        out = []
        while True:
            try:
                out.append(self._queue.get_nowait())
            except queue.Empty:
                break
        return out
