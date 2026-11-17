# IF capture/streaming: lessons from WSPR IQ

Reviewed `c/k6/mod/wspriq.c`, `c/k6/mod/gp0rx.h`,
`docs/k6-ft8-wspr.md`, and `tools/k6_wspr.py`.

`wspriq` **already performs continuous IF capture and serial export**:

- GP0/PB1 DMA sampling with a 1 KB ring, CPU-side draining and loss counts.
- Frequency mixing and two cascaded CIC decimators on the MCU, to about
  199 complex I/Q samples/s (sufficient for narrowband WSPR, not APRS).
- Groups of 15 complex samples as signed I/Q bytes, a per-row scale shift,
  and a 96 MHz timestamp for the final sample. Each line is 53 characters,
  roughly 13 lines/s, encoded as base64 text.
- Host reconstruction uses timestamps, fills gaps for lost lines, fits the
  effective sample rate and resamples before decoding. DMA throughput can
  change by a few percent with CPU load.
- Delays UI work and status/serial output outside the tight DMA drain loop;
  exposes loss counts and idle statistics.

For APRS, preserve the architecture but use a **much wider baseband**. Bell
202's 1200 and 2200 Hz tones require sufficient output sample rate and
anti-alias filtering; 199 complex samples/s is inadequate. A proposed first
prototype would mix to complex baseband and use a properly characterized CIC
chain to produce ~9.6 k complex samples/s, or recover the audio discriminator
at an appropriate rate, then use a binary transport. At 9.6 k complex
samples/s with 8-bit I and Q, payload is 19.2 KB/s, requiring at least
192 kbaud at 8N1 before framing; 230400 might work but needs hardware proof.
A one-bit demodulated/audio-derived stream could be much smaller, but must
retain the information needed to recover Bell 202 under real impairments.

Do **not** reuse WSPR's decimation constants or claim it preserves APRS;
validate anti-alias response, IF center, FM deviation, timestamp continuity,
DMA overruns, and serial throughput with hardware captures. In particular,
previous `gp0dma` measurements show the timer does not pace DMA as expected.

The browser workbench now exposes **direct** and **measured-rate held-GPIO**
DMA modes for both synthetic APRS and imported IF logs. The measured mode
models multiple DMA reads of the same GPIO level; it does not imply calibrated
RF sampling, bus arbitration, or verified decode. Default remains direct.
