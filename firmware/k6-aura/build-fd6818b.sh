#!/bin/sh
# Experimental FD6818B Aura builds: EXPLORE or compact normal-Aura Blowfang host.
# The legacy Blowfang FSK packet modem is disabled until ported and hardware-tested.
set -eu
HERE=$(cd "$(dirname "$0")" && pwd)
ROOT=$(cd "$HERE/../.." && pwd)
REPO=${AURA_REPO:-https://github.com/sophiel-meow/bf-k61-firmware-aura}
REV=${AURA_FD6818B_REV:-c3aeb17aec0fd09dccf931b52f6c7d5dbf72e7ac}
WORK="$HERE/build/aura-fd6818b-port"
OUT="$HERE/out-fd6818b"
FEATURES=${K6_AURA_FEATURES:-pager-explore,fd6818b,spilib,txdog}
IMAGE=${K6_IMAGE_NAME:-aura-fd6818b-explore}

if [ ! -d "$WORK/.git" ]; then
  git clone -q "$REPO" "$WORK"
  git -C "$WORK" checkout -q --detach "$REV"
fi
[ "$(git -C "$WORK" rev-parse HEAD)" = "$REV" ] || {
  echo "checkout at $WORK is not pinned to $REV; preserve it and choose another AURA_FD6818B_REV" >&2
  exit 1
}
if [ ! -f "$WORK/src/app/pager.rs" ]; then
  git -C "$WORK" apply "$HERE/aura-pager.patch"
  git -C "$WORK" apply "$HERE/aura-pager-fd6818b.patch"
fi
if ! grep -q 'read_bytes_checked' "$WORK/src/drivers/norflash.rs"; then
  git -C "$WORK" apply "$HERE/aura-norflash-timeout.patch"
fi
if ! grep -q 'mod_fsk_rx_start' "$WORK/src/app/pager.rs"; then
  git -C "$WORK" apply "$HERE/aura-fd6818b-fsk-api.patch"
fi
if ! grep -q 'MOD_EXIT_TO_AURA' "$WORK/src/app/pager.rs"; then
  git -C "$WORK" apply "$HERE/aura-exit-to-aura.patch"
fi
if ! grep -q 'Two-line message for full Aura builds' "$WORK/src/ui/cps.rs"; then
  git -C "$WORK" apply "$HERE/aura-full-radio.patch"
fi
case ",$FEATURES," in
  *,blowfang-host,*)
    if ! grep -q 'blowfang-host' "$WORK/Cargo.toml"; then
      if [ ! -s "$HERE/aura-blowfang-host.patch" ]; then
        echo "missing Aura patch required for the blowfang-host feature" >&2
        exit 1
      fi
      git -C "$WORK" apply "$HERE/aura-blowfang-host.patch"
    fi
    ;;
esac
if ! grep -q 'PXK6 card data uses explicit commands' "$WORK/src/cps/mod.rs"; then
  git -C "$WORK" apply "$HERE/aura-card-cable.patch"
fi
python3 "$HERE/apply-fd6818b-fsk-tx-api.py"
python3 "$HERE/apply-fd6818b-afsk-module-api.py"
python3 "$HERE/apply-fd6818b-kiss-api.py"
python3 "$HERE/apply-module-settings-api.py"
python3 "$HERE/apply-action-beep.py"
python3 "$HERE/apply-surf-vfo-b.py"
python3 "$HERE/apply-managed-signal-api.py"
python3 "$HERE/apply-explore-header-api.py"
python3 "$HERE/apply-explore-engine-api.py"
python3 "$HERE/apply-vfo-repeater-hint.py"
python3 "$HERE/apply-module-run-diag.py"
python3 "$HERE/apply-cw-bk-in-only.py"
python3 "$HERE/apply-cw-hang-timing.py"
python3 "$HERE/apply-module-power-off.py"
python3 "$HERE/apply-host-module-screen.py"
python3 "$HERE/apply-explore-ui-api.py"
python3 "$HERE/apply-boot-app-stack.py"
python3 "$HERE/apply-cardlink-stack.py"
python3 "$HERE/apply-cable-stack.py"
python3 "$HERE/trim-generated-host.py"
if [ "${K6_MODULE_REMOVE:-0}" = 1 ]; then
  python3 "$HERE/apply-library-erase.py"
fi
case ",$FEATURES," in
  *,blowfang-host,*)
    python3 "$HERE/apply-blowfang-host.py"
    python3 "$HERE/apply-vfo-focus.py"
    python3 "$HERE/apply-band-surf-shortcut.py"
    python3 "$HERE/apply-status-callsign.py"
    ;;
esac
grep -q 'FD6818B FSK TBD' "$WORK/src/ui/pager.rs" || {
  echo "FD6818B overlay is missing from $WORK; inspect that checkout before building" >&2
  exit 1
}

mkdir -p "$OUT"
K6_EXPLORE_HOST=0
case ",$FEATURES," in *,blowfang-host,*) K6_EXPLORE_HOST=1 ;; esac
K6_EXPLORE_HOST="$K6_EXPLORE_HOST" K6_SCAN_SERVICE="${K6_SCAN_SERVICE:-1}" K6_PKT_YIELD=0 K6_VOICE=0 K6_CB=spi \
  K6_OUT="$OUT/c-build" sh "$ROOT/tools/k6_build.sh"
mkdir -p "$WORK/lib"
cp "$OUT/c-build/libsotto_k6.a" "$WORK/lib/libsotto_k6.a"
(cd "$WORK" && cargo build --release --features "$FEATURES")
ELF="$WORK/target/thumbv6m-none-eabi/release/aura"
llvm-size -A "$ELF" > "$OUT/size.txt"
FLASH=$(awk '$1==".vector_table" || $1==".text" || $1==".rodata" || $1==".gnu.sgstubs" || $1==".k6_id" || $1==".data" {n += $2} END {print n+0}' "$OUT/size.txt")
if [ "$FLASH" -gt 122880 ]; then
  echo "image needs $FLASH bytes; KD32F328 application limit is 122880 bytes" >&2
  exit 1
fi
llvm-objcopy -O binary "$ELF" "$OUT/$IMAGE.bin"
sha256sum "$OUT/$IMAGE.bin" | tee "$OUT/$IMAGE.bin.sha256"
case ",$FEATURES," in
  *,blowfang-host,*) python3 "$HERE/build-vfo-module-bundle.py" --out "$OUT/vfo-module-bundle" ;;
esac
if [ -n "${K6_MOD_KEY_FILE:-}" ]; then
  echo "Built keyed FD6818B image with features: $FEATURES"
else
  echo "Built unkeyed FD6818B image with features: $FEATURES; it refuses every module."
fi
