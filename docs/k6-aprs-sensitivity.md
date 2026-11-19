# FD6818B APRS sensitivity investigation

## Field observation (2026-11-18)
The operator heard numerous APRS bursts during mobile use, but decoded only
packets from a separate transmitter in the same vehicle. This establishes a
practical receive-performance problem, not a calibrated sensitivity figure.
Preserve the working standalone APRS receiver and physical selector baseline.

## Prior evidence
See k6-aprs-clock.md (original FD6818): the GP0 one-bit tap noise can dominate
normal FM receiver sensitivity. Frozen gain, higher sampling rate and matched
filtering helped in prior experiments; these results do not establish gains on
FD6818B. The existing B receiver runs the 8463.54 Hz IF discriminator, AGC on,
AFC off, wide filter (k6-fd6818b-refcal.md). Its close-range FCS-valid frames
establish function, not weak-signal performance.

## Test plan
1. Compare discriminator and matched-filter DSP with the same B IF, DMA rate,
   seeded packet set, deviation, pre-emphasis, carrier offsets and noise.
   Record valid FCS frames / transmitted frames; report simulated C/N0, not dBm.
2. Bench test separate gain settings with stepped input power, preferably
   conducted through rated attenuators into the receiver; never connect a
   transmitter directly. Record RSSI, valid frames, preambles, bad candidates,
   overruns and IF offset. Sweep gain from AGC baseline; do not assume original
   chip gain register values are optimal.
3. Compare GP0 faster sampling and alternative demodulated audio/bit paths.
   The one-bit IF noise may impose a limit that DSP alone cannot overcome.
4. Use a known-good external APRS modem/receiver as a control, with the same
   packets/antenna conditions where possible. Field audio audibility alone is
   not a measurement of tap SNR.
5. Only promote a new receiver when controlled packet success improves without
   unacceptable CPU cost, clipping, overruns, or regressions at strong signals.

## Initial B-IF simulation
`python3 tools/k6_aprs_sensitivity.py`, seed 11, six frames, 3 kHz
deviation, nominal B IF, 5.493 MS/s, 8 kHz model filter:

| C/N0 (dB-Hz) | Discriminator | Matched filter |
|---|---:|---:|
| 48 | 0/6 | 6/6 |
| 52 | 6/6 | 6/6 |
| 56 | 6/6 | 6/6 |

The frontend is the existing simplified sigma-delta model with its IF
changed to 8463.54 Hz, not a calibrated FD6818B RF model.
