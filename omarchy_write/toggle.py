"""Toggle the Omarchy Write window (launch if not running, show/hide if running)."""
from __future__ import annotations

import os
import signal
import subprocess

PIDFILE = os.path.expanduser("~/.config/omarchy-write/run.pid")


def _running_pid() -> int | None:
    try:
        with open(PIDFILE) as f:
            pid = int(f.read().strip())
    except Exception:  # noqa: BLE001
        return None
    try:
        # Verify the pid actually belongs to our app (avoid signalling a
        # recycled pid that reused our stale pidfile).
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
    if pid is not None:
        try:
            os.kill(pid, signal.SIGUSR1)
            return 0
        except Exception:  # noqa: BLE001
            pass
    # Launch via uwsm so Hyprland/Wayland manage it in a proper session scope.
    import shutil

    launch = ["omarchy-write"]
    if shutil.which("uwsm-app"):
        launch = ["uwsm-app", "--", "omarchy-write"]
    subprocess.Popen(
        launch,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
