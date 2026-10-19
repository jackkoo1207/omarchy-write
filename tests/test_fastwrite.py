"""Verify commit-on-new-stroke: write char 1, then char 2 before auto-fill.
Char 1 should be committed (inserted) when char 2's stroke starts, so strokes
don't pile up."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

from evdev import UInput, ecodes

LOG = os.path.expanduser("~/.config/omarchy-write/insert.log")


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
        print("FAIL: no window", flush=True)
        return 1

    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:Hermes' })"])
    time.sleep(1.2)
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:omarchy-write' })"])
    time.sleep(0.4)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-fast", version=0x3)
    time.sleep(0.3)

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    def hline(cx, cy):
        move_to(cx, cy); time.sleep(0.1)
        btn(1); time.sleep(0.05)
        for _ in range(6):
            rel(32, 0); time.sleep(0.04)
        btn(0)

    cx = at[0] + 210
    hline(cx, at[1] + 150)   # char 1 (top)
    time.sleep(0.9)           # recognition done, candidates showing, auto-fill pending
    hline(cx, at[1] + 250)   # char 2 (bottom) -> should commit char 1 first
    ui.close()
    time.sleep(2.2)           # char 2 recognition + auto-fill

    print("=== insert.log ===", flush=True)
    try:
        print(open(LOG).read().strip() or "(empty)", flush=True)
    except Exception:
        print("(no log)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
