# APRS RX research follow-up — 2026-11-17

Scope: source review and external developer reports. No new radio experiment,
firmware change, or claim of successful K6 decoding. Earlier hardware results
are recorded in `k6-aprs-b-rx-audit.md`.

## Comparable reports

1. [F4HWN UV-K1/K5-v3 APRS RX](https://github.com/armel/uv-k1-k5v3-firmware-custom/blob/main/App/apps/aprsrx/README.md)
   reports failure of BK4829 hardware FSK reception with an FT3D, followed by
   successful software decoding of sampled audio. Its receiver uses continuous
   acquisition, tone normalization, three decision thresholds, and clock
   recovery. It explicitly budgets keypad/display pauses. Its PA4 audio input
   is board-specific: our K6 PA4 assignment does not establish that input.
2. [RadioFoundry DM-32 bring-up](https://github.com/RadioFoundry/RadioFoundry/blob/main/docs/testing/dm32-bringup.md#13-aprs)
   reports receive-tone imbalance of 6–8 dB plus 320–400 Hz contamination.
   A second, high-pass-filtered demodulator path recovered frames lost by the
   first. This uses FD6818 audio through HR_C7000, not our FD6818B GP0 path;
   it motivates measurements rather than direct register or filter copying.
3. [TA1JS issue #1](https://github.com/bcanata/uv-k5-firmware-ta1js/issues/1)
   documents packets received by software modems but rejected by a TH-D75.
   Measurement corrected the initial diagnosis: its transmitter produced
   1200/1800 Hz instead of Bell 202's 1200/2200 Hz. This concerns another
   radio/chip and the opposite direction from our D74-to-K6 failure. It is
   evidence that headline APRS compatibility and FSK register names are
   insufficient; validate actual tones and interoperability.
4. [UV-5RH hardware investigation](https://github.com/amoxu/Baofeng-UV-5RM-5RH-RE/issues/18)
   explicitly distinguishes FD6818B from FD6818 register compatibility.
   Working older-chip recipes do not establish B-chip modem behavior.

No directly matching, confirmed FD6818B K6 APRS fix was found in this search.
The Blowfang open-issue listing returned no entries. That is not proof that
no related discussion or fix exists elsewhere.

## Findings in our code

`c/k6/mod/aprsclk.c` has both hardware-FSK variants and a software IF receiver.
`aprsifbrx.c` enables the latter with AGC active (`GAIN13=0`). Earlier captures
recorded an active GP0/PB1 signal path, but no complete valid AX.25 packet.

The current DMA accounting is a specific concern: `poll()` increments `laps`
only when the current ring position is lower than the previous one. Complete
wraps between polls are indistinguishable from no wrap or a partial wrap.
`drain()` therefore cannot reliably infer all overruns from this counter.
`lost=0` is not sufficient evidence of uninterrupted acquisition. This is a
source-level limitation, not proof it caused a particular supplied recording.

The ring holds roughly 0.2 ms. The loop polls keys every 50 ms; its comments
put LCD work at 20–40 ms. Display work ends with `resync()`, deliberately
omitting samples, and suppression depends on already recognizing flags or a
frame. Acquisition startup is consequently vulnerable before synchronization.
Measure keypad, host-service, and decoder execution time on this build.

The software receiver mixes around an inherited 16.92708 kHz IF, then uses
CORDIC FM discrimination and tone correlation/matched filtering. Earlier B-chip
captures showed changing spectra at different RF levels. IF center, gain,
AFC behavior, and symbol timing remain measurements to establish, not values
to change merely because another chip uses them.

## Proposed next experiment

1. Measure maximum elapsed cycles between DMA observations; reject ambiguous
   gaps. Use appropriate DMA event accounting or bounded servicing, with
   explicit timing checks; sticky interrupt flags alone also miss many wraps.
2. Capture with minimal UI/logging during reception and fixed RF conditions.
   Use moderate signal levels and a known D74 packet independently decoded
   by an SDR/audio reference. Keep packet content, timestamps, rate, gain,
   and source/build hashes with each capture.
3. Preserve enough continuous signal for a whole frame. Current 67 ms raw
   windows are useful for tones but insufficient for ordinary AX.25 packets.
   Evaluate reduced-rate discriminator capture or bounded block streaming
   against RAM and serial bandwidth before implementation.
4. Replay the exact recording through the existing decoder and a separate
   reference decoder. Measure tone frequencies, relative levels, sample rate,
   and preamble timing. Compare filtering/normalization/multiple thresholds
   only on identical recordings. Require expected addresses/payload and FCS.
5. Bring the successful bounded DSP/sample path into the Aura host/module
   architecture. Add captured-signal replay to the simulator; modeled FIFO
   injection alone cannot establish live RF demodulation.

Priority: trustworthy acquisition first, measured IF recovery second,
Bell 202 robustness third. Preserve Aura host and the module system.
