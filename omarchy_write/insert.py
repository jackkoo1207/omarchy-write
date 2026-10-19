"""Insert recognized text into the previously focused app on Wayland.

Strategy: copy to clipboard, refocus the app the user was typing in (its
Hyprland window address), wait until that focus actually lands, then send
Ctrl+V with wtype.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time

DEBUG_LOG = os.path.expanduser("~/.config/omarchy-write/insert.log")


def _dbg(msg: str) -> None:
    try:
        with open(DEBUG_LOG, "a") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {msg}\n")
    except Exception:
        pass


def copy_to_clipboard(text: str) -> None:
    if not text:
        return
    if not shutil.which("wl-copy"):
        return
    try:
        subprocess.run(["wl-copy", "--", text], timeout=3)
    except Exception:  # noqa: BLE001
        pass
    try:
        subprocess.run(["wl-copy", "--primary", "--", text], timeout=3)
    except Exception:  # noqa: BLE001
        pass


def paste() -> None:
    if not shutil.which("wtype"):
        return
    try:
        subprocess.run(
            ["wtype", "-s", "60", "-M", "ctrl", "-k", "v", "-m", "ctrl"],
            timeout=3,
        )
    except Exception:  # noqa: BLE001
        pass


def focus_window(address: str | None) -> bool:
    """Focus the given window. Returns True if the focus landed on it."""
    if not address:
        return False
    try:
        r = subprocess.run(
            ["hyprctl", "dispatch", f"hl.dsp.focus({{ window = 'address:{address}' }})"],
            capture_output=True, text=True, timeout=2,
        )
        _dbg(f"focus cmd rc={r.returncode} out={r.stdout.strip()!r} err={r.stderr.strip()!r}")
    except Exception as exc:  # noqa: BLE001
        _dbg(f"focus cmd EXC {exc!r}")
        return False
    # Wait until Hyprland actually reports the target as active (the dispatch is
    # async with the compositor's focus propagation).
    deadline = time.monotonic() + 0.3
    while time.monotonic() < deadline:
        act = _active_address()
        if act == address:
            return True
        time.sleep(0.02)
    _dbg(f"focus TIMEOUT active={_active_address()}")
    return _active_address() == address


def _active_address() -> str | None:
    try:
        out = subprocess.run(
            ["hyprctl", "activewindow", "-j"],
            capture_output=True, text=True, timeout=1,
        )
        return json.loads(out.stdout).get("address")
    except Exception:  # noqa: BLE001
        return None


def insert_text(text: str, focus_addr: str | None = None) -> None:
    copy_to_clipboard(text)
    if focus_addr:
        ok = focus_window(focus_addr)
        _dbg(f"insert {text!r} -> {focus_addr} focused={ok} active={_active_address()}")
    else:
        _dbg(f"insert {text!r} -> NO target (prev_addr is None!)")
    paste()
