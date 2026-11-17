# Flux

Flux is AG7SU firmware and a module catalog for the Baofeng UV-K6/K61 with the FD6818B RF chip. The firmware keeps normal VFO and channel operation, native Search, a module launcher labeled **Catalog**, and an About screen with the active feature set and flash space.

Optional feature sets add modules through the local Catalog. The **Scan** set bundles SURF and EXPLORE; APRS and Sotto remain separate module work. The boot screen supports voltage, message, or logo mode, with optional text alongside the logo.

The firmware is built from pinned upstream sources with Flux patches. Upstream names remain in source paths and protocol identifiers where compatibility or attribution requires them.

## Build

Install Rust with the `thumbv6m-none-eabi` target, clang, LLD, LLVM tools, and Python 3. Configure the 16-byte module signing key at `~/.config/flux/k6-mod.key`, then build through the unified CLI:

```sh
K6_MOD_KEY_FILE="$HOME/.config/flux/k6-mod.key" \
  python3 tools/k6.py build base
```

To build the base with Scan:

```sh
K6_MOD_KEY_FILE="$HOME/.config/flux/k6-mod.key" \
  python3 tools/k6.py build base scan
```

Builds go under `firmware/k6-aura/out-fd6818b/`. The FD6818B build script also remains available at `firmware/k6-aura/build-fd6818b.sh`. The build and planning tools do not write to a radio. Use `python3 tools/k6.py --help` for the available read-only, build, install, and flash commands.

## Local Catalog

The Catalog reads local or Git-hosted module repositories and can install compatible bundles over the programming cable. Start it with:

```sh
python3 -m pip install -r tools/k6_store_requirements.txt
python3 tools/k6.py catalog
```

Open <http://127.0.0.1:5055>. The web interface includes the Catalog, feature packs, device settings, and radio status. The CLI and catalog behavior are documented in [the Catalog guide](docs/module-store.md). The cable installer is [tools/k6_install.py](tools/k6_install.py).

## Simulator

Start the radio development workbench with:

```sh
python3 -m pip install -r sim/k6emu/requirements.txt -r tools/k6_store_requirements.txt
python3 -m sim.k6ide
```

It serves on port 5056 by default. Open <http://127.0.0.1:5056> locally. The workbench runs the firmware image in the K6 emulator, shows the display and UART output, and supports virtual keypad, power, and PTT input. Module bundles can be staged in virtual SPI flash. The simulator does not open a programming cable; emulator results do not verify RF or physical-radio behavior.

## Development map

- `firmware/k6-aura/` contains the pinned source build, Flux patches, and FD6818B feature-set build.
- `c/k6/` contains module and shared-library code; [docs/k6-modules.md](docs/k6-modules.md) describes the module API.
- `tools/k6.py` is the unified command line; `tools/k6_store.py` runs and manages the local Catalog.
- `local-modules/` contains generated local starter bundles and is ignored by Git.
- `sim/` and `tests/` contain the emulator and tooling validation.

For installation guidance, see [docs/manual/install.md](docs/manual/install.md). For deeper engineering notes, browse the other files in `docs/`.
