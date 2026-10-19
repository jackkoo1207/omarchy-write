"""Stress the app: repeated drags + draws, then verify it's still alive."""
from __future__ import annotations

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
    import json
    for x in json.loads(out):
        if x.get("class") == "omarchy-write":
            return x.get("at")
    return None


def main() -> int:
    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-stress", version=0x3)
    time.sleep(0.3)

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    for i in range(6):
        at = window_at()
        if at is None:
            print(f"[{i}] window gone (crashed?)", flush=True)
            return 1
        # drag from header
        hx, hy = at[0] + 80, at[1] + 15
        move_to(hx, hy)
        time.sleep(0.15)
        btn(1)
        time.sleep(0.08)
        for _ in range(3):
            rel(30, 20 if i % 2 else -20)
            time.sleep(0.04)
        btn(0)
        time.sleep(0.2)
        # draw a quick stroke on canvas
        cx, cy = at[0] + 200, at[1] + 200
        move_to(cx, cy)
        time.sleep(0.1)
        btn(1)
        time.sleep(0.05)
        for _ in range(3):
            rel(40, 0)
            time.sleep(0.04)
        btn(0)
        time.sleep(0.6)
        print(f"[{i}] ok, window at {window_at()}", flush=True)

    ui.close()
    print("stress done, window at", window_at(), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
