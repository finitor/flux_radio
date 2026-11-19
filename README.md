<p align="center">
  <img src="tools/k6_store_templates/static/favicon.svg" width="72" alt="Flux logo">
</p>

<h1 align="center">Flux</h1>
<p align="center"><strong>Your handheld. Your firmware. Your modules.</strong></p>
<p align="center">Experimental alternative firmware for the Baofeng UV-K6 / K61 (FD6818B).</p>
<p align="center">
  <a href="docs/manual/install.md">Getting started</a> ·
  <a href="docs/module-store.md">Module Catalog</a> ·
  <a href="docs/k6-feature-packs.md">Feature packs</a> ·
  <a href="CONTRIBUTING.md">Contribute</a>
</p>

Flux keeps familiar dual-VFO and channel operation, then adds a modular
radio toolkit. Explore the bands, install applications over your programming
cable, or design your own radio display. You can start with a small firmware
image and add optional features as your interests grow.

![SURF spectrum displays from the emulator](docs/img/k6-surf-screens.png)

*SURF band surfing — emulated displays from development.*

## Choose your starter

| Starter | Includes | Best for |
| --- | --- | --- |
| **Base** | Core radio, Catalog, VFO module | A compact everyday radio |
| **Base + Scan** | Base, FM broadcast radio, SURF, Explore Scan | **Recommended first install** |
| **Base + Scan + Designer** | Scan plus custom display themes | Make the radio your own |

Optional Data, Sotto and authenticated OTA services are available through
custom builds. APRS is a separately installable experimental application;
its weak-signal reception is still under investigation.

## Is my radio supported?

| Hardware | Status |
| --- | --- |
| UV-K6 / K61 with FD6818B (chip ID 0x4829) | Current experimental target |
| Original FD6818 (0x4819) | Planned, not a compatible image |
| Other Aura models and rebrands | Not yet validated |

A model name alone does not establish compatibility. Confirm the RF chip
and board before flashing. See the [hardware roadmap](docs/k6-hardware-parity-plan.md).

> **Important:** Flux is development firmware, not a stable release.
> First installation replaces the original MCU firmware. A SPI flash backup
> preserves calibration and stored data, not the original firmware itself.
> Do not format the radio until you have a verified backup. Use only compatible
> hardware and transmit only where your license and equipment permit.

## Get Flux on your radio

Start with the [installation guide](docs/manual/install.md), which covers
the cable, first boot, backup, format prompt, and module installation.
Starter bundles are intended to eliminate the need for a compiler on the
installation computer. See the guide for the current release workflow.

## Build from source

On Linux, install Git, Python 3.10+, a C toolchain, Clang, LLD, LLVM tools and
Rust with the Cortex-M0 target. For Debian/Ubuntu:

```sh
sudo apt install git python3 python3-venv build-essential clang lld llvm
rustup target add thumbv6m-none-eabi
git submodule update --init --recursive
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
```

Run these commands inside a clone of this repository. Build a starter pack
and choose the appropriate transmit profile for your location:

```sh
python tools/k6.py build base scan --tx-profile fcc \
  --output firmware/k6-aura/out-fd6818b/packs/starter
python tools/k6.py inspect firmware/k6-aura/out-fd6818b/packs/starter
```

The example uses the FCC profile; use the correct local profile instead.
The build and inspect commands do not contact the radio.
Cable-only builds need no signing key. The optional OTA pack requires a
personal module key; see the [installation guide](docs/manual/install.md).

## The local Catalog

```sh
python tools/k6.py catalog
```

Open <http://127.0.0.1:5055>. Choose feature packs, build firmware,
edit themes, and manage installed modules. The Catalog runs on your
computer, not on a cloud service. See the [Catalog guide](docs/module-store.md).
Install only trusted native modules; they are not sandboxed.

## Try the radio without flashing

```sh
python -m pip install -r requirements-dev.txt
python -m sim.k6ide --host 127.0.0.1
```

Open <http://127.0.0.1:5056> and use the emulator's virtual display, keys,
PTT and SPI library. This is a development tool, not evidence of RF
performance. Keep its unauthenticated server on a trusted local network.

## Explore the project

| Find out about | Documentation |
| --- | --- |
| Installation and recovery | [First radio](docs/manual/install.md) |
| Modules and the local store | [Catalog](docs/module-store.md) |
| Firmware customization | [Feature packs](docs/k6-feature-packs.md) |
| Native module development | [Module API](docs/k6-modules.md) |
| Emulator development | [Workbench](docs/k6-emulator.md) |
| Development and tests | [Contributing](CONTRIBUTING.md) |

## Credits and licensing

Flux builds on [Blowfang](https://github.com/baitisj/blowfang),
[Aura](https://github.com/sophiel-meow/bf-k61-firmware-aura) and
[Sotto](https://github.com/baitisj/sotto). The original Blowfang MIT notice
is preserved in [LICENSE](LICENSE); Aura-derived patches and linked
firmware carry GPL-3.0 obligations. See [THIRD_PARTY.md](THIRD_PARTY.md)
for the full attribution and licensing scope.
