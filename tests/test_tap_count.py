"""Count how many selection-moves a single arrow tap produces."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from evdev import UInput, ecodes

LOG = os.path.expanduser("~/.config/omarchy-write/touchpad.log")


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
    ui = UInput(cap, name="ow-tap", version=0x3)
    time.sleep(0.3)

    cx, cy = at[0] + 210, at[1] + 200
    move_to(cx, cy)
    time.sleep(0.15)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1); ui.syn()
    time.sleep(0.06)
    for _ in range(8):
        ui.write(ecodes.EV_REL, ecodes.REL_X, 38); ui.syn(); time.sleep(0.04)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0); ui.syn()
    ui.close()
    time.sleep(2.3)

    # clear log, then ONE right tap
    open(LOG, "w").close()
    sh(["wtype", "-d", "40", "-k", "Right"])
    time.sleep(0.5)

    moves = 0
    lines = []
    try:
        with open(LOG) as f:
            lines = f.read().splitlines()
    except Exception:
        pass
    moves = sum(1 for l in lines if l.startswith("move"))
    print(f"move count after ONE Right tap: {moves}", flush=True)
    for l in lines:
        print("  ", l, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
