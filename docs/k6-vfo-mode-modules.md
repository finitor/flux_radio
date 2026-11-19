# VFO mode modules — design spike

Status: experimental native lifecycle and SPI-loaded callback probes implemented;
production mode selection, complete arena audit and hardware validation pending.

## Findings from the FD6818B host

- Native modulation conversion currently recognizes FM, AM, USB, CW and CWF
  (raw 0–4). Unknown values become FM. Do not add digital protocols directly
  to the RF driver's modulation enum.
- app/side_ops.rs toggle_modulation handles CW cleanup and tunes the watching
  side. This is the natural integration boundary for logical mode selection.
- app/side.rs Side owns ChannelConfig and frequency/offset state. Keep logical
  module selection separate from physical modulation and channel storage.
- app/pager.rs run_module invokes km_run_on_stack synchronously, clears the
  display, owns MOD_CTX, and restores RF state only on return. Existing modules
  cannot safely be called as periodic VFO callbacks without a new contract.
- hal/arena.rs provides 11776 bytes for the compact host. A resident module
  competes with foreground modules, packet staging and shared decoder buffers.

## Proposed architecture

1. Versioned, data-only K6 mode registration descriptor with stable mode ID,
   short display label, required API/services, allowed physical modulation,
   RX/TX capability and declared memory requirements. Discover through the
   existing library validation path; reject ambiguous IDs and malformed records.
   Do not execute code during discovery. Keep existing K6A key registrations.
2. Logical per-side operating mode: Native or a stable module ID plus physical
   fallback. Expose in the modulation chooser, native status row and Designer.
   Never store slot indices or reinterpret unknown legacy modulation values.
   Initially keep selection volatile; design versioned storage only after
   auditing the backup and channel interchange formats.
3. Cooperative callback ABI (proposed, not assigned API level): activate,
   bounded tick / RX event, suspend, resume, deactivate and optional TX request.
   A module returns promptly to the native loop after each callback; host owns
   keys, frequency, timers, LCD, RF and watchdog. Do not expose unrestricted
   legacy blocking callbacks to resident modules. Timing instrumentation is not
   preemption: a hung native callback needs watchdog recovery or a stricter
   execution mechanism.
4. First release: one resident receive-only mode, bound to one VFO. Other VFO
   may remain native; suspend on retune or dual-watch handoff and reset partial
   decoder state. Do not imply simultaneous RF reception. Suspend/unload before
   foreground modules or cable operations reuse the arena; clean up on failure.
5. Start with a minimal test mode (counter/status), then receive-only APRS
   using the existing software Bell 202 implementation after splitting its
   blocking loop. TX is a separate milestone: route PTT through host band,
   power, watchdog, timeout and authorization checks. RX-only modes must not
   accidentally key analog FM; missing or incompatible providers fall back to
   native receive with an explicit indication.

## Acceptance gates

- Existing module binaries and native modulation cycling remain unchanged.
- Mode discovery, duplicate/missing provider, invalid descriptor and removal
  fallback tests; no raw channel-format change.
- Native UI and Designer display correct label; mode selection survives side
  changes within the session; frequency and offset remain intact.
- Simulated activation, tick, suspend, resume and deactivation ordering;
  arena ownership and cable/foreground handoff verified.
- Measure linked Base and Data feature-set profiles plus RAM and stack
  watermark; no mandatory Base growth without a measured review.
- Hardware RX timing and dual-watch behavior before enabling any TX module.

## Related extension requests

Explorer key action 34 uses the existing action contract. GPS Sync settings
entry next to LAT/LON can use a separate launch action registration, not the
resident VFO mode ABI. Keep that one-shot position import distinct from APRS
receive mode.

## Simulator-first implementation

The reference runtime is `sim/k6emu/vfo_modes.py` with regression tests in
`tests/test_k6_vfo_modes.py`. It models discovery, one resident RX-only
provider, switching between sides, retune resets, arena handoff and removal.
Its memory reserve and provisional IDs are test parameters, not ABI decisions.
For initial handoffs it unloads and reactivates rather than preserving state.
RX sample routing uses generated Bell 202 audio; this does not yet run the
resident module decoder. The existing transition-following slicer tests
exercise AX.25 recovery separately.

Next: introduce a compiled minimal mode probe and host dispatcher, instrument
callback entry/exit and arena ownership in the Unicorn whole-firmware runner,
then port the existing APRS decoder to bounded callbacks. Use synthetic and
recorded audio fixtures and compare decoded packets. Do not claim hardware
timing from the emulator. The full firmware must be tested for side switching,
PTT inhibition, module removal and foreground/cable handoff before release.

Run: `python3 -m pytest -q tests/test_k6_vfo_modes.py tests/test_k6_aprs_signal.py tests/test_k6_aprs_slicer.py`.

## Feature pack decision (2026-11-18)

Gate resident VFO mode discovery, selection UI, dispatch, and memory ownership
under the existing Data (digital) pack: K6_FSK_RX_SERVICE=1 / not(k6_no_fsk_rx).
Base, Scan and Designer alone must not link the resident runtime. Ordinary
launchable APRS modules remain independent of Data; only APRS-as-VFO-mode
requires Data. Designer should display the logical mode label when Data is
present, without making Designer a prerequisite. Advertise a separate runtime
capability only after the implementation passes whole-image tests. Measure
Base, Data, and Data+Designer independently.

The isolated ARM dispatcher/probe is in c/k6/vfo_mode_probe.c and
tests/test_k6_vfo_mode_thumb.py. The native milestones below supersede this
original isolated-test milestone.


## Feature-set decision (2026-11-18)

Use the existing Data feature set (K6_FSK_RX_SERVICE=1 / not k6_no_fsk_rx)
for the cooperative native VFO dispatcher and mode discovery. No additional
pack or mandatory Base code. Existing standalone APRS remains usable without
Data. Do not advertise a resident-mode capability until the native loop and
loader actually implement it. The isolated Cortex-M0 probe in
c/k6/vfo_mode_probe.c passes tests/test_k6_vfo_mode_thumb.py; integrate into
the native loop next, then measure Base/Data size and arena usage.

## Native lifecycle probe milestone

An experimental Data-only image is built with K6_VFO_PROBE=1 and
K6_FSK_RX_SERVICE=1. The default image does not enable the probe. The native
main loop calls the actual C dispatcher with watched frequency metadata, resets
on side/frequency changes, and stops outside standby, while asleep, on TX/CW,
and before cable sessions. This is not a sample feed or a user-selectable
mode. The built-in probe now uses 16 bytes at the base of the shared arena, plus
dispatcher/bookkeeping in the main frame. It invalidates cached legacy modules,
reserves the upper 4096 bytes for alternate stacks, and checks a boundary guard.
This reserve remains experimental; the complete arena ownership audit is pending.
The opt-in whole-image test hooks the C callback in Unicorn and checks that
the actual boot reaches START and repeated RX metadata ticks.

Do not advertise the resident runtime capability or publish this as a normal
Catalog image. Next measure stack high water and implement an exclusive
arena lease with eviction of cached foreground modules before resident load,
and stop/release before foreground/cable/voice operations.

## SPI-backed probe milestone (2026-11-18)

`K6_VFO_SPI_PROBE=1 K6_FSK_RX_SERVICE=1` enables an opt-in native runtime that
discovers experimental mode ID 41 and loads it using the shared SPI validation
path. It invokes the actual callback from RAM, with separate aligned state.
`tools/k6_resident_probe.py` builds the position-independent metadata counter
image without installing it. See `docs/k6-resident-loader.md` for its envelope.
Default firmware does not enable this runtime and no capability is advertised.

The probe scans metadata each tick to catch missing/ambiguous providers. This is
an intentionally simple test path, not the final discovery/cache policy. Load
or callback failure latches the runtime off until reboot. Metadata disappearance
stops the callback and permits rediscovery. Cable entry stops it before a session
can change SPI or arena contents. Sotto builds refuse the experimental lease.

The whole-firmware test is `tests/test_k6_vfo_spi_probe.py`; set
`K6_SIM_VFO_SPI_IMAGE` and `K6_SIM_VFO_SPI_ELF` to the matching cable-only
SPI-probe build. It runs real firmware in Unicorn, not the Python reference
runtime. The probe receives watched-frequency metadata, not audio samples.
User-selectable modes, RX-only PTT inhibition, sample delivery, stack high-water
measurement and hardware timing remain separate milestones.

Validation on 2026-11-18: 10 C-loader tests, 4 reference-runtime tests and the
isolated Thumb dispatcher test pass. Both whole-image SPI probe tests pass:
discovery and RAM execution, removal/reload, a real queued foreground module
returning through the normal launcher, cable-session stop, and guard corruption.
The foreground test exposed duplicate queue polls inserted by successive build
overlays. The runtime overlay now normalizes that block to one guarded poll.
The matching cable-only test image SHA-256 is
`6ca6d6f4a9af550b13422613ece82c0bbdce1ea4ad87b970a68d2e016ad18315`.
Build outputs are ignored under `firmware/k6-aura/out-vfo-spi-probe/`.

The wider loader regression run had 52 passes and 5 failures: three require the
missing `capstone` test dependency; the empty-slot return-code and API-level
expectation failures reproduce using the pre-change C sources. These are not
counted as passing. `/dev/ttyUSB0` answered a read-only status request; no radio
firmware or library writes were performed. Next measure stack high water and
Base/Data/Data+Designer linked sizes before physical-radio validation.

## Scheduled module jobs

Add an optional scheduled-job registration, separate from VFO mode selection,
using the same host-owned dispatcher and arena/RF arbitration. Initial use
case: periodic APRS or identification beacons, with a user-selected interval,
frequency, power and enable setting. Use monotonic deadlines for intervals;
wall-clock scheduling may be added separately. No TX on boot by default.
When PTT, RX activity, foreground modules, cable sessions or another RF owner
block a job, defer within a bounded window, then skip rather than burst to
catch up. Apply normal TX frequency/power authorization, busy-channel policy,
timeout and duty-cycle limits; restore the previous VFO/RF configuration on
completion or failure. A scheduled job must not silently change the selected
VFO mode. Initially allow one job at a time, without requiring simultaneous
resident images. Test deadline wraparound, missed intervals, cancellation,
PTT priority and state restoration in the simulator before enabling TX.
Keep modem scheduling in Data; standalone launchable beacon modules retain
their existing behavior. No new scheduler capability is advertised yet.
