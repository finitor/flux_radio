# Flux native APRS (FD6818B)

Hardware milestone: 2026-11-17, APRS 8K DISC received three FCS-valid
48-byte frames, three preambles, no DMA losses. See k6-fd6818b-refcal.md.
Do not modify that known-good test binary during UI development.
The software IF receiver does not need the experimental hardware FSK
receive service, nor the Scan pack. All new modules are independent
SPI applications, not simultaneously resident in RAM.

## Installable candidates

- **APRS** (aprsapp.c, level 6): one-hour listening session, six recent
  packets newest first; up/down browse, MENU details, up/down text pages,
  MENU returns to list, EXIT returns to host. No clock writes or TX.
  Parses uncompressed positions (including ambiguity), source/destination
  SSID, path hop count, APRS message addressee/text, status and packet type.
  Compressed/Mic-E, objects, items, weather, telemetry and third-party are
  classified; full decoding of those formats is future work. Text preview
  limited to 56 printable characters; history is volatile, not persistent.
- **APRS BEACON** (aprsbeacon.c, level 15): read live Aura settings using
  existing stable settings ABI. Builds one AX.25 UI position packet with
  callsign/SSID, coordinates, symbol, path and custom comment, FCS,
  32 lead flags, 3 tail flags, HDLC stuffing and MSB-first NRZI for the
  host AFSK API. Only fresh MENU confirmation transmits; EXIT or 15-second
  timeout cancels. TX low-power through host's US amateur band guard,
  bounded AFSK API, TX release, no timer or automatic retry. Two RSSI
  comparisons against -82 dBm are a coarse occupancy guard based on the
  -87 dBm measured floor, not complete CSMA. Verify config, frequency,
  station ID and clean channel (prefer attenuated bench setup).
  TX is not physically validated. Existing settings battery/device-info
  comment extensions are not used by this candidate. No automatic TX.
- **APRS KISS RX** (aprskissrx.c, level 14): exclusive programming UART in
  KISS mode, port 0, FCS-stripped AX.25 data with FEND/FESC escaping.
  Receives only; no KISS commands or outbound frames accepted.
  Exit key restores text mode. Host UART writes and LCD draws may pause
  receive processing briefly; not full-duplex or continuous-lossless TNC.
  Use a dedicated serial KISS client after starting the module.

Build them with:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/aprsapp.c --id org.ag7su.k6.aprs -o local-modules/aprs
python3 tools/k6_install.py module-bundle c/k6/mod/aprsbeacon.c --id org.ag7su.k6.aprsbeacon -o local-modules/aprs-beacon
python3 tools/k6_install.py module-bundle c/k6/mod/aprskissrx.c --id org.ag7su.k6.aprskissrx -o local-modules/aprs-kiss-rx
```

Existing Catalog server discovers the bundles. Do not enable the old
aprs feature pack to obtain any of these. That pack still requests the
unvalidated hardware-FSK receiver; promote the new receive application
only after physical acceptance. Existing host API levels 6/14/15 suffice,
no new base firmware features needed. Use the 8K DISC module as fallback.

## Validation / physical gates

1. Install APRS on the current Designer firmware. Confirm the expected
   source, packet type, text and position for multiple D74 packets.
   Verify list scrolling, detail navigation, return-to-VFO, memory
   and no DMA overrun regression. Repeat with real on-air traffic.
2. Test APRS BEACON on an appropriate clear test channel, first cancel
   and busy/refused cases, then explicit one-packet send with D74
   configured for 1200-baud APRS. Verify decoded source/path/position,
   FCS and actual unkeying. No automatic transmit until this passes.
3. Test APRS KISS RX with a computer TNC client (115200 cable UART), check
   escape handling and exit-to-text. No TX support until step 2 passes.
4. Replace legacy APRS pack with receive software module(s), make raw FSK
   an independent optional digital-data service. Re-test Designer+APRS
   pack size; it need not link the raw FSK receive callback.

## Next feature phases

- Full packet parsing: compressed and Mic-E positions, object/item and
  weather fields, telemetry, altitude/course/speed, distance/bearing if
  a valid configured home position exists. Keep packet type distinct from
  complete decoding.
- Station table (deduplicate callsigns, last heard, position, packet
  count), packet and message filters, local inbox from own callsign/SSID
  settings. No automatic acknowledgments in initial RX-only release.
- Editor for outgoing addressed messages and canned replies using radio
  keypad; message IDs, ack/rej parsing, duplicate suppression, bounded
  retry and backoff. Separate manual confirmation for send.
- Periodic fixed-position beacons explicitly enabled by user, sensible
  interval and CSMA; GPS/smart beaconing only with a real position source.
- Bidirectional KISS with host commands, length bounds, FCS/NRZI encoding,
  channel arbitration, transmit policy, queue and bounded scheduler.
- Persist configuration via existing Settings/Catalog; history persistence
  needs an explicitly allocated storage/API region, never reuse calibration
  or repeater sectors. A background receiver would need independent
  scheduling/RAM design, not simultaneous synchronous module execution.

## Automated tests

tests/test_k6_aprs_app.py covers UI-frame parsing, bounds, positions,
message metadata, TX wire roundtrip, coordinate rounding, KISS worst-case
escaping, real module arena size and modeled Cortex-M0 RX. Physical
preamble fixture in tests/test_k6_b_if_cal.py remains part of the baseline.
Tests do not prove RF TX, physical screens/key handling or UART behavior.

## GPS SYNC (API level 23)

One-shot, receive-only position import from exactly AG7SU-7 at 144.390
MHz. Launch the module and send a TH-D74 position beacon; first accepted
CRC-valid direct packet with a nonambiguous position updates both
APRS settings coordinates and ends the listening session. Cancel with
any key or wait for the five-minute timeout. No per-beacon confirmation
or TX. A repeated/digipeated frame, wrong SSID, non-position packet,
ambiguous coordinate or invalid position is ignored. Supports ordinary,
timestamped, compressed and Mic-E station positions. Does not accept
third-party packet injection or objects/items as a source position.
Position is stored in signed degrees x100000 using Aura's existing
settings save path; saved coordinates are used by APRS BEACON.
The same position causes no flash write; at most one changed position
is saved per invocation. The settings write uses the existing storage
routine; hardware reboot/readback validation remains necessary.
Callsign filtering is NOT authentication; a spoofed direct matching
packet could update the position. A dedicated SSID is recommended.

Default source is compiled into aprsgpssync.c using SYNC_SOURCE; to
select another station create a wrapper (include the absolute module
path if building outside c/k6/mod):

```c
#define K6_MODULE_LEVEL 23
#define SYNC_SOURCE "N0CALL-9"
#include "aprsgpssync.c"
```

Build with module-bundle and a unique ID. Source editing on-device and
continuous background tracking are future features. The module is a
manual single-fix acquisition tool, not an onboard GPS.

The keyed designer host build is
`firmware/k6-aura/out-fd6818b/flux-designer-gps-sync.bin`.
It uses the Designer service without Scan or hardware FSK RX.
Level 23 adds only the bounded `aprs_position_set(lat,lon)` callback;
general settings writes remain unavailable to RAM modules.
Reflash this image before installing GPS SYNC. Test with a direct
D74 beacon, verify Settings coordinates, reboot and verify persistence,
then confirm APRS BEACON uses the adopted coordinates.
