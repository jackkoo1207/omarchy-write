#!/usr/bin/env bash
# Install the Python backend for the Omarchy Handwrite board plugin.
# Run once after `omarchy plugin add <repo-url>` (or a manual drop-in).
#
# The Omarchy plugin system only clones/validates files — it never installs
# Python dependencies or udev rules, so those live here. Safe to re-run.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${PYTHON:-python3}"

echo "== Omarchy Handwrite board: installing backend =="

# 1. Python venv with the OCR + touchpad dependencies.
if [ ! -x "$PLUGIN_DIR/.venv/bin/python" ]; then
  echo "  creating venv..."
  "$PYTHON" -m venv "$PLUGIN_DIR/.venv"
fi
"$PLUGIN_DIR/.venv/bin/pip" install --quiet --upgrade pip
"$PLUGIN_DIR/.venv/bin/pip" install --quiet onnxruntime numpy pillow evdev
echo "  venv ready at .venv/"

# 2. udev rules: touchpad capture + /dev/uinput access.
if [ "$(id -u)" -eq 0 ]; then
  cp "$PLUGIN_DIR/udev/99-omarchy-write-touchpad.rules" /etc/udev/rules.d/
  cp "$PLUGIN_DIR/udev/99-omarchy-write-uinput.rules" /etc/udev/rules.d/
  udevadm control --reload
  udevadm trigger
  echo "  udev rules installed"
else
  echo "  udev rules need root — run:"
  echo "    sudo cp $PLUGIN_DIR/udev/*.rules /etc/udev/rules.d/"
  echo "    sudo udevadm control --reload && sudo udevadm trigger"
fi

echo "Done. Enable the plugin and set up the hotkeys (see README)."
