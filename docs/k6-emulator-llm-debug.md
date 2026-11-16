# Debugging K6 firmware freezes with an LLM

This guide describes a reproducible loop for asking an LLM to analyze a freeze in
the whole-firmware K6 emulator. The emulator runs the actual Cortex-M0 image; it
does not yet model interrupts, RF, or audio. A matching freeze is useful evidence
about firmware control flow, but not proof that every hardware interaction is
faithful.

## What to give the LLM

Give the model the exact firmware image, module bundle if used, emulator JSON
report, UART log, LCD trace or screenshot, and a short description of the same
steps on the radio. Include the image's source revision and build command when
available. Do not provide the module signing key or a raw SPI backup: the report
contains only a screen snapshot and bounded diagnostic data.

From the repository root, first confirm the CLI and dependencies:

```sh
python3 -m pip install -r sim/k6emu/requirements.txt
python3 -m sim.k6emu --help
```

## Headless reproducible run

Run a fixed instruction budget and save structured diagnostics and the LCD byte
trace. Start with the image and inputs that reproduce the freeze; do not change
several inputs between captures.

```sh
python3 -m sim.k6emu \
  firmware/k6-aura/out-fd6818b/aura-fd6818b-blowfang-host.bin \
  --instructions 20000000 \
  --quantum 256 \
  --spi-flash /home/tyler/blowfang-backups/k6-spiflash-emulator.bin \
  --module-bundle firmware/k6-aura/out-fd6818b/vfo-module-bundle \
  --module-slots 30 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  --key-event 500:MENU:down --key-event 580:MENU:up \
  --report-json /tmp/k6-freeze.json \
  --lcd-trace /tmp/k6-freeze-lcd.jsonl
```

Replace the image, module, slot, and key sequence with the case under study. Key
event times are virtual milliseconds from reset; each event is a press or
release. The key names must match the keypad names accepted by `--press-key` and
the live UI. For a sequence discovered interactively, use the live mode to find
the right navigation, then reproduce it with timestamped key events.

If a run ends before the freeze, increase `--instructions`; use the same
`--quantum`, image, flash, and inputs for comparisons. At a capped run, the
reported `pc` is the last observed program counter. Repeatedly reaching the same
PC with the same screen and no UART progress is a useful spin-loop clue. A
different instruction budget can land at a different PC if execution continues
normally, so compare several snapshots rather than treating one PC as a verdict.

To inspect what the firmware drew, render the captured LCD trace:

```sh
python3 -m sim.k6emu.lcd /tmp/k6-freeze-lcd.jsonl -o /tmp/k6-freeze.svg
```

## Run a module in the interactive emulator

For interactive investigation, overlay the module bundle into virtual SPI and
start live mode. The key file is read locally to create radio-compatible module
images; it is never included in the report.

```sh
python3 -m sim.k6emu \
  firmware/k6-aura/out-fd6818b/aura-fd6818b-blowfang-host.bin \
  --live \
  --spi-flash /home/tyler/blowfang-backups/k6-spiflash-emulator.bin \
  --module-bundle firmware/k6-aura/out-fd6818b/vfo-module-bundle \
  --module-slots 30 \
  --key-file /home/tyler/.config/blowfang/k6-mod.key \
  --report-json /tmp/k6-live-freeze.json \
  --lcd-trace /tmp/k6-live-freeze-lcd.jsonl
```

Use the emulator window to enter the module menu and reproduce the failure.
Closing the window stops the run and writes the summary and requested files.
The report records the module slot/name/size, not the key or module contents.
The virtual SPI flash is in memory; it is not written back unless `--save-spi`
is explicitly supplied.

## Read the JSON report

The schema is `k6emu.report.v1`:

- `run.pc`, `run.instructions`, and `run.virtual_ms_estimate` locate the stop.
- `uart.tail_text` and `uart.tail_hex` contain at most the last 4096 UART bytes;
  `bytes_total` tells whether older output was truncated.
- `mmio.hotspots` summarizes frequently accessed registers;
  `mmio.unmodelled` calls out registers using generic/default behavior;
  `mmio.recent` is a bounded tail of the most recent 256 accesses.
- `fd6818_writes` records recent writes to the simulated radio chip.
- `screen.ram_hex` is the LCD controller RAM snapshot. `lcd_trace_events` and
  the separate JSONL trace preserve the display update stream.
- `modules` identifies virtual modules placed into SPI before execution.

The recent MMIO event's `instruction` field is sampled at emulator scheduling
boundaries, not a cycle-exact timestamp. `cycles_estimate` and virtual
milliseconds are coarse estimates. Avoid interpreting absent interrupt-driven
behavior as a firmware bug until interrupt delivery is implemented.

## Suggested LLM prompt

Attach the report, source checkout/revision, and relevant source files, then ask:

> Diagnose this K6 firmware freeze from the emulator evidence. First restate the
> observed stopping PC, UART tail, last MMIO accesses, screen state, and module
> context. Map the PC to source using the exact build's ELF/map/disassembly; do
> not guess if symbols are missing. Separate direct evidence from hypotheses.
> Check whether the PC is in a loop, whether the loop depends on an unmodelled
> register or interrupt, and whether the same symptom on hardware is compatible
> with that explanation. Propose the smallest reversible source or emulator
> change and one capture that would distinguish the leading hypotheses. Do not
> claim RF/audio or physical-radio behavior from emulator-only evidence.

For address mapping, use the ELF and map from the same build as the raw image.
Depending on the available toolchain, `arm-none-eabi-addr2line` can translate
addresses; Thumb bit 0 may need clearing. If there is no ELF/debug information,
inspect the linker map and disassembly, and report that source mapping is
uncertain.

## Good comparison discipline

Keep one baseline report, then change one factor per run: module slot, key
sequence, ADC input, peripheral model, or firmware patch. Preserve each JSON
report and LCD trace with a descriptive filename. Use the same image, SPI seed,
and virtual inputs for before/after comparisons. If a proposed model change
removes the freeze, verify that the affected firmware path now advances and
record any new unknown MMIO accesses; an emulator workaround alone does not
establish that the physical radio is fixed.
