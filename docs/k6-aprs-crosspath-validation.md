# APRS decoder cross-path validation

Run: `python3 -m pytest -q tests/test_k6_aprs_crosspath.py`

The cross-path fixture uses one deterministic AX.25 UI frame (`AG7SU-7>APRS`,
`>crosspath validation`) and checks three independently useful properties:

1. The browser/simulator APRS frame generator produces the exact same AX.25
   frame bytes and FCS as `modem.aprs.frame`.
2. Its Bell 202 audio is decoded back to the **exact frame bytes** by the
   independent Python audio decoder.
3. Its simulated one-bit IF reaches the actual Cortex-M0 IF-capture module;
   all 8192 captured samples match the injected GPIO waveform, including the
   DMA start offset.

Separately, `tests/test_k6_aprsclk.py::test_aprsdfsk_reads_the_bench_captures_on_the_emulated_m0`
validates the actual on-radio APRS decoder against existing bench-derived
plain-FSK chip samples. These are **parallel paths**, not a connected
end-to-end IF-to-APRS decoder test. The IF capture module captures only a
short burst and does not demodulate AX.25. The next step is to bridge the
synthetic IF discriminator into the FD6818 plain-FSK sample model and run the
actual `aprsdfsk` module on that signal, checking recovered frame contents.
The module's current serial report only exposes callsign/metadata; a
byte-for-byte frame comparison will require a test-only frame export or an
instrumented decoder boundary. No real-radio success is implied.

## Audio-to-plain-FSK bridge investigation

`sim/k6emu/aprs_slicer.py` and `tests/test_k6_aprs_slicer.py` add a simple
uniform-clock 4800 Hz audio sign sampler. It reproduces the expected crossing
counts for continuous 1200 and 2200 Hz tones, **but it does not decode an
AX.25 frame** when passed through `modem.aprs.dfsk_line`: that test is kept as
a strict expected failure. This is a useful negative result, not a decoder
success. The FD6818 plain-FSK receiver follows zero crossings and its sample
intervals vary with the tone, whereas a uniform 4800 Hz sampler quantizes
those intervals differently. Next investigate a transition-following slicer
with calibrated timestamp/phase behavior and then feed its output to the
existing emulated Cortex-M0 `aprsdfsk` harness. Do not substitute generated
HDLC bits directly and claim IF-to-decoder validation.
