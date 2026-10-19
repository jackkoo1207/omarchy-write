"""Confirm the current selection in the running Omarchy Write app (via signal).

Usage: omarchy-write-insert

Sends SIGUSR2; the app inserts the currently-highlighted candidate (moved with
the left/right arrow keys) into the previously focused app.
"""
from __future__ import annotations

import os
import signal
import sys

PIDFILE = os.path.expanduser("~/.config/omarchy-write/run.pid")


def _running_pid() -> int | None:
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
    except Exception:  # noqa: BLE001
        return None
    try:
        # Verify the pid belongs to our app (avoid signalling a recycled pid).
        with open(f"/proc/{pid}/cmdline", "rb") as f:
            cmd = f.read().decode("utf-8", "replace")
        if "omarchy-write" not in cmd and "omarchy_write" not in cmd:
            return None
        os.kill(pid, 0)
        return pid
    except (ProcessLookupError, PermissionError, FileNotFoundError):
        return None


def main() -> int:
    pid = _running_pid()
    if pid is None:
        return 1
    try:
        os.kill(pid, signal.SIGUSR2)
        return 0
    except Exception:  # noqa: BLE001
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
