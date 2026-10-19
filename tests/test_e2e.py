"""End-to-end offscreen test: strokes -> recognition -> candidate bar."""
from __future__ import annotations

import os
import sys
import time

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from omarchy_write.app import MainWindow  # noqa: E402


def _st(pts):
    return [QPointF(x, y) for x, y in pts]


def candidates(w):
    labels = []
    for i in range(w.cand_row.count()):
        it = w.cand_row.itemAt(i)
        if it.widget() and isinstance(it.widget(), QPushButton):
            labels.append(it.widget().text())
    return labels


def main() -> int:
    app = QApplication([])
    w = MainWindow()
    w.resize(470, 430)
    w.show()

    # Wait for model (downloads already cached).
    for _ in range(600):
        app.processEvents()
        if w.recognizer.ready:
            break
        time.sleep(0.1)
    print("model ready:", w.recognizer.ready, "| err:", w.recognizer.error)
    if not w.recognizer.ready:
        return 1

    # "中" = taller-than-wide box + vertical line protruding above and below.
    cw = max(w.canvas.width(), 100)
    ch = max(w.canvas.height(), 100)
    x0, x1 = 0.35 * cw, 0.65 * cw
    y0, y1 = 0.25 * ch, 0.60 * ch
    w.canvas._strokes = [
        _st([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)]),
        _st([(0.5 * cw, 0.15 * ch), (0.5 * cw, 0.70 * ch)]),
    ]
    w._recognize_current()
    app.processEvents()
    print("candidates for '中':", candidates(w))

    ok = bool(candidates(w)) and candidates(w)[0] == "中"
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
