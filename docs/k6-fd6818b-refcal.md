# FD6818B reference calibration and APRS IF experiments

Imported upstream refcal from baitisj/blowfang commit
9bc3c2d2187fe82a24213f34b431454618165ba3 (MIT), with dry-run
cleanup on errors and a guard against unexpected trim register values.
Upstream evidence: docs/k6-drift-cal.md and docs/k6-aprs-clock.md in that
commit. Their original FD6818 bench results are not B-chip validation.

## Catalog modules

All are receive-only and slot-independent. These are experiments, not
promoted feature-pack capabilities. Build from the checkout:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/ifsurveyb.c --id org.ag7su.k6.ifsurveyb -o local-modules/if-survey
python3 tools/k6_install.py module-bundle c/k6/mod/refcalb.c --id org.ag7su.k6.refcalb -o local-modules/refcal-dry
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbcal.c --id org.ag7su.k6.aprsifbcal -o local-modules/aprs-if-cal
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbcal8.c --id org.ag7su.k6.aprsifbcal8 -o local-modules/aprs-if-8k
```

The bundles appear in the local Catalog. Installation uses the existing
signed loader, not a firmware flash. No persistent calibration or system
clock changes are made. Refcal Dry temporarily changes the crystal trim
and restores the original trim and AFC/filter settings on normal return;
power-cycling also discards temporary trim.

## Hardware acceptance gates

1. Select an FM VFO on the frequency of a known steady carrier, ideally
   in the 2 m band or 70 cm for comparison. A calibrated bench source
   into suitable attenuation is preferred. Aim for roughly -50 to -70
   dBm (not near-field overload). A NOAA weather station can provide an
   initial check, but voice modulation adds bias/variance. Start the
   serial log and open IF SURVEY. Keep the reference stable during the
   complete four-way measurement. It reports original 3D/3B/3C/73 and
   lines of the form `if w=1 off=1 if=16927 lo=16910 hi=16942 n=16 lost=0 bad=0`.
   `w` is wide; `off` is AFC disabled; IF values are Hz. Noise can
   yield plausible zero crossings, so a stable, known RF signal and
   comparison with an idle capture are essential.
2. If wide/no-AFC centers around 16.9 kHz, try REFCAL DRY (ATSC pilots
   and weather stations); note that the algorithm assumes the legacy
   16.927 kHz center. If the B-chip's measured center differs, do not
   interpret its output as a valid crystal correction. The reference
   antenna and RF front end may not receive higher UHF television pilots.
   Stock frequency-word calibration contributes to the effective measured
   frequency error. Do not enable REFCAL_APPLY until repeatability,
   mixing side, trim scale and TX frequency have been independently checked.
3. With the corresponding measured wide/no-AFC IF, select APRS IF CAL
   (16.92708 kHz) or APRS IF 8K (8.46354 kHz). The latter is a hypothesis,
   not an established B-chip mode. The modules set AGC, wide tuning and
   explicitly disable AFC, log mixer center in centihertz, and restore
   the previous receive state when they exit. The receiver uses the
   upstream matched-filter Bell 202 DSP; no UTC clock voting/setting.
   Both remain on 144.390 MHz for two minutes or until a key is pressed.
   Other measured centers can be built by overriding FIF_CHZ in a wrapper
   (round measured Hz times 100); do not choose using noise captures.
4. Send a known TH-D74 APRS frame at moderate level. Save the complete
   serial log; require `f <expected source>` and `ok>0`, which are
   emitted only after AX.25 FCS verification. `bad`, `pre`, or
   a plausible IF alone is not a successful frame decode.
5. Repeat with pre-emphasized and flat Bell 202 audio, compare sensitivity
   and repeat on 2 m. Only after valid FCS frames on physical B hardware
   should APRS RX be promoted into the normal feature pack.
   APRS TX / KISS / messaging follow separately. No RF transmission is
   enabled by these four experiments.

The FD6818B driver uses 0x3D=0x2AAB for FM (named IF_SEL_8K46), as
does its legacy FD6818 counterpart. This naming is not proof of the
GP0 tap's measured center. Upstream found large filter-dependent changes,
so survey measures both filter widths rather than picking a constant based
solely on the driver's register name.

## First physical IF survey (2026-11-17)

On 162.550 MHz, three user runs returned all 16 blocks per case, no DMA
losses. Original REG_3D was 0000 and REG_73 was 4681 in every run.

| Filter / AFC | Run 1 Hz | Run 2 Hz | Run 3 Hz |
| --- | ---: | ---: | ---: |
| Narrow / on | 5747 | 6196 | 6038 |
| Wide / on | 10399 | 10829 | 10541 |
| Narrow / off | 5541 | 5786 | 5920 |
| Wide / off | 9659 | 10158 | 10279 |

These are measured zero-crossing averages, not a validated carrier-center
calibration. The signal level was not logged and the station may have
been modulated. Do not interpret them as crystal error or pick a decoder
mixer center yet. The driver explicitly uses 3D=2AAB for FM and 0000 for
USB/CW; mod_tune retunes without applying modulation. The cause of the
inherited 0000 is not yet established.

IF SURVEY FM repeats the survey for both 3D values; it checks readback
after tune/RX-on and logs actual filter, AFC and RSSI. Both IF selector and
AFC are restored on exit. Install the separate bundle:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/ifsurveyfm.c --id org.ag7su.k6.ifsurveyfm -o local-modules/if-survey-fm
```

Run on the same station if audibly receiving, then on a known clean carrier
if possible. Use a moderate signal and compare against an idle channel.

## Explicit selector test on the physical B chip (20:00 PT)

At 162.550 MHz, the two FM survey runs measured RSSI -70 to -75 dBm,
all 16 blocks usable and no DMA loss for 3D=0000. Means (Hz):

| Filter / AFC | Run 1 | Run 2 |
| --- | ---: | ---: |
| Narrow / on | 5351 | 5949 |
| Wide / on | 8777 | 10113 |
| Narrow / off | 4194 | 5219 |
| Wide / off | 8525 | 9309 |

Both runs returned -11 after attempting 3D=2AAB. The prior diagnostic
only checked after retune; it cannot distinguish an ignored write
from a value cleared during receiver startup. The updated IF SURVEY FM
reports immediate and 10-ms readback before retuning and the actual
value if the post-retune check fails. Do not weaken the readback guard.
An idle-channel comparison or known unmodulated carrier is still
needed to interpret the zero-crossing averages.

## Stable carrier measurement (2026-11-17, 146.560 MHz)

IF CARRIER, wide and AFC off, gave:

| Tune offset (Hz) | Run 1 (Hz) | Run 2 (Hz) |
| ---: | ---: | ---: |
| 0 | 8385 | 8379 |
| -2000 | 10384 | 10382 |
| +2000 | 6381 | 6381 |
| -4000 | 12394 | 12396 |
| +4000 | 4387 | 4388 |
| 0 again | 14040 (carrier off) | 8388 |

The no-carrier readings were 14108/14192 Hz (RSSI -85/-86 dBm);
carrier readings were -24 dBm. All captures lost zero DMA samples.
The fitted slope is nearly -1 Hz/Hz, and stable center is about 8384 Hz.
This supports the half-IF nominal 26 MHz / 3072 = 8463.542 Hz,
with about -80 Hz combined RF/timing offset. It is not an absolute
crystal calibration: the transmitter reference is not calibrated
and the received signal is very strong. Do not infer crystal ppb
or apply trim yet. Immediate 3D=2AAB readback remained 0000;
whether it is write-only or unsupported remains unresolved.

Use the already-built APRS IF 8K module at 144.390 MHz next.
It programs the 8463.54 Hz mixer, wide filter, AFC off and AGC on.
Try reducing D74 signal strength to around -50 to -70 dBm.
Require expected AX.25 source and valid FCS. The reference-calibration
module still uses legacy nominal IF and should NOT be used for actual
crystal corrections until adapted to B-chip measurements.

## Physical APRS preamble recovered

APRS IF 8K confirmed RSSI about -87 dBm idle and -24 dBm during D74
packets, but no preambles. The RSSI polling diagnostic introduced
occasional DMA overruns. The earlier nonpolling build had no overruns
but also no decoded frames. Lean host LED callback is a no-op.

APRS 8K CAP with AFC off recorded 6000 counts at 5493 kS/s DMA,
zero loss, -24 dBm. The mean Hilbert phase-derived IF was approximately
8384 Hz. The legacy matched-filter decoder produced no consecutive
HDLC flags; the simpler discriminator, with the nominal 8463.54 Hz
mixer and no tone weighting change, recovered five consecutive flags
from the same recording. It recovered them even when preceded by the
separately captured noise window. Tone weighting experiments were not
retained. A regression fixture preserves the first 3600 counts only,
covering the preamble rather than the complete 67 ms capture.

Raw capture SHA-256:
979cfdf974fcb1f1061490be26926a8cb93e9a5de0853310477168b8b1f4a1a0.

APRS 8K DISC is the separate candidate using APRS_DISC and avoiding
the added RSSI polls. Install and try normal D74 APRS transmissions.
Five flags are not a valid AX.25 packet; complete FCS-checked frames
remain the acceptance criterion. No RF transmit or clock setting.

## First CRC-valid APRS reception on physical FD6818B (2026-11-17)

APRS 8K DISC, slot 25, loaded code 5160 bytes, scratch offered 5552
bytes. At 144.390 MHz, AFC off, wide filter, AGC, nominal IF 8463.54 Hz,
DMA rate 5497 kS/s, 12 audio samples per bit:

```
f AG7SU-7 n=48 h=0
f AG7SU-7 n=48 h=0
f AG7SU-7 n=48 h=0
aprs end ok=3 bad=7 ts=0 v=0 lost=0 pre=3
```

Returned 0 after 17917 ms, host stack_free=1616 bytes. All three
reported frames passed the AX.25 FCS check before source parsing.
Seven bad candidates are not seven confirmed missed transmissions;
noise can create false HDLC candidates. Three preambles and three valid
frames, with zero DMA overruns, establish physical reception on the B
chip. Do not claim weak-signal sensitivity or packet success rate from
this short test. Preserve this discriminator build as the known-good
baseline before integrating full packet display, RX/TX and KISS.
