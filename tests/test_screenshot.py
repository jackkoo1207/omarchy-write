"""Draw a character and screenshot while candidates are showing (for visual
verification of the candidate rendering)."""
from __future__ import annotations

import json
import subprocess
import sys
import time

from evdev import UInput, ecodes


def sh(cmd):
    return subprocess.run(cmd, capture_output=True, text=True, timeout=3)


def move_to(x, y):
    sh(["hyprctl", "dispatch", f"hl.dsp.cursor.move({{ x = {x}, y = {y} }})"])


def window_at():
    out = sh(["hyprctl", "clients", "-j"]).stdout
    for x in json.loads(out):
        if x.get("class") == "omarchy-write":
            return x.get("at")
    return None


def main() -> int:
    at = window_at()
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:omarchy-write' })"])
    time.sleep(0.4)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-shot", version=0x3)
    time.sleep(0.3)

    cx, cy = at[0] + 210, at[1] + 190

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    # horizontal stroke
    move_to(cx - 70, cy); time.sleep(0.12)
    btn(1); time.sleep(0.05)
    for _ in range(5):
        rel(28, 0); time.sleep(0.04)
    btn(0)
    # vertical stroke
    move_to(cx, cy - 70); time.sleep(0.1)
    btn(1); time.sleep(0.05)
    for _ in range(5):
        rel(0, 28); time.sleep(0.04)
    btn(0)
    ui.close()

    # wait for recognition (700ms) but before auto-fill (1.9s)
    time.sleep(1.0)
    subprocess.run(["grim", "-g", f"{at[0]},{at[1]} 470x430", "/tmp/ow_candidates.png"])
    print("screenshot saved to /tmp/ow_candidates.png", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
