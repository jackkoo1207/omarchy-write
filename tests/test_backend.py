"""End-to-end test of the QML-plugin backend (stdio JSON protocol)."""
from __future__ import annotations

import json
import select
import subprocess
import sys
import time

HERE = "/home/jack/Projects/omarchy-write"


def main() -> int:
    proc = subprocess.Popen(
        [".venv/bin/python", "backend.py"],
        cwd=HERE,
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    def send(obj):
        proc.stdin.write(json.dumps(obj) + "\n")
        proc.stdin.flush()

    def read_line(timeout=3.0):
        r, _, _ = select.select([proc.stdout], [], [], timeout)
        if r:
            return proc.stdout.readline().strip()
        return None

    # wait for model ready
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        line = read_line(1.0)
        if line:
            print("OUT:", line)
            if '"ready"' in line or "載入失敗" in line:
                break

    send({"type": "show"})
    time.sleep(0.3)

    # draw a horizontal stroke (should read as a one-stroke char)
    for i in range(6):
        phase = "down" if i == 0 else "move"
        send({"type": "stroke", "phase": phase, "x": 0.3 + i * 0.08, "y": 0.5})
    send({"type": "stroke", "phase": "up"})

    # wait for candidates
    deadline = time.monotonic() + 5
    while time.monotonic() < deadline:
        line = read_line(1.0)
        if line:
            print("OUT:", line)
            if '"candidates"' in line:
                break

    send({"type": "confirm"})
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        line = read_line(1.0)
        if line:
            print("OUT:", line)

    proc.stdin.close()
    proc.terminate()
    proc.wait(timeout=3)
    return 0


if __name__ == "__main__":
    sys.exit(main())
