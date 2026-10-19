"""Headless UI test: render the window offscreen and verify layout + candidates."""
from __future__ import annotations

import os
import sys

os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from PySide6.QtWidgets import QApplication, QPushButton  # noqa: E402

from omarchy_write.app import MainWindow  # noqa: E402


def analyze(img) -> dict:
    import numpy as np
    from PIL import Image

    path = "/tmp/ow_offscreen.png"
    img.save(path, "PNG")
    arr = np.asarray(Image.open(path).convert("RGB"))
    return {"array": arr, "size": (arr.shape[1], arr.shape[0])}


def main() -> int:
    app = QApplication([])
    w = MainWindow()
    w.resize(470, 430)
    w.show()
    app.processEvents()

    img = w.grab().toImage()
    a = analyze(img)
    arr = a["array"]
    h, wd = arr.shape[:2]
    print("rendered size:", (wd, h))

    # Center of the canvas should be white (255,255,255).
    cy, cx = h // 2, wd // 2
    print("canvas center pixel:", tuple(int(v) for v in arr[cy, cx]))

    # A few px inside the top-left card border should be dark (the card bg).
    print("card edge pixel (15,15):", tuple(int(v) for v in arr[15, 15]))
    print("corner pixel (3,3):", tuple(int(v) for v in arr[3, 3]))

    # Candidate wiring: feed candidates, check buttons are created.
    w._show_candidates([("中", 0.95), ("申", 0.03), ("虫", 0.01)])
    labels = []
    for i in range(w.cand_row.count()):
        it = w.cand_row.itemAt(i)
        if it.widget() and isinstance(it.widget(), QPushButton):
            labels.append(it.widget().text())
    print("candidate buttons:", labels)

    # Canvas stroke state toggles.
    assert w.canvas.has_strokes() is False
    ok = (
        arr[cy, cx].tolist() == [255, 255, 255]
        and arr[15, 15][0] < 80
        and labels[:1] == ["中"]
    )
    print("RESULT:", "PASS" if ok else "FAIL")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
