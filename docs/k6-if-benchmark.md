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
