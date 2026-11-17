# Flux hardware parity with Aura

Status: proposed, 2026-11-17. No new radio support is claimed by this document.

## Goal and scope

Make every hardware variant supported by upstream Aura a selectable Flux build
target, without requiring the maintainer to own each device. Deliver reproducible
experimental images and a community validation process. Preserve the current
FD6818B target and its defaults throughout the migration.

Source of truth: [Aura](https://github.com/sophiel-meow/bf-k61-firmware-aura)
and its pinned source revisions. The upstream README identifies the UV-K6,
UV-K61, UV-K63, UV-K67, UV-K69 and Aigo E618S as a family, not as individually
validated boards. Other rebrands and unidentified chips are out of scope until
their hardware is identified. Do not infer compatibility from a case label.

| Target ID (proposed) | RF chip ID | Aura basis | Initial Flux status |
| --- | --- | --- | --- |
| k6-fd6818b | 0x4829 | fd6818b, pinned c3aeb17aec0fd09dccf931b52f6c7d5dbf72e7ac | Existing build path |
| k6-fd6818 | 0x4819 | master, commit to be selected and pinned | Planned, not built |
| unknown | any other / unknown | none | Unsupported; no image |

Both known chips belong to the KD32F328CB platform but are not register
compatible. Verify board-level differences (display, flash, GPIO, audio path,
bootloader and calibration layout) rather than assuming every board is identical.

## Phase 0 — baseline and inventory

- [ ] Record clean baseline builds, binary sizes, pack manifests and host ABI
  for the existing target. Preserve the existing defaults and flash policy.
- [ ] Pin a known-good Aura master revision; build unmodified Aura for each
  target in separate work directories with pinned toolchains.
- [ ] Inventory every patch and apply script in firmware/k6-aura, including
  FD6818B FSK/AFSK/KISS, scan, managed signal and host integration. Classify
  common, chipset-specific and unavailable operations.
- [ ] Compare board definitions, flash layouts, peripheral drivers and module
  ABI assumptions; document which capabilities each upstream revision provides.

## Phase 1 — target-aware build system

- [ ] Add a versioned hardware target registry with target ID, upstream repo
  and SHA, RF chip ID, board constraints, Cargo features, flash limits,
  capability flags and support status. Keep radio marketing names as aliases.
- [ ] Refactor build-fd6818b.sh into a shared target-aware entry point, retaining
  the existing script as a compatibility wrapper. Separate source worktrees,
  output paths, caches and locks by target and revision. Fail on patch errors.
- [ ] Apply shared patches once per fresh checkout; isolate divergent patches
  and implement deterministic regeneration. Never change a pinned checkout
  silently or reuse a patched tree from another target.
- [ ] Thread target through tools/k6.py, k6_pack_build.py, k6_build_jobs.py,
  k6_build_identity.py, k6_build_lock.py, pack matrix, manifests and flash
  budget/policy; include it in cache keys and artifact names.
- [ ] Produce a minimal FD6818 Flux host first (boot, basic UI, VFO and module
  runtime); compile out unavailable services rather than fabricate support.
- [ ] Keep module signing, key handling and licensing intact; preserve
  reproducible source provenance and GPL corresponding-source availability.

## Phase 2 — radio abstraction and module compatibility

- [ ] Define a common internal radio service interface for tuning, RX/TX,
  audio, signal strength, scan, FSK, AFSK, interrupts and timing as applicable.
- [ ] Implement FD6818 and FD6818B adapters using the respective Aura drivers.
  Do not reuse incompatible register sequences. Keep TX timeout, PTT release,
  band locks and cleanup behavior consistent.
- [ ] Audit module ABI compatibility, capability query, hardware assumptions
  and service gates. Use explicit unsupported errors and no-op-free failure
  paths; no silent success for absent services.
- [ ] Allow module manifests to declare required capabilities and versions.
  Reject incompatible packs server-side; explain unavailable modules in UI.
  Keep existing module manifests backward compatible where safe.
- [ ] Port and compile each service incrementally; document missing or
  experimental functions rather than blocking the minimal host release.

## Phase 3 — firmware builder and distribution

- [ ] Add target/chip selection to the existing profile planner and builder.
  Show known model aliases separately from actual hardware identification.
  Do not default an unidentified device to a flashable image.
- [ ] Filter modules, service options and size estimates by target; themes stay
  hardware-independent where display capabilities permit.
- [ ] Carry the target through saved profiles, build requests, CLI, logs,
  downloadable filenames and manifests; validate all inputs on the server.
- [ ] Include upstream SHA, Flux SHA, toolchain, chip ID, board constraints,
  modules, theme, image size, checksum and validation level in artifacts.
- [ ] Verify detected chip/board when a trustworthy mechanism is available.
  Bootloader connection alone does not prove chip identity. Refuse known
  mismatches; for unknown identity require explicit manual verification for
  experimental downloads and do not offer automatic flashing.
- [ ] Document backup of stock firmware where possible, SPI/calibration data
  and settings; confirm recovery instructions before volunteer flashing.
  Do not promise that software recovery is always possible.

## Phase 4 — build-only CI (maintainer can complete without new hardware)

- [ ] Expand .github/workflows/k6-firmware.yml into a two-target matrix with
  independent clean builds and pinned revisions.
- [ ] Build minimal and representative/full compatible feature profiles on
  both targets; cover default and non-default themes and starter module bundles.
- [ ] Check linker/map limits, flash budgets, manifests, ABI consistency,
  capability filtering, checksum and target-specific artifacts.
- [ ] Run Python and host/simulator tests, including negative cases for wrong
  chipset, unknown target, incompatible modules and stale cache entries.
- [ ] Publish opt-in experimental CI artifacts and a machine-readable matrix.
  Do not publish a failed target or label successful compilation as RF tested.
- [ ] Keep the existing target green; require both target builds for common
  changes once the second target is established.

## Phase 5 — community hardware validation

No additional physical radios are assumed available to the maintainer.
Recruit volunteers with confirmed FD6818 devices first, then broaden to other
K6-family board revisions and aliases. Release experimental images only after
Phase 4 and documented recovery prerequisites are met.

Validation levels (per target, board revision, feature and firmware SHA):

- Planned: no successful build yet.
- Build verified: clean CI image and automated checks pass; no hardware claim.
- Boot verified: volunteer confirms boot, screen, controls and safe idle.
- RX verified: receive/audio/tuning and relevant receive services exercised.
- TX verified: authorized controlled RF tests with appropriate dummy load,
  attenuation and measurement equipment; verify output, modulation, PTT
  release, timeout and band safeguards.
- Hardware validated: documented core test checklist passes on that specific
  board; unrelated modules remain separately qualified.

Suggested volunteer checklist: identify actual RF chip and board revision;
record factory firmware and backup/recovery procedure; confirm boot, keys,
display, battery indication, safe idle, settings persistence, channel/VFO,
RX/audio/squelch, controlled TX, CPS/serial, module load/unload and return to
VFO. Exercise FSK/AFSK and other available services separately. Stop on
unexpected TX, overheating, failed PTT release, bad audio or recovery failure.
Use lawful frequencies and safe bench procedures; transmitting is not required
for boot/RX reports.

Report template (issue or discussion):

    Model / board revision:
    RF chip ID and identification method:
    Flux commit / Aura commit / artifact SHA256:
    Target / profile / theme / modules:
    Stock backup and recovery verified:
    Boot / controls / persistence:
    RX checks:
    TX checks (or not attempted):
    Module/service checks:
    Failures / reproduction / logs:
    Rollback result (if attempted):

Do not include signing keys, private settings or unredacted radio backups in
public reports. Track evidence by board revision, not just marketing name.

## Definition of done

Build parity: both known Aura targets produce distinct reproducible images in
CI; builder and CLI select either target; compatibility checks and manifests
pass; experimental downloads and recovery guidance are available. This is the
initial deliverable and requires no new physical hardware.

Hardware parity: community evidence supports the specific board and feature
claims. Until then, label each untested combination explicitly. Revisit the
registry when upstream adds chips or board variants; pin and qualify new
revisions before exposing them. Maintain a public matrix showing actual
evidence and known limitations.

## Suggested implementation order

Baseline/inventory -> target registry and isolated builds -> minimal FD6818
host -> CI artifacts -> builder integration -> service/module porting ->
community validation. Each step should be a small reviewable commit; stage
only its files and preserve unrelated in-progress work.
