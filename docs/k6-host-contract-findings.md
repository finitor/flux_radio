# Aura / Blowfang shared-host regression loop

## Baseline: 2026-11-15

The radio stops after `K6 LCD page0 command begin`. The simulator stops earlier,
inside the shared LCD callback. These are not yet demonstrated to be the same
failure, but the simulator exposes a real RAM-layout defect worth fixing first.

Baseline image SHA256:
`a6552add714288c5aecb1896f6e4fcf10a657702ea7cbb4d1ebae7c2f30fc104`.
Size: 122712 bytes. The runner verifies that its ELF produces exactly this binary
before using symbol addresses.

| Case | Result | Fault PC | Observation |
| --- | --- | --- | --- |
| Minimal HOST PROBE | FAIL | 0x08004456 | Invalid display pointer in shared LCD callback |
| VFO RADIO | FAIL | 0x08004456 | Same |
| SURF | FAIL | 0x08004456 | Same |

Each run recorded 232 writes to watched control globals while the host stack
was below the end of static RAM. The first corrupting writes map to
`Storage::load_satellites`, before launching any module. Later graphics and UART
formatting calls also write there. The watch history is bounded; it is not an
exhaustive count of all RAM corruption.

Relevant baseline addresses:

- Static allocation end (`__sheap`): `0x200053bc`.
- Saved display pointer (`MOD_DISPLAY`): `0x200052cc`.
- Normal main frame observed at SP `0x20005670`: only 692 bytes above statics.
- `load_satellites` observed at SP `0x20004478`, inside static allocations.
- Separate module stack: `0x200010b0..0x20001530` (1152 bytes).

Restoring a callback pointer does not repair objects already overwritten by the
host stack. The module's reported free stack is also not a measure of the host's
remaining stack. Fix the host RAM budget before further LCD/SPI-specific patches.

## Shared-host fix and current result: 2026-11-15

The root cause was broader than SURF or the LCD callback: Aura's normal main
stack grows down into the end of static RAM. That can corrupt any host global,
including the saved NOR-flash object used by the module library. The fix moves
large boot-time `place_app` construction and the high-stack UI/key paths onto
the otherwise unused module arena, then clears that temporary arena before
runtime use. This keeps the ordinary firmware stack out of app statics and
module-loader control data.

Current image SHA256:
`d01c74cd14317dbe9108d59a5f30ef42a914ff9e70f9927efdf4798cfba8aade`.
The reproducible four-case matrix is in `/tmp/k6-host-contract-arenastack-02`.

| Case | Result | Module entries/returns | LCD callback | CPU fault | Observed stack collisions |
| --- | --- | --- | --- | --- | --- |
| HOST PROBE | PASS | 2 / 2; returned 42 twice | complete | none | 0 |
| VFO RADIO | PASS | 2 / 2 | complete | none | 0 |
| SURF | PASS | 2 / 2 | complete | none | 0 |
| FSKB CAP | PASS | 2 / 2 | complete | none | 0 |

The simulator confirms that the shared module entry/return, stack switch,
callback, and screen paths complete for three different module behaviors. This
supports the shared-host RAM corruption diagnosis; it does not model real
hardware interrupts, RF/audio, serial cable timing, or SPI busy behavior. The
user flashed this exact image and confirmed that it works on the radio. That
hardware result closes the reported LCD hang for this image; it does not by
itself validate RF/audio behavior or every module.

## CARD LINK smoke coverage: 2026-11-16

The keyed host build reserves a 2048-byte stack from the end of the module
arena only when the loaded image name is `CARD LINK`; those bytes are removed
from the module's advertised scratch region. CARD LINK requires 3280 bytes for
a maximum-size record and its LCD preview, which fits in the remaining scratch
area. The change keeps the additional stack out of Aura's constrained static
RAM.

The simulator's new `cardlink` case loads slot 8, observes its LCD hook and
screen flush, processes the scripted exit key, and returns without a CPU fault
or watched stack collision. This checks module UI entry and return only. It
does not emulate RF, K6 FIFO byte order, physical cable I/O, or flash busy
timing; those still require hardware validation.

## Investigation recipe

This is the sequence that led from the field symptom to the fix:

1. Preserve a failing image and its exact ELF. Never use symbol addresses from
   a different build; the harness checks that the ELF reconstructs the image
   byte-for-byte.
2. Reproduce the reported interaction in a fresh emulator instance using a
   private copy of the SPI seed and one signed module. Record UART output, CPU
   registers at faults, LCD bytes/screen, and write history for selected host
   globals (`APP_SLOT`, `MOD_DISPLAY`, `MOD_LCD`, and `CB_NOR`).
3. Compare a tiny module probe with VFO and SURF. Their identical baseline LCD
   callback fault showed the failure was in shared host state, not one module.
4. Map the recorded program counters to source with `llvm-addr2line`, then
   inspect each watched write's stack pointer. The writes mapped to app setup,
   storage loading, and UI/formatting paths while SP had descended below
   `__sheap` into static allocations. This exposed stack/static overlap as the
   common cause and explained why an invalid NOR pointer could appear later.
5. Move large app construction and the deep UI/key paths to the reserved arena
   stack. Clear the arena after boot construction, since it becomes module
   storage at runtime. Keep module execution on its dedicated stack.
6. Rebuild and run the four-case matrix against fresh emulated boards. Require
   two entries and returns per module, no CPU faults, no watched out-of-range
   stack writes, completed LCD callbacks, and the probe's expected return.
   Inspect the captured screen and UART checkpoints before changing gates.
7. Flash only after the simulator passes, then verify the actual radio. The
   user's report confirms the current image works on their K6.

This process keeps the diagnosis tied to artifacts and observable evidence:
same firmware image, isolated emulator state, explicit RAM watches, source
mapping, a repeatable regression matrix, and a final hardware check.

## Repeatable local run

From the repository root, use a fresh output directory for every iteration:

```sh
python3 -m sim.k6emu.host_contract \
  --image firmware/k6-aura/out-fd6818b/aura-fd6818b-blowfang-host.bin \
  --elf firmware/k6-aura/build/aura-fd6818b-port/target/thumbv6m-none-eabi/release/aura \
  --spi-flash /home/tyler/blowfang-backups/k6-spiflash-emulator.bin \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  --bundle firmware/k6-aura/out-fd6818b/vfo-module-bundle \
  --fskb-bundle firmware/k6-aura/out-fd6818b/fskbcap-bundle \
  --cardlink-bundle firmware/k6-aura/out-fd6818b/cardlink-module-bundle \
  --cases probe,vfo,surf,fskbcap,cardlink \
  --out /tmp/k6-host-contract-iteration-01
```

Requires the simulator dependencies plus Clang, lld, and LLVM binary utilities.
This never opens a serial port or writes the supplied SPI backup. It replaces
only the virtual module library and installs one signed module per fresh boot.
The signing key and raw SPI backup are not copied into reports.

The runner builds a tiny probe that checks scratch sentinels, calls the shared
LCD API, and returns 42. The other cases exercise the VFO, SURF, and FSKB CAP
bundle artifacts. `fskbcap` uses slot 31 from the separate FSKB bundle.
Artifacts, key events, execution quantum, and seed hashes are recorded. UART,
CPU-fault registers, watched writes, source mappings, and an SVG of the display
are saved per case. `summary.json` and the exit status report success/failure.

## Iteration gates

1. Preserve the failing image, matching ELF, seed hash, and reports.
2. Make one shared-host change. Keep an explicit budget for host stack, module
   stack, arena, and interrupt headroom; run the complete matrix before drawing
   conclusions from any one module.
3. Rebuild the host, check image size, then rerun the same four cases.
4. Require no CPU fault, no observed host-stack overlap at watched writes, two
   module entries and returns, and completion of the LCD callback. The probe
   must return 42 twice. Check the captured screen as well.
5. A failure produces the next source-level investigation. Do not weaken a gate
   simply to get a pass. If a menu change invalidates the scripted key sequence,
   update the sequence explicitly and retain that fact in the result.
6. Once these pass, extend coverage to repeated menu use, cable load then launch,
   callback lifetime, and bounded SPI waits before a hardware confirmation run.

The current gates are diagnostics, not full memory safety proof. Watches cover
selected control globals. The simulator does not deliver hardware interrupts,
model RF/audio, or reproduce real SPI busy timing. A simulated pass must still
be followed by the physical radio test, especially for the reported LCD-command
hang. Baseline results are in `/tmp/k6-host-contract-baseline` on this machine;
temporary output is not a permanent archive.

Diagnostic machinery checks:

```sh
python3 -m pytest -q tests/test_k6_host_diagnostics.py
```
