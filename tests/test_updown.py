"""Verify Up/Down selection: Down moves to candidate 2, confirm inserts it."""
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
    ui = UInput(cap, name="ow-updown", version=0x3)
    time.sleep(0.3)

    cx, cy = at[0] + 210, at[1] + 200
    move_to(cx, cy); time.sleep(0.15)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1); ui.syn(); time.sleep(0.06)
    for _ in range(8):
        ui.write(ecodes.EV_REL, ecodes.REL_X, 38); ui.syn(); time.sleep(0.04)
    ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0); ui.syn()
    ui.close()
    time.sleep(1.0)  # after recognition (~0.7s) but before auto-fill (~1.9s)

    print("active after recognition:", active(), flush=True)

    # Down arrow -> next candidate, then confirm
    sh(["wtype", "-d", "40", "-k", "Down"])
    time.sleep(0.2)
    sh(["omarchy-write-insert"])  # SIGUSR2 = confirm current selection
    time.sleep(0.6)

    clip = sh(["wl-paste"]).stdout.strip()
    print("after Down+confirm -> clipboard:", repr(clip), "active:", active(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
