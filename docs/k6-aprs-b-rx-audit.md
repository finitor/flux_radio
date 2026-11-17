# FD6818B APRS receive audit — 2026-11-16

Status: APRS reception on this K6 is not working. Stop treating the current
FSK register variants as validated Bell 202 receivers.

## Latest hardware evidence

The diagnostic module reported:

```
B cfg 58=00c1 59=1028 5a=7e7e 5b=7e7e
B cfg 5c=0001 5d=ff00 72=3065 3f=3002
B cfg 70=0000 0c=0280
B diag st=0382 edges=0 rssi=009f..012c
aprs end ok=0 bad=0 ts=0 v=0 lost=0
```

The project's RSSI conversion gives approximately -95 through -24 dBm.
Status bit 0 was never observed set by this polling loop. Neither this nor
RSSI proves that the modem produced Bell 202 samples. The stream also resets
the modem approximately every 59 ms when idle, which limits conclusions from
its interrupt observations. No valid AX.25 frame has been obtained.

## Independent source evidence

- The BK4829 APRS RX implementation reports abandoning hardware FSK
  demodulation after an FT3D test. Its working implementation instead samples
  RX audio through PA4 ADC at 9.6 kHz and demodulates Bell 202 in software:
  https://github.com/armel/uv-k1-k5v3-firmware-custom/blob/main/App/apps/aprsrx/README.md
- That project's `App/driver/bk4829.c`, `BK4819_SetupAircopy`, describes
  `0x58=0x00C1` as plain FSK. It is not evidence of a Bell 202 tone receiver:
  https://github.com/armel/uv-k1-k5v3-firmware-custom/blob/main/App/driver/bk4829.c
- A radio developer reports FD6818B chip ID 0x4829 and successful porting of
  the BK4829 driver. This supports comparison, but does not prove every modem
  register or board connection is identical:
  https://github.com/amoxu/Baofeng-UV-5RM-5RH-RE/issues/18

These are source/project reports, not a successful test on our K6.

## Corrections to our assumptions

1. Copying Aura's raw FSK configuration did not establish APRS compatibility.
   The D74's 1200-baud Bell 202 signal needs tone demodulation before NRZI and
   HDLC decoding. Matching the baud number is insufficient.
2. `FSK_FORMAT2` currently changes only the startup label in `aprsclk.c`.
   `FSK_TYPE` writes register 0x5C. The available FD6818 documentation describes
   this as a transmitted type byte; it does not establish that writing 1
   enables unlimited RX on the B chip. Our earlier claim was unsupported.
3. `0x7E` is an HDLC flag after NRZI decoding. It is not automatically the
   sync pattern to search in raw tone states; upstream's legacy receiver uses
   FEFE for that reason. The 7E experiment was not a justified fix.
4. Aura polls 0x0C bit 0 and writes 0 to 0x02 to acknowledge interrupts.
   This proves its driver usage, not that 0x02 is write-only or cannot return
   causes on this silicon. The previous categorical description of 0x02 was
   too strong. Do not infer a register specification from a helper's name.
5. `tests/k6_fd6818b_fsk.py` explicitly models register transactions and
   injected FIFO frames, not RF or tone demodulation. Passing it cannot show
   that an APRS transmission will reach the FIFO.

## K6 input-path constraint

The external receiver's ADC wiring cannot be copied directly. In Aura's K6
board sources, PA4 is the broadcast FM I2C clock; PA0 is VOX microphone level
sense and PA1 is battery sense. None establishes a sampled RX-audio input.

The existing K6 code provides a candidate without board modifications:
GP0 to PB1, captured through DMA, with software IF/FM demodulation. The
evidence in `docs/k6-if-modem.md` and `c/k6/mod/gp0cap.c` concerns the legacy
FD6818. Its routing and useful output must be established for FD6818B before
claiming this works on the user's radio. The existing capture also uses a
large stack buffer; it must not be deployed unchanged with the host's roughly
692-byte entry stack allowance.

## Next acceptance gates

1. Establish a B-chip sample source: documented RX audio or measured GP0/IF.
   Record noise and a known signal, with capture timing and loss counts.
   Place capture buffers in checked scratch RAM, not the small module stack.
2. Save samples and exact firmware/module hashes. Recover the expected audio
   tones offline before modifying the APRS packet decoder.
3. Replay the same capture through the software Bell 202/NRZI/HDLC decoder.
   Require the expected callsign/payload and a valid AX.25 FCS; include a
   corrupted-frame rejection check. Synthetic audio validates DSP separately.
4. Run that decoder through the module/host path with measured stack and
   scheduling requirements; then perform an on-radio reception check.

If no usable sample path exists on the unmodified B board, state that limit
and evaluate an external audio TNC or a hardware audio connection. Do not
substitute further arbitrary FSK register sweeps for the missing input path.

## B-chip capture implementation

`c/k6/mod/aprsifbcap.c` is a receive-only, slot-independent probe. It tunes
144.390 MHz, routes GP0 selector 13 to PB1, checks the route register readback,
and captures one 25 ms no-carrier window. It then waits for RSSI at least 12 dB
above that baseline and captures two 25 ms windows during the signal. The ring
and capture buffer live in checked module scratch RAM (1024 + 2160 bytes), not
on the small module stack. It restores the modified RF registers and MCU
DMA/timer clocks before returning. It shares the proven legacy capture code in
`gp0cap.c`, but the B-chip route and signal quality remain unverified.

Build and load it from this repository:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbcap.c \
  --id org.ag7su.k6.aprsifbcap -o /tmp/k6-aprsifbcap-bundle
python3 tools/k6_install.py --port /dev/ttyUSB0 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  load /tmp/k6-aprsifbcap-bundle --verify
picocom -b 115200 --logfile /tmp/k6-aprs-if.log /dev/ttyUSB0
```

Select **APRS IF CAP** in the Blowfang menu. Once it says it is listening,
send a 1200-baud APRS packet from the TH-D74. Press a radio key to stop waiting.
Then extract the raw signed counts:

```sh
python3 tools/k6_aprs_if_probe.py /tmp/k6-aprs-if.log \
  --out-dir /tmp/k6-aprs-if-captures
```

The summary includes RSSI, sample rate, overrun count, and AC RMS for each
window. A low `lost` count and a difference between no-carrier and carrier
captures establish only that a sample path responds. These windows are too
short to validate a whole AX.25 packet or its FCS.

### First B-chip capture, 2026-11-16

The user loaded APRS IF CAP in slot 22 and sent APRS from a TH-D74. All three
windows had 2160 samples at a measured 5688 kS/s DMA rate and `lost=0`:

| Window | RSSI | AC RMS counts | Observation |
| --- | ---: | ---: | --- |
| no carrier | -87 dBm | 5.08 | broad noise |
| carrier 1 | -59 dBm | 26.58 | strong narrow IF peak near 18.1 kHz |
| carrier 2 | -24 dBm | 23.23 | much more distorted spectrum |

This establishes an active B-chip GP0/PB1 receive sample path. The strong
window suggests overload or another source of distortion, not a decoded APRS
packet. The 25 ms windows do not contain enough continuous data for AX.25 FCS
validation. The samples and machine summary from the supplied log are under
`/tmp/k6-aprs-if-analysis` on the development host; this directory is not a
tracked fixture.

An AGC-on APRS software receive experiment, `c/k6/mod/aprsifbrx.c`, reuses
the existing `aprsclk.c` Bell 202/HDLC decoder with `GAIN13=0`. The older
APRS CLOCK run fixed REG_13 at `0x03FF`, so it did not test this gain state.
Build and install the experiment as a separate module:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbrx.c \
  --id org.ag7su.k6.aprsifbrx -o /tmp/k6-aprsifbrx-bundle
python3 tools/k6_install.py --port /dev/ttyUSB0 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  load /tmp/k6-aprsifbrx-bundle --verify
```

The acceptance criterion is an `aprs end ok` count above zero plus an `f`
line with the TH-D74's expected source and valid FCS. A higher `pre` count
alone shows only flag detection. If this fails, collect longer continuous IF
samples at a moderate RSSI and replay them offline before changing the
decoder or adding a permanent receive API to the base firmware.

The first AGC-on APRS IF RX radio run reported `ok=0 bad=4 pre=0 lost=0`
over 13.7 seconds. In the decoder, `bad` counts only flag-delimited candidates
at least 18 bytes long whose AX.25 FCS failed. Noise can produce these; `pre=0`
means it did not see three consecutive flags. This is progress in the signal
path, but not yet evidence of a packet.

The next APRS IF RX build printed six bad candidate lengths (18 to 26 bytes)
and unrelated first bytes, with `pre=0` and `lost=0` in 21.5 seconds. These
look like random false frames, not a nearly correct AX.25 packet.

The current `APRS_IF_DIAG` build records the last 4096 NRZI-decoded bit
decisions in scratch RAM. It stops on the first CRC-failed candidate, shuts
down DMA, and then emits `bad n=... b0=... b1=... b2=...`, `bits total=...`,
and 32 `bits <offset> <hex>` lines. Bit positions are packed least significant
bit first, with byte index `(bit_index >> 3) & 511`. The circular buffer holds
up to 3.4 seconds at 1200 baud. This avoids serial output during capture.
The first three bytes should resemble shifted ASCII of the destination
callsign if the receiver is close to a real frame. The raw bit record can
also be searched for repeated 0x7E flags and decoded offline with alternate
timing and polarity assumptions. Because noise can trigger a false candidate,
start transmitting soon after opening the module.

The first bit recording held 4096 of 5448 decisions. It contained 28 0x7E
patterns with no consecutive flags; 56.57% of decisions were ones. Independent
bits at that balance would produce about 25 flags by chance in the same span.
Its first bad candidate was 18 bytes with an implausible AX.25 prefix
`102, 77, 52`. This supports the noise/failed-demodulator interpretation.
`tools/k6_aprs_bits.py LOG` reproduces the bit count, flag count, and longest
flag run from a saved serial log.

The first raw IF captures are only 25 ms. Offline FM discrimination found a
strong component near 2.2 kHz in the -59 dBm window, so the sample source can
carry Bell 202 tone information. A 67 ms capture (`APRS IF 67`) now records
6000 consecutive count samples at a carrier rise. It fits the existing B-host
scratch (1024-byte DMA ring plus 6000-byte capture) and can include roughly
80 transmitted bits, enough to inspect a flag lead-in if the trigger catches
it. Build/load it as a separate module:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbcapwide.c \
  --id org.ag7su.k6.aprsifbcapwide -o /tmp/k6-aprsifbcapwide-bundle
python3 tools/k6_install.py --port /dev/ttyUSB0 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  load /tmp/k6-aprsifbcapwide-bundle --verify
```

Open picocom with `--logfile /tmp/k6-aprs-if-67.log`, select **APRS IF 67**,
and transmit a D74 APRS packet after the module says it is listening. Then:

```sh
python3 tools/k6_aprs_if_probe.py /tmp/k6-aprs-if-67.log \
  --out-dir /tmp/k6-aprs-if-67
```

The analysis must report a clean capture (`lost=0`) with a moderate carrier
level. Replay that exact window through `c/k6/aprsclk_host.c` and compare its
bit decisions against the actual FM tone transitions before altering the
firmware receive API or any further FSK register settings.

### First 67 ms B-chip recording

The user's 6000-sample recording at 5493 kS/s had `lost=0`. Noise was
`-86 dBm`, AC RMS 5.65 counts. The carrier window was `-56 dBm`, AC RMS
23.61 counts. Its first few milliseconds were a carrier onset; the remaining
window was dominated by a roughly 2.2 kHz FM discriminator tone. In 5 ms
windows, the 1200 Hz energy was only about 0.12 to 0.30 of the 2200 Hz
amplitude. Replaying the exact 6000 counts through `aprsclk_host.c` gave
84 NRZI decisions and no valid AX.25 frame. This recording establishes that
the B-chip sample path carries a modulated signal but does not yet contain
enough visible alternating Bell 202 tones to diagnose packet bit timing.
It may have caught the D74's initial transmit delay.

`APRS IF LATE` captures 300 ms after the first RSSI rise, using the same
gain, route, 67 ms sample window, scratch allocation, and cleanup as
`APRS IF 67`. This is a separate module so the onset probe stays reproducible:

```sh
python3 tools/k6_install.py module-bundle c/k6/mod/aprsifbcaplate.c \
  --id org.ag7su.k6.aprsifbcaplate -o /tmp/k6-aprsifbcaplate-bundle
python3 tools/k6_install.py --port /dev/ttyUSB0 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  load /tmp/k6-aprsifbcaplate-bundle --verify
picocom -b 115200 --logfile /tmp/k6-aprs-if-late.log /dev/ttyUSB0
```

Select **APRS IF LATE** and transmit once after its listening line. The
module records noise first, waits for a carrier, pauses 300 ms, then records
one 67 ms window. Extract it with `tools/k6_aprs_if_probe.py`. If it still
contains only a 2.2 kHz tone, the next check is a later point in the same
transmission or an independent RX-audio source, before changing decoder
coefficients.

### First delayed recording

The 300 ms delayed capture arrived at `-24 dBm` with `lost=0`; its noise
window was `-86 dBm`. The carrier window's AC RMS was 23.47 counts. Its
strongest raw IF components were around 6 to 7 kHz and 10 to 12 kHz, with
little energy near the earlier recording's 18 kHz. This shift lasted across
the whole 67 ms window. The FM-discriminator spectrum had energy around both
1200 and 2200 Hz, but those components alone do not establish clean Bell 202
symbols. The current decoder yielded 80 bit decisions, no flag, and no valid
frame. Offline replays with IF center frequencies from 5.5 through 20 kHz
in 500 Hz steps produced at most two isolated flag patterns, no consecutive
flags, and no frame. The raw carrier capture SHA-256 is
`29137d6f62f5d476a5f82bc61dcb8e0c7af0556302cbf43df0b71d0df4deb580`.

The level changed from `-56 dBm` in the onset capture to `-24 dBm` here, so
time offset and RF level changed together. A lower-power or more distant D74
transmission that yields approximately `-50` to `-70 dBm` in the same delayed
probe is the next controlled comparison. If the IF still shifts, repeat with
AFC held off and measured route/register readbacks. Keep the raw samples and
require a valid AX.25 FCS before promoting an IF-center change into firmware.

The next user run reported only a noise window (`floor=-87`, capture RSSI
`-88 dBm`, `lost=0`), then `ret=-2` after about 49 seconds. No carrier
window was captured, so it cannot be compared with the two previous signal
windows. At that time the trigger required at least `-75 dBm` (`floor+12`).
The probe now requires two consecutive 5 ms RSSI samples at `floor+8` and
prints its trigger level and peak RSSI when it stops or captures. This will
distinguish a signal that stays below threshold from a missed/absent
transmission without guessing from the noise window.

## Host and module boundary for additional modems

The base image should own the RF input selection, DMA/timer reservation,
sample timing, sample buffering, PA control, and the existing bounded transmit
primitive. Those are chip and board dependent and must be arbitrated centrally.
After the B-chip input is measured, expose a small versioned receive-sample API
that returns sample format, measured rate, loss count, and blocks of samples.
Do not expose raw DMA or GP0 register writes as a general app-store API.

Bell 202, AX.25, APRS message/digipeater behavior, KISS policy, and any future
Sotto mode should use that service from modules where CPU and RAM permit. The
current Sotto implementation also has a separate hardware-FSK path; it need
not be forced through Bell 202. If sustained timing or RAM makes a modem
impractical as a module, move only its reusable DSP kernel into the base image
and leave the user interface and protocol policy in the module. This preserves
flash space and lets different modes share the same measured receive source.
