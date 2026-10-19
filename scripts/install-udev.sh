#!/usr/bin/env bash
# Install udev rules granting jack access to the touchpad and /dev/uinput.
set -euo pipefail
DIR="$(dirname "$(dirname "$(readlink -f "$0")")")/udev"
cp "$DIR/99-omarchy-write-touchpad.rules" /etc/udev/rules.d/99-omarchy-write-touchpad.rules
cp "$DIR/99-omarchy-write-uinput.rules" /etc/udev/rules.d/99-omarchy-write-uinput.rules
udevadm control --reload
udevadm trigger
echo "udev rules installed and triggered."
