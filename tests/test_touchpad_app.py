"""Deterministic test of the app's touchpad -> canvas processing."""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication  # noqa: E402

from omarchy_write.app import MainWindow  # noqa: E402


def main() -> int:
    app = QApplication([])
    w = MainWindow()
    w.resize(470, 430)
    w.show()
    app.processEvents()

    q = w._tp._queue
    import time

    # Realistic stroke: larger movement (maps to ~88px on canvas).
    q.put(("down", None, None))
    q.put(("move", 0.30, None))  # X only (Y not known yet)
    q.put(("move", 0.30, 0.30))  # both
    q.put(("move", 0.35, 0.32))
    q.put(("move", 0.40, 0.35))
    q.put(("move", 0.45, 0.38))
    q.put(("move", 0.50, 0.40))
    w._poll_touchpad()  # process down + moves

    # Simulate a touch lasting > 0.25s before lift.
    w._tp_down_t = time.monotonic() - 0.5
    q.put(("up", 0.50, 0.40))
    w._poll_touchpad()  # process up -> commit stroke

    print("moved:", round(w._tp_moved, 1))
    print("strokes committed:", len(w.canvas._strokes))
    ok = w._tp_moved > 12 and len(w.canvas._strokes) == 1
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
