# AG7SU Blowfang

AG7SU Blowfang is a standalone firmware and module project for the Baofeng UV-K6/K61 with the
FD6818B RF chip. The active target is **normal Aura VFO/channel operation with a Blowfang module
launcher**, plus the module loader, local Git-backed catalog, and tools to build, simulate, install,
and manage modules.

This repository is intentionally scoped to that host and its module ecosystem. The experimental
VOICE MSG / sotto pager, Explore firmware image, and unrelated UV-380/OpenRTX port are outside the
current target. When one of those efforts is resumed, bring the needed upstream code and changes in
then. Shared K6 code and fixtures that the host build or module workflow still depends on remain
here.

## Build the Aura host

The build fetches the pinned Aura source, applies the FD6818B and Blowfang host patches, then builds
the host image and the bundled starter modules. You need Rust's `thumbv6m-none-eabi` target, clang,
LLD, LLVM tools, Python 3, and the module signing key used by this radio:

```sh
K6_MOD_KEY_FILE="$HOME/.config/blowfang/k6-mod.key" \
  sh firmware/k6-aura/build-blowfang-host.sh
```

Outputs are written under `firmware/k6-aura/out-fd6818b/`:

- `aura-fd6818b-blowfang-host.bin` — Aura radio with the **BLOWFANG** launcher entry.
- `vfo-module-bundle/` — SURF and VFO starter modules.
- `cardlink-module-bundle/` — optional CARD LINK module.

On the radio, open Aura's launcher and select **BLOWFANG**. **AURA RADIO** returns to normal Aura
VFO/channel operation; the other rows launch installed modules. V/M or A/B returns from the module
menu to Aura.

The image must be keyed with the same local key used to sign modules at install time. Keep that key
private and out of Git. The radio loader verifies signatures but does not sandbox native modules.

## Install and manage modules

The catalog can display Git-hosted or local module repositories, show README screenshots, and install
compatible bundles over the programming cable:

```sh
python3 -m pip install -r tools/k6_store_requirements.txt
python3 tools/k6_store.py add https://github.com/OWNER/K6-MODULE --ref main
python3 tools/k6_store.py serve
```

Open <http://127.0.0.1:5055> and choose **My radio** to inspect, install, or remove modules. The
CLI and bundle format are documented in [`docs/module-store.md`](docs/module-store.md); the cable
installer is [`tools/k6_install.py`](tools/k6_install.py).

## Working on modules and the host

- [`firmware/k6-aura/`](firmware/k6-aura/) contains the pinned Aura build, host overlay, and module
  bundle builders.
- [`c/k6/k6_mod.c`](c/k6/k6_mod.c), [`c/k6/k6_lib.c`](c/k6/k6_lib.c), and
  [`docs/k6-modules.md`](docs/k6-modules.md) define the signed module and SPI library contract.
- [`local-modules/`](local-modules/) is generated locally by `python3 tools/k6_make_local_catalog.py`;
  these build outputs are ignored by Git.
- [`sim/k6emu/`](sim/k6emu/) is the host-contract emulator used to iterate on module and library
  behavior without repeatedly flashing hardware.
- [`tests/`](tests/) covers the shared loader, catalog, emulator, and module tooling.

## Radio development workbench

Run the local IDE-style simulator for the K6 host image:

```sh
python3 -m pip install -r sim/k6emu/requirements.txt -r tools/k6_store_requirements.txt
python3 -m sim.k6ide
```

The server binds to `0.0.0.0:5056` by default. On the host, open
<http://127.0.0.1:5056>; from another device, use `http://<host-LAN-IP>:5056`. It has no login or
token and is intended for the trusted home LAN; do not expose it to the public internet.

The workbench runs the actual K6 firmware image in the emulator, shows its LCD and UART output,
maps keyboard and on-screen presses to the radio keypad, and offers modeled power/PTT lines. Enter
a bundle directory and signing key to stage modules in virtual SPI flash. Use
`--spi-image sim/k6emu/runs/k6-spi.bin` to retain that virtual library between workbench restarts;
this generated file is ignored by Git and may contain calibration copied into virtual flash. The
workbench never opens the programming cable.

This is the first radio backend, for UV-K6/K61 boards using the FD6818B RF chip. The interface
and catalog should become radio-model adapters as other board emulators are added; at this point
only the K6 execution and peripherals are implemented. Emulator evidence covers firmware behavior
against modeled peripherals, not RF performance or physical-radio behavior.

Start with the focused host and emulator notes in [`docs/k6-host-contract-findings.md`](docs/k6-host-contract-findings.md)
and [`docs/k6-emulator-llm-debug.md`](docs/k6-emulator-llm-debug.md). Hardware testing still means
testing on the actual FD6818B K6; an emulator pass is not a radio or RF test.

## Project boundary

This is the AG7SU project checkout, not the upstream Blowfang development tree. It keeps the pinned
Aura integration and the working host/module/store path together so that work can continue here
without pulling in unrelated radio ports. Upstream K6 components can be brought back selectively
when a feature needs them.
