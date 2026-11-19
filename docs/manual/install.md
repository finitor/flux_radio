# Getting Flux onto your first radio

Flux targets the Baofeng UV-K6/K61 with the FD6818B chip (0x4829).
Other chips and models are not verified. Confirm your hardware before
proceeding. This is experimental firmware.

## What you need

- A compatible radio, charged battery and a working two-pin USB programming cable.
- A Linux computer with Python 3.10+ and serial-port access.
- A complete starter pack, either from a trusted release or built using the
  [README](../../README.md#build-from-source). Keep the pack together.
- A safe location for your radio's 2 MiB SPI backup.

**Before proceeding:** flashing replaces the original MCU firmware, which
this installer cannot read back or restore. Obtain a compatible recovery
image independently if returning to stock is essential. Do not copy a
different radio's factory calibration. Keep power and cable connected
throughout the procedure.

## Prepare your computer

In the repository's directory, activate your Python environment and install
the dependencies as described in the README. Identify the cable:

```sh
python -m serial.tools.list_ports
```

The examples use `/dev/ttyUSB0`. Substitute your actual port. Close other
programs using it. On many Linux systems, the serial device belongs to the
`dialout` group; if needed, ask your administrator to grant access and log
out and back in.

For the examples below, set the pack directory:

```sh
PACK=firmware/k6-aura/out-fd6818b/packs/starter
python tools/k6.py inspect "$PACK"
```

Inspection verifies artifact consistency, not the publisher's identity or
the connected radio's hardware. Do not install an untrusted bundle.

## First installation from stock firmware

1. Try a backup while the radio is on its normal screen:

   ```sh
   mkdir -p "$HOME/flux-backups"
   python tools/k6.py radio --port /dev/ttyUSB0 backup \
     -o "$HOME/flux-backups/my-k6-before-flux.bin"
   ```

   Stock firmware may not support the required read protocol. If it does
   not, the first-boot backup below is essential.
2. Switch the radio off, hold both side keys, and switch it on. Confirm
   the display says UPDATE. Release the keys.
3. Flash the firmware:

   ```sh
   python tools/k6.py flash-pack "$PACK" --port /dev/ttyUSB0 --already-update --yes
   ```

   If the radio remains in UPDATE after the tool reports completion,
   power cycle it normally.
4. On a new radio, Flux may display **FORMAT FLASH?**. Do **not** press
   MENU yet. Use the backup command from step 1 with a new filename
   if needed. The backup session supports this screen. It reads the
   entire SPI and checks the calibration sector twice. Verify the file
   is 2,097,152 bytes, keep it outside the repository and make a second
   copy. If backup fails, stop.
5. Only after the verified backup, press MENU on the radio to confirm
   format. This resets settings and may erase stored data. Wait for the
   normal VFO screen. If the prompt is absent, do not try to force format.
6. Preview and install the starter modules:

   ```sh
   python tools/k6.py install-pack "$PACK" --port /dev/ttyUSB0 --preview
   python tools/k6.py install-pack "$PACK" --port /dev/ttyUSB0 --yes
   ```

   The installer compares capabilities and firmware build identity,
   allocates slots and reads installed modules back. If installation is
   interrupted, return to the normal screen and rerun the install command;
   do not blindly erase an occupied slot.

## First steps on the radio

From the VFO screen, press MENU, navigate to CATALOG with UP/DOWN and
press MENU. Try the installed modules. EXIT returns to the previous screen.
In Settings > System > About, check your active feature set and flash budget.
Configure your callsign, frequency, offset, tones and permitted transmit
bands before transmitting. Start with receive-only checks.

## Updating an existing Flux radio

Back up the radio first. With the normal screen showing, use:

```sh
python tools/k6.py flash-install-pack "$PACK" --port /dev/ttyUSB0 --yes
```

This writes the selected firmware, installs its modules and included
artwork, and verifies module readback. For a fresh radio with a format
prompt, use the separate first-install steps above instead.

## Module keys

The starter profiles use cable-only CRC integrity checking, not a secret
module key. OTA is disabled. For an explicit custom build containing
the OTA feature, generate and keep a personal key with
`python tools/k6.py radio key`; use that key with `--key-file` on pack
provisioning commands. Reuse the key for an existing keyed radio.
Neither CRC nor module signatures sandbox native code.

## If something goes wrong

- No serial connection: verify the cable, port, permissions, radio power,
  and that no other app has the port open.
- No bootloader response: verify the UPDATE display and retry with
  `--already-update`. Do not flash another hardware variant to test.
- FORMAT FLASH? remains: do not erase until the SPI backup succeeds.
- Modules missing: return to the VFO screen and run the install command
  again using the exact same pack.
- Radio will not boot: try entering UPDATE with both side keys held
  while powering on. Use a known-compatible image. If UPDATE itself is
  unavailable, stop and seek hardware-specific recovery assistance.

There is no guaranteed stock recovery path in this repository. Keep your
backup and record the firmware build, model, chip variant and complete
installer error when asking for help.

For additional modules and the browser interface, see the
[Catalog guide](../module-store.md).
