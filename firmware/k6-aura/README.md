# Aura host firmware for the Baofeng K6

This directory builds the AG7SU FD6818B host image: Aura's normal VFO/channel radio with an entry
to the Blowfang module launcher. The current build deliberately omits the voice pager and Explore
application. The launcher opens **BLOWFANG**, where **AURA RADIO** returns to Aura and installed
library modules can be selected.

## Build

Required tools: Rust with `thumbv6m-none-eabi`, clang, LLD, LLVM binutils, Python 3, and the local
16-byte module signing key. The Aura checkout and revision are pinned in `build-fd6818b.sh`.

```sh
K6_MOD_KEY_FILE="$HOME/.config/blowfang/k6-mod.key" \
  sh firmware/k6-aura/build-blowfang-host.sh
```

The output directory is `firmware/k6-aura/out-fd6818b/`. The main artifact is
`aura-fd6818b-blowfang-host.bin`; module bundles are emitted beside it. Never commit the signing
key or generated `.bin` files.

`build-blowfang-host.sh` is the supported project build. `build.sh` and the other feature variants
are retained as references for upstream Aura integration work, not as the current radio target.
