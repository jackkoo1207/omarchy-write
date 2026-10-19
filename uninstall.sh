#!/usr/bin/env bash
# Remove the Omarchy Handwrite board backend (venv + udev rules).
# Run before `omarchy plugin remove jack.omarchy-write`.
set -euo pipefail

PLUGIN_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo "== Omarchy Handwrite board: removing backend =="

rm -rf "$PLUGIN_DIR/.venv"
echo "  venv removed"

if [ "$(id -u)" -eq 0 ]; then
  rm -f /etc/udev/rules.d/99-omarchy-write-touchpad.rules \
        /etc/udev/rules.d/99-omarchy-write-uinput.rules
  udevadm control --reload
  echo "  udev rules removed"
else
  echo "  udev rules need root to remove — run:"
  echo "    sudo rm -f /etc/udev/rules.d/99-omarchy-write-*.rules"
  echo "    sudo udevadm control --reload"
fi

echo "Done. Remove the plugin with: omarchy plugin remove jack.omarchy-write"
