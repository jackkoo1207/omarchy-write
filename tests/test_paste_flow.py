"""Full paste flow: draw '一', click first candidate, verify clipboard + refocus."""
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


def read_log_tail():
    try:
        with open(LOG) as f:
            return f.read().strip()
    except Exception:
        return ""


def main() -> int:
    at = window_at()
    if at is None:
        print("FAIL: window not found", flush=True)
        return 1

    # focus Hermes so the tracker captures it
    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:Hermes' })"])
    time.sleep(1.2)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-paste", version=0x3)
    time.sleep(0.3)

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    # draw '一' (horizontal line) on canvas
    cx, cy = at[0] + 210, at[1] + 200
    move_to(cx, cy)
    time.sleep(0.15)
    btn(1)
    time.sleep(0.06)
    for _ in range(8):
        rel(38, 0)
        time.sleep(0.04)
    btn(0)
    time.sleep(2.2)  # recognition + debounce

    # find first candidate position from the log
    log = read_log_tail()
    cand = None
    for line in log.splitlines():
        if line.startswith("cand0 global"):
            cand = tuple(int(v) for v in line.split("cand0 global ")[1].split(","))
    if cand is None:
        print("FAIL: no cand0 position in log; log was:\n", log, flush=True)
        return 1
    print("candidate at", cand, flush=True)

    # click the first candidate
    move_to(cand[0], cand[1])
    time.sleep(0.2)
    ui.close()
    ui2 = UInput({ecodes.EV_KEY: [ecodes.BTN_LEFT]}, name="ow-paste-click", version=0x3)
    time.sleep(0.3)
    ui2.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 1)
    ui2.syn()
    time.sleep(0.08)
    ui2.write(ecodes.EV_KEY, ecodes.BTN_LEFT, 0)
    ui2.syn()
    time.sleep(0.6)
    ui2.close()

    clip = sh(["wl-paste"]).stdout.strip()
    active = sh(["hyprctl", "activewindow", "-j"]).stdout
    active_class = json.loads(active).get("class") if active else "?"
    print("clipboard:", repr(clip), flush=True)
    print("activewindow:", active_class, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
