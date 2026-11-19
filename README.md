# Flux

Flux is AG7SU firmware and a module catalog for the Baofeng UV-K6/K61 with the FD6818B RF chip. The firmware keeps normal VFO and channel operation, native Search, a module launcher labeled **Catalog**, and an About screen with the active feature set and flash space.

Optional feature sets add modules through the local Catalog. The **Scan** set bundles SURF and EXPLORE; APRS and Sotto remain separate module work. The boot screen supports voltage, message, or logo mode, with optional text alongside the logo.

The firmware is built from pinned upstream sources with Flux patches. Upstream names remain in source paths and protocol identifiers where compatibility or attribution requires them.

**Development status:** experimental firmware, not a stable release. The FD6818B variant is the current target; other Aura-supported radios are not yet validated. Back up your radio before flashing. Simulator success does not establish RF performance or hardware compatibility.

## Build

Clone this repository with its submodules (`git clone --recurse-submodules <repository-url>`), or run `git submodule update --init --recursive` in an existing clone.

Install Rust with the `thumbv6m-none-eabi` target, clang, LLD, LLVM tools, Git, and Python 3. Use a virtual environment and install the Python dependencies:

```sh
rustup target add thumbv6m-none-eabi
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Generate a local 16-byte module signing key if you do not already have one. Keep the same key for a given radio; never publish it or overwrite an existing key. If migrating from Blowfang or Sotto, reuse your existing key rather than generating a new one for that radio.

```sh
mkdir -p "$HOME/.config/flux"
if [ ! -e "$HOME/.config/flux/k6-mod.key" ]; then
  (umask 077; set -C; python3 -c 'import secrets; print(secrets.token_hex(16))' > "$HOME/.config/flux/k6-mod.key")
fi
```

Build through the unified CLI:

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
python3 -m pip install -r requirements.txt
python3 tools/k6.py catalog
```

Open <http://127.0.0.1:5055>. The web interface includes the Catalog, feature packs, device settings, and radio status. The CLI and catalog behavior are documented in [the Catalog guide](docs/module-store.md). The cable installer is [tools/k6_install.py](tools/k6_install.py).

## Simulator

Start the radio development workbench with:

```sh
python3 -m pip install -r requirements.txt -r sim/k6emu/requirements.txt
python3 -m sim.k6ide --host 127.0.0.1
```

It serves on port 5056 by default. Without `--host`, the workbench binds to all interfaces; it has no authentication, so do not expose it to untrusted networks. Open <http://127.0.0.1:5056> locally. The workbench runs the firmware image in the K6 emulator, shows the display and UART output, and supports virtual keypad, power, and PTT input. Module bundles can be staged in virtual SPI flash. The simulator does not open a programming cable; emulator results do not verify RF or physical-radio behavior.

## Development map

- `firmware/k6-aura/` contains the pinned source build, Flux patches, and FD6818B feature-set build.
- `c/k6/` contains module and shared-library code; [docs/k6-modules.md](docs/k6-modules.md) describes the module API.
- `tools/k6.py` is the unified command line; `tools/k6_store.py` runs and manages the local Catalog.
- `local-modules/` contains generated local starter bundles and is ignored by Git.
- `sim/` and `tests/` contain the emulator and tooling validation.

## Tests and contributing

Install `requirements-dev.txt` in the virtual environment and run `python -m pytest` for the Flux tests. Some hardware-oriented or toolchain-dependent tests require additional local setup; the CI smoke tests cover core tooling without a radio. See [CONTRIBUTING.md](CONTRIBUTING.md).

## Licensing and upstreams

Flux builds on [Blowfang](https://github.com/baitisj/blowfang), [Aura](https://github.com/sophiel-meow/bf-k61-firmware-aura), and [Sotto](https://github.com/baitisj/sotto). The original Blowfang MIT notice is preserved in [LICENSE](LICENSE); Aura-derived patches and linked firmware have GPL-3.0 obligations. See [THIRD_PARTY.md](THIRD_PARTY.md) and [firmware/k6-aura/LICENSE.md](firmware/k6-aura/LICENSE.md) for scope and source information.

For installation guidance, see [docs/manual/install.md](docs/manual/install.md). For deeper engineering notes, browse the other files in `docs/`.
