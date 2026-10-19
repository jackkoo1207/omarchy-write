"""Clean click: cursor.move for absolute positioning, UInput for the button only."""
from __future__ import annotations

import subprocess
import sys
import time

from evdev import UInput, ecodes


def cursorpos():
    out = subprocess.run(["hyprctl", "cursorpos"], capture_output=True, text=True, timeout=3)
    return out.stdout.strip()


def main() -> int:
    tx, ty = 700, 463
    subprocess.run(
        ["hyprctl", "dispatch", f"hl.dsp.cursor.move({{ x = {tx}, y = {ty} }})"],
        timeout=3, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    time.sleep(0.3)
    print("cursorpos after move:", cursorpos(), flush=True)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT]}
    ui = UInput(cap, name="ow-test-btn", version=0x3)
    time.sleep(0.3)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
    ui.syn()
    time.sleep(0.12)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
    ui.syn()
    time.sleep(0.3)
    ui.close()
    print("click done; cursorpos:", cursorpos(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
