"""Verify: panel takes focus (for arrows), left/right arrows move the candidate
selection, and Super+Z (SIGUSR2) inserts the currently-selected candidate."""
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


def active():
    out = sh(["hyprctl", "activewindow", "-j"]).stdout
    return json.loads(out).get("class") if out else "?"


def window_at():
    out = sh(["hyprctl", "clients", "-j"]).stdout
    for x in json.loads(out):
        if x.get("class") == "omarchy-write":
            return x.get("at")
    return None


def draw_horizontal(ui, at):
    cx, cy = at[0] + 210, at[1] + 200
    move_to(cx, cy)
    time.sleep(0.15)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1); ui.syn()
    time.sleep(0.06)
    for _ in range(8):
        ui.write(ecodes.EV_REL, ecodes.REL_X, 38); ui.syn(); time.sleep(0.04)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0); ui.syn()


def main() -> int:
    at = window_at()
    if at is None:
        print("FAIL: window not found", flush=True)
        return 1

    # 1. track Hermes
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:Hermes' })"])
    time.sleep(1.2)

    # 2. focus the panel (simulate summon)
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:omarchy-write' })"])
    time.sleep(0.4)
    print("active after focusing panel:", active(), flush=True)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-arrows", version=0x3)
    time.sleep(0.3)

    # 3. draw + recognize
    draw_horizontal(ui, at)
    time.sleep(2.3)
    ui.close()

    # 4. move selection right once, then confirm
    sh(["wtype", "-d", "30", "-P", "Right", "-p", "Right"])
    time.sleep(0.3)
    sh(["omarchy-write-insert"])  # SIGUSR2 -> confirm current selection
    time.sleep(0.6)
    clip = sh(["wl-paste"]).stdout.strip()
    print("after Right+confirm -> clipboard:", repr(clip), "active:", active(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
