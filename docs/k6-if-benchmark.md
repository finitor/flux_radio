# IF packing benchmark (pre-hardware calibration)

`c/k6/mod/ifbench.c` is a small, receive-neutral level-2 module. It does not
change UART speed, key the transmitter, touch DMA or write flash. It measures
three 8,192-iteration CPU workloads using the existing 100-us `ticks()` API:
integer arithmetic, reading PB1-like bits from a 1-KB ring, and packing them
into a separate 1-KB buffer. It prints decimal ticks and a deterministic
checksum for each stage. It requires at least 2,052 scratch bytes.

Run the emulator baseline:

```sh
python3 -m pytest -q tests/test_k6_ifbench.py
```

At the current **estimated** 1.5 cycles/instruction and 96-MHz CPU model, the
first run gave 10, 12 and 22 ticks respectively: 1.0, 1.2 and 2.2 ms.
These are **simulated MCU time**, not desktop wall time or validated hardware
results. The tests assert the deterministic checksums, not these specific
estimated timings. Compare the three `ifbench` lines from a physical K6 with
the emulator output, and tune the model by workload, not just a global CPI.

**Important caveats:** This is a RAM packing microbenchmark, not a continuous
capture benchmark. It excludes DMA contention, UART interrupts, radio register
access and scheduler stalls. The existing GP0 DMA notes (`c/k6/mod/gp0dma.c`)
report ~5.7 million transfers/s on physical hardware in one configuration;
85.8 kS/s is the *effective* sample rate used by the experimental simulator,
not a verified rate for this DMA path. We must measure the actual effective
capture rate and loss before sizing a sustained serial transport.

Hardware follow-up: run IF BENCH, collect each timer result, compare with
simulation, then separately test UART baud and sustained binary throughput.
Do not change the default 115,200-baud serial setting during these tests.

## DMA timing calibration (simulator)

`sim/k6emu/rx_dma.py` now provides `GpioRxDma.measured_free_running()`
using the **approximately 5.71 M transfers/s** measured in `gp0dma` run 7.
At a 96 MHz modeled clock, that is about 16.81 CPU cycles per DMA
transfer; 2 ms corresponds to 11,420 transfers. The unit test checks that
count and circular-buffer position, including accumulation across CPU steps.

This is an **opt-in transfer clock**, not a calibrated GP0 IF sample clock.
The existing synthetic APRS injection continues to use its independently
configured 85,800 samples/s. In particular, feeding 85.8 kS/s samples into a
5.71 M transfers/s DMA model without a separate GPIO sample-and-hold stage
would artificially accelerate the RF waveform. The measured rate also does
not prove the transfer request source or exact hardware bus arbitration.

## Serial transport budget for later hardware tests

At 5.71 M raw 1-bit samples/s, bit-packed payload alone is **713,750 B/s**.
A conventional 8N1 UART would need at least **7.14 Mbaud** before framing,
metadata and CPU overhead. Even 230,400 baud cannot sustain that raw capture.
At 85.8 kS/s the packed payload is 10,725 B/s, requiring at least 107,250
baud at 8N1, so 115,200 baud leaves little margin. 230,400 baud would leave
more margin, but is not yet verified on this radio. Hex output doubles the
payload and cannot sustain either rate at 115,200 baud.

Before implementing streaming, measure whether GP0 can be sampled at a
**controlled** lower rate, or decimate the measured high-rate samples with
an explicitly validated anti-aliasing strategy. Otherwise use bounded
recording and delayed export. These figures are transport budgets, not proof
of firmware or UART performance.
