"""Standalone touchpad reader process — evdev isolated from Qt.

Reads raw multitouch events, normalizes coordinates to [0,1], and prints one
event per line to stdout:

    ready
    down <x> <y>
    move <x> <y>
    up
    error <message>

The parent app spawns this with ``python -m omarchy_write.touchpad_reader``
and reads its stdout. Running evdev in its own process avoids the refcount
crash that occurred when evdev shared the Qt process.
"""
from __future__ import annotations

import glob
import os
import sys

from evdev import InputDevice, ecodes

TOUCHPAD_HINT = "touchpad"


def find_device() -> str | None:
    for name_file in glob.glob("/sys/class/input/event*/device/name"):
        try:
            with open(name_file) as f:
                name = f.read().strip()
        except OSError:
            continue
        if TOUCHPAD_HINT in name.lower():
            return "/dev/input/" + os.path.basename(name_file.split("/device/name")[0])
    return None


def main() -> int:
    # Die with the parent: if the app process exits, the kernel sends us
    # SIGTERM so we never linger holding the touchpad grab.
    try:
        import ctypes
        import signal as _signal

        libc = ctypes.CDLL("libc.so.6", use_errno=True)
        libc.prctl(1, _signal.SIGTERM)  # PR_SET_PDEATHSIG = 1
    except Exception:  # noqa: BLE001
        pass

    path = find_device()
    if path is None:
        print("error 找不到觸控板裝置", flush=True)
        return 1
    try:
        dev = InputDevice(path)
        x_info = dev.absinfo(ecodes.ABS_MT_POSITION_X)
        y_info = dev.absinfo(ecodes.ABS_MT_POSITION_Y)
        dev.grab()
    except Exception as e:  # noqa: BLE001
        print(f"error 無法讀取觸控板：{e}", flush=True)
        return 1

    def norm(v, info) -> float:
        if info.max == info.min:
            return 0.0
        return max(0.0, min(1.0, (v - info.min) / (info.max - info.min)))

    print("ready", flush=True)

    tracking = -1
    lx = ly = None
    pending_down = False
    try:
        for event in dev.read_loop():
            if event.type != ecodes.EV_ABS:
                continue
            if event.code == ecodes.ABS_MT_TRACKING_ID:
                if event.value == -1:
                    print("up", flush=True)
                    tracking, lx, ly = -1, None, None
                    pending_down = False
                else:
                    tracking = event.value
                    pending_down = True
            elif event.code == ecodes.ABS_MT_POSITION_X:
                lx = norm(event.value, x_info)
                if tracking != -1:
                    if pending_down and ly is not None:
                        print(f"down {lx:.4f} {ly:.4f}", flush=True)
                        pending_down = False
                    elif not pending_down and ly is not None:
                        print(f"move {lx:.4f} {ly:.4f}", flush=True)
            elif event.code == ecodes.ABS_MT_POSITION_Y:
                ly = norm(event.value, y_info)
                if tracking != -1:
                    if pending_down and lx is not None:
                        print(f"down {lx:.4f} {ly:.4f}", flush=True)
                        pending_down = False
                    elif not pending_down and lx is not None:
                        print(f"move {lx:.4f} {ly:.4f}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"error {e}", flush=True)
        return 1
    finally:
        try:
            dev.ungrab()
        except Exception:  # noqa: BLE001
            pass
        try:
            dev.close()
        except Exception:  # noqa: BLE001
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
