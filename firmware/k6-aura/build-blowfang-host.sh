#!/bin/sh
# Build Aura's normal VFO/channel radio with the small sideloaded-module launcher.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
if [ -z "${K6_MOD_KEY_FILE:-}" ]; then
  K6_MOD_KEY_FILE="$HOME/.config/blowfang/k6-mod.key"
fi
if [ ! -r "$K6_MOD_KEY_FILE" ]; then
  echo "module key not readable: $K6_MOD_KEY_FILE (set K6_MOD_KEY_FILE to the key used when signing modules)" >&2
  exit 1
fi
export K6_MOD_KEY_FILE
# Keep the transmitter watchdog enabled while omitting only its boot-time debug line;
# the compact radio image is close to the MCU flash limit.
K6_AURA_FEATURES=blowfang-host,fd6818b,lean,spilib,txdog-quiet \
K6_IMAGE_NAME=aura-fd6818b-blowfang-host \
  sh "$HERE/build-fd6818b.sh"
python3 "$HERE/build-cardlink-module.py" --out "$HERE/out-fd6818b/cardlink-module-bundle"
