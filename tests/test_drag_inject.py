"""Inject a real drag on the header: cursor.move to position, BTN down, REL moves, BTN up."""
from __future__ import annotations

import subprocess
import sys
import time

from evdev import UInput, ecodes


def main() -> int:
    # Position cursor on the header (title area, left side).
    subprocess.run(
        ["hyprctl", "dispatch", "hl.dsp.cursor.move({ x = 700, y = 265 })"],
        timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.3)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-test-drag", version=0x3)
    time.sleep(0.3)

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
    ui.syn()
    time.sleep(0.15)
    for _ in range(4):
        rel(40, 25)  # move right+down; window should follow
        time.sleep(0.05)
    time.sleep(0.15)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
    ui.syn()
    time.sleep(0.3)
    ui.close()
    print("drag injected", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
