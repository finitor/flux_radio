# Flux theme studio and non-destructive upgrades

## Goals
- Keep factory appearance and behavior when no custom theme is selected.
- Design the whole 128×64 LCD, including an always-visible background and independent VFO A/B active layers, with transparent/on/off pixels. Preserve live RF state and critical warning readability.
- Change installed themes without reflashing the MCU. Feature changes that alter compiled code still require firmware updates.
- Preserve channels, VFOs, preferences, APRS, module data and calibration across compatible upgrades.

## Staged delivery
1. Finish the compile-time proof of concept: existing legacy cursor, full-screen layers, five-column normal/over-S9 glyphs, frequency font/inset, splash; one backward-compatible share code. Verify flash size and factory restoration. No new physical-radio writes.
2. Define versioned, bounded binary theme package shared by the editor, CLI and firmware. Use the smaller of horizontal sparse runs or packed 2-bit pixels per layer. Include lengths, schema, target, CRC, optional layout metadata; no executable code or RF parameters. Maximum raw layer data is 6 KiB (three 2-bit screens), usually much smaller. Host and device must independently validate.
3. Reuse 16 KiB module-library slots for non-executable theme objects; explicitly select an empty slot and never replace executable modules. Distinct K6T magic is mandatory: older firmware must reject themes rather than treat an unknown K6M flag as executable. Audit slot ownership, selection persistence, atomic replacement and rollback before enabling writes.
4. Implement a compact generic runtime renderer in the optional Designer feature pack, targeting at most 2,048 incremental MCU flash bytes against an identical factory profile. All graphics, glyphs and layout data live in the SPI theme object. Measure MCU text/rodata, RAM, stack, frame time and SPI contention. No extra full screen buffers; bounded reads or small cache. Factory fallback on absent/invalid theme, clear status during TX and emergency overlays. In-place updates are data writes, not firmware writes.
5. Reuse authenticated library transport and add typed theme read/install/select/reset operations with strict bounds, compatibility/version checks, integrity, explicit confirmation, readback, and atomic commit; no arbitrary raw SPI write. Keep host compatibility and existing module authentication policies. Catalog can import/export and install supported themes without MCU reflashing. Hardware test before enabling production writes.
6. Expand movable UI elements incrementally with bounded geometry, collision/visibility checks, preserved frequency precision and accurate preview. Keep factory/menu behavior unchanged where not explicitly themed.
7. Add versioned user-data snapshots: portable user settings/channels/VFO/contacts/APRS/module prefs separated from device-specific calibration and recovery image. Audit actual storage formats, migration compatibility and safe device identity. Existing full SPI dump is read-only recovery evidence, not a generic restore payload.
8. Upgrade flow: validate target, take a fresh verified backup, flash MCU only, compare persisted data, restore/migrate only needed records via bounded commands. Never automatically restore calibration from another radio, overwrite unknown areas or format SPI. Preserve module settings even when service temporarily unavailable. Explicit restore preview and confirmation, pre-restore snapshot, readback and recovery documentation.

## Acceptance
- Old theme codes and factory rendering remain compatible.
- Editor import/export and browser storage round-trip all three layers and custom glyphs.
- A/B selection shows only corresponding cursor; status and warning rendering retains precedence; TX uses factory markings.
- Compiled prototype passes profile budget and generates a matching receipt, or explicitly fails budget without relaxing gates.
- Runtime pack must fit measured budget and recover from malformed packages, interrupted writes, rollback, missing SPI, feature-pack changes.
- Snapshot migration proven on simulated flash, then bench radio with operator approval. No physical hardware verification claimed from emulator/testing alone.

## Current status
Combined compile-time Scan prototype built at 117,196 bytes (122,880-byte limit). This is not the runtime renderer. Runtime installation, portable restore and migration remain planned; the offline K6T package codec is the first runtime-format milestone.
