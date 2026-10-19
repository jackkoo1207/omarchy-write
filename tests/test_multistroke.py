"""Verify multi-stroke: draw a cross (horizontal + vertical) with a 600ms gap
between strokes. The fix should prevent premature recognition, so the final
result reflects BOTH strokes, not just the first."""
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
    if at is None:
        print("FAIL: window not found", flush=True)
        return 1

    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:Hermes' })"])
    time.sleep(1.2)
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:omarchy-write' })"])
    time.sleep(0.4)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-multi", version=0x3)
    time.sleep(0.3)

    cx, cy = at[0] + 210, at[1] + 190

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    # stroke 1: horizontal
    move_to(cx - 70, cy)
    time.sleep(0.12)
    btn(1); time.sleep(0.05)
    for _ in range(5):
        rel(28, 0); time.sleep(0.04)
    btn(0)

    # gap of 600ms — would have triggered premature recognition with the old
    # 450ms debounce (no cancel-on-new-stroke)
    time.sleep(0.6)

    # stroke 2: vertical, crossing stroke 1
    move_to(cx, cy - 70)
    time.sleep(0.12)
    btn(1); time.sleep(0.05)
    for _ in range(5):
        rel(0, 28); time.sleep(0.04)
    btn(0)
    ui.close()

    # wait for recognition (700ms debounce) + auto-fill (1200ms) + margin
    time.sleep(2.4)

    clip = sh(["wl-paste"]).stdout.strip()
    print("clipboard after 2-stroke cross:", repr(clip), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
