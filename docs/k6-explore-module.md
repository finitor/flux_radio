# EXPLORE as a sideloaded module

This module brings the original EXPLORE scan engine and candidate grader to the compact
Aura/Blowfang host image. It scans receive-only, displays the latest sweep as a scan trace, ranks
candidate frequencies, and marks frequencies already saved in the repeater table. It reads saved
rows via the host's bounded flash API and validates their CRCs; it does not write or erase the
table.

## Build and load

Build the module bundle from the repository root:

```sh
python3 firmware/k6-aura/build-explore-module.py
```

Load slot 29 over the programming cable while the radio is in the Blowfang host firmware:

```sh
python3 tools/k6_install.py \
  --port /dev/ttyUSB0 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  load firmware/k6-aura/out-fd6818b/explore-module-bundle \
  --only 29 --verify
```

Open the Blowfang module menu and select **EXPLORE**. Change `/dev/ttyUSB0` if Linux assigned
the cable a different device name.

## Scan and controls

The module uses the original two-stage quick scan, confirms hits with settled RSSI reads, tracks
overs, and grades candidates with the original band-plan and signal-consistency rules.

| Control | Action |
| --- | --- |
| BAND | Cycle ALL, 2 m, 70 cm, and 1.25 m scan modes; candidates remain in the list |
| MENU | Toggle between waterfall and ranked candidates |
| UP / DOWN | Select a candidate in the ranked list |
| Side key 1 | Try the selected candidate: park on its frequency, then press a key to resume scanning |
| EXIT | Stop scanning and return to Aura |

A `*` after a candidate's over count means its frequency is already in the saved repeater table.

The module now uses the original Explore band's segment definitions: ALL scans 144–148 MHz in
10 kHz steps, 223.8–225 MHz in 20 kHz steps, and 440–445 MHz in 12.5 kHz steps. BAND then
selects 2 m (144–148 MHz), 70 cm (440–450 MHz in two 5 MHz segments), 1.25 m (222–225 MHz in
20 kHz steps), then ALL again. The candidate grader classifies repeater, simplex, and calling
frequencies across those ranges. The display keeps the latest 128-column sweep trace; completed
transmissions enter the ranked list after the scanner observes their end.

## Current boundary

This port currently implements the original scanner ranges, a live scan trace, a six-candidate
ranked list, band changes, candidate-list navigation, Try, and saved-frequency lookup. It does not
yet include
EXPLORE's CW-ID listener, automatic ID listening, DMR/CTCSS/DCS capture, repeater-table
save/delete, or station editor. The 9.7 KB code image leaves about 2.1 KB in the host's 11.7 KB
module arena; the remaining feature set requires reducing the scanner/UI footprint or changing
the host/API. Candidate state is lost when the module exits.

The current default build is the tested 9,682-byte scanner. A table-save prototype was measured
at 10,762 bytes, leaving only 988 bytes for module state; the simulator confirmed it exits with
`-8` before scanning. The prototype is compile-gated and is not in the default bundle. Keep this
as a useful sizing result: moving the scan floors alone will not fit Save; the design likely needs
a small host/API save callback or a deliberate split between scanning and table editing.

## Simulator check

The standard module run checks startup, saved-table lookup, band switching, and the no-candidate
guard against the exact host image/ELF pair:

```sh
python3 -m sim.k6emu.host_contract \
  --image firmware/k6-aura/out-fd6818b/aura-fd6818b-blowfang-host.bin \
  --elf firmware/k6-aura/build/aura-fd6818b-port/target/thumbv6m-none-eabi/release/aura \
  --spi-flash /home/tyler/blowfang-backups/k6-spiflash-emulator.bin \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  --bundle firmware/k6-aura/out-fd6818b/vfo-module-bundle \
  --explore-bundle firmware/k6-aura/out-fd6818b/explore-module-bundle \
  --cases explore \
  --instructions 250000000 \
  --out /tmp/k6-host-contract-explore-normal
```

For a deterministic candidate, build the simulator-only fixture and rerun with
`--explore-bundle firmware/k6-aura/out-fd6818b/explore-module-sim-bundle`,
`--instructions 300000000`, and a fresh `--out` directory. The fixture run passed Try park/resume;
the fixture bundle must not be installed on the radio. Both simulator runs passed without CPU
faults or writes outside watched host RAM. The 2026-11-16 normal run and deterministic candidate
fixture both passed; the fixture's Try park/resume passed too. The simulator has no RF stimulus,
so it does not verify signal detection or a real receiver's audio behavior. The Explore module
still needs an on-radio scan check.
