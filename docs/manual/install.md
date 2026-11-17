# Install Flux

This guide covers Flux on a Baofeng UV-K6/K61 with the FD6818B RF chip. The firmware keeps native
VFO/channel radio operation and adds the Flux Catalog module launcher. It is not the stock Baofeng image;
keep a SPI flash backup and understand the radio's bootloader recovery procedure before flashing.

## Build

Follow the root [README](../../README.md#build) to install toolchains and build the
host image. The image is keyed with the local module key, so keep that key for signing modules you
intend to install.

## Back up and flash

Connect the two-pin programming cable and identify its serial device (often `/dev/ttyUSB0`). First
save the radio's 2 MB SPI flash, including factory calibration:

```sh
python3 tools/k6_install.py --port /dev/ttyUSB0 backup -o k6-spiflash-backup.bin
```

Put the radio into UPDATE mode by holding Side Keys 1 and 2 while switching it on. Then flash the
built image:

```sh
python3 tools/k6_install.py \
  --port /dev/ttyUSB0 \
  --key-file "$HOME/.config/flux/k6-mod.key" \
  flash firmware/k6-aura/out-fd6818b/flux-fd6818b.bin \
  --already-update
```

The script keys the image with your local key before writing it. Do not disconnect power or the
cable while flashing. After the radio restarts, open **CATALOG** from the Flux launcher.

## Install starter modules

With the radio back at the Flux VFO screen, install the generated starter bundle over the cable:

```sh
python3 tools/k6_install.py \
  --port /dev/ttyUSB0 \
  --key-file "$HOME/.config/flux/k6-mod.key" \
  load firmware/k6-aura/out-fd6818b/vfo-module-bundle --verify
```

The catalog can also install modules and manage occupied slots; see [the Catalog guide](../module-store.md).
