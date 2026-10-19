"""Verify: (1) window stays fixed-size when candidates appear, (2) signal-based
candidate insert (Super+Enter/Super+N equivalent) works."""
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


def window_info():
    out = sh(["hyprctl", "clients", "-j"]).stdout
    for x in json.loads(out):
        if x.get("class") == "omarchy-write":
            return x.get("at"), x.get("size")
    return None, None


def main() -> int:
    at, size = window_info()
    print("window before:", at, size, flush=True)
    if at is None:
        print("FAIL: window not found", flush=True)
        return 1

    sh(["hyprctl", "dispatch", "hl.dsp.focus({ window = 'class:Hermes' })"])
    time.sleep(1.2)

    cap = {ecodes.EV_KEY: [ecodes.BTN_LEFT], ecodes.EV_REL: [ecodes.REL_X, ecodes.REL_Y]}
    ui = UInput(cap, name="ow-auto", version=0x3)
    time.sleep(0.3)

    def rel(dx, dy):
        ui.write(ecodes.EV_REL, ecodes.REL_X, dx)
        ui.write(ecodes.EV_REL, ecodes.REL_Y, dy)
        ui.syn()

    def btn(v):
        ui.write(ecodes.EV_KEY, ecodes.BTN_LEFT, v)
        ui.syn()

    # draw a horizontal stroke
    cx, cy = at[0] + 210, at[1] + 200
    move_to(cx, cy)
    time.sleep(0.15)
    btn(1)
    time.sleep(0.06)
    for _ in range(8):
        rel(38, 0)
        time.sleep(0.04)
    btn(0)
    time.sleep(2.3)  # recognition + debounce
    ui.close()

    at2, size2 = window_info()
    print("window after (candidates shown):", at2, size2, flush=True)
    print("size stable:", size == size2, flush=True)

    # insert top candidate via signal (== Super+Enter / Super+1)
    r = sh(["omarchy-write-insert", "1"])
    time.sleep(0.6)
    clip = sh(["wl-paste"]).stdout.strip()
    active = sh(["hyprctl", "activewindow", "-j"]).stdout
    active_class = json.loads(active).get("class") if active else "?"
    print("insert1 rc=", r.returncode, "clipboard=", repr(clip), "active=", active_class, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
