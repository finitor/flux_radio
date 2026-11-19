# Flux feature extraction roadmap

## Explore extraction scope (clarified 2026-11-18)

Move all Explore-specific implementation and dependencies from Base into the Scan
feature set. The roughly 3 KiB figure is an estimate, not a measured saving.
Acceptance requires a matched Base-before/Base-after link with Scan disabled in
both, plus a Scan-enabled link and regression checks showing the features remain
available. Base versus Base+Scan measures the whole pack cost, not this extraction.

The shared CW and managed tone helpers are now gated with Scan. Base retains
stable, fail-closed API slots, while CW Listen falls back to its module-local
implementation. The matched links show 3180 B of Base savings; Base + Scan
retains the moved services. API23 offsets, module loading, and TX safety remain
intact. Linked-size acceptance is complete; Explore behavior validation still
has two failing XSCAN checks to resolve.

## First: stabilize the current host
- Rebuild from the pinned Aura revision without relying on an incrementally patched checkout.
- Complete cable-only CRC32 versus keyed OTA selection, including installer, Catalog, capability checks, existing slot migration, and RF ingress rejection.
- Keep module ABI and existing transmit restrictions unchanged. Preserve the known-good image until hardware tests pass.
- Measure independent Base, Base+OTA and Base+Designer linked images; track the 96 KiB Base design goal and enforce only the 120 KiB application limit.

## Subsequent candidates
| Feature set | Scope | Dependencies / constraints |
| --- | --- | --- |
| Sotto (already planned) | Pager UI, voice decoder, codebooks, air transport, playback | Audit shared cable framing and module arena dependencies first. |
| OTA | Authenticated RF native module transfer and telemetry | Retain physical cable loader, whole-image integrity checks, slot validation; no unsigned RF loading. FD6818B air transport still requires a validated implementation. |
| License profiles (default enabled proposed) | Jurisdiction/license-class band tables, policy selection, class-specific transmit checks and user interface | Audit effective TX paths and table sizes. Maintain immutable hardware safety bounds and a central TX authorization gate regardless of profile selection. No unrestricted-TX default; absent/unknown policy fails closed. Receive tuning remains independent. |
| Data | Raw fixed-frame FSK/Card Link and PXK6 cable record management | Implemented behind Data; 3,860 B measured pack cost in the matched full profile. Software APRS remains independent. |
| Scan | Scanner, ranking, Explore observations and FM | Already optional; audit residual native scanner/Explore code. |
| Designer | SPI theme rendering | Already optional; preserve ordinary fallback UI. |
| Legacy pager services | ARQ/telemetry, replay, speech and codebook support | Trace callers and distinguish transport-independent helpers from Sotto/OTA. Remove dead code or move into owning packs. |
| Additional optional native services | DTMF, signaling, broadcast FM, presets, large help tables | Measure before promising removal; do not remove calibration, TX watchdog, power control or hardware protection. |

License profiles are a future design/audit item, not an implemented switch. Separate policy data from central authorization; assess table compression, selectable region/class bundles, and compact fallback policy. A build omitting the optional multi-profile UI/tables must still enforce an explicitly selected legal transmit policy. Verify every PTT, module, beacon, cross-band and raw radio entry point. Hardware limits alone are not legal authorization.

For each candidate: inventory symbols and references; choose stable unavailable ABI stubs where appropriate; add dependency declarations and fail-closed capability checks; build A/B with identical other settings; test enabled/disabled paths; document migration; verify on hardware. Do not relax the flash budget to conceal regressions.

## Milestone 1: cable-only versus authenticated OTA

Host-side regression suite: 64 passing tests in Goal Runner; independent review
added a Designer capability round-trip test, with 23 targeted tests passing.
The tests independently compile C loader objects for CRC and SipHash modes.
Source-level assertions about Rust build gates supplement, but do not replace,
physical radio validation.

Pinned Aura build comparison (application binary bytes):

| Profile | Bytes | Key placeholders | Headroom to 120 KiB |
| --- | ---: | ---: | ---: |
| Base, cable only | 105036 | 0 | 17844 |
| Base + OTA | 105880 | 1 | 17000 |
| Base + Designer | 111308 | 0 | 11572 |

OTA incremental cost: 844 bytes. Designer incremental cost: 6272 bytes.
Base exceeds the 96 KiB target by 6732 bytes. The 96 KiB figure is a design goal only; it never blocks a build. The 120 KiB application limit is the hard cap.
These comparison builds were produced from the pinned upstream checkout;
the Designer capability bit review fix was applied during the build matrix.
Recheck all three after subsequent source changes. Physical radio validation
remains outstanding. OTA here means the authenticated loader; FD6818B RF
transport is not yet hardware validated.

Base recheck before Explore extraction, 2026-11-18: fresh pinned Aura Base with
CE and Scan/Data/Sotto disabled linked to 104364 bytes. After gating the shared
Explore CW and tone helpers to Scan, a matched Base link is 101184 bytes: an
actual 3180-byte Base reduction. Base + Scan links to 115832 bytes, so the
Scan-enabled image retains the moved features and remains under the 120 KiB
application limit. Both new builds use the same pinned Aura revision, CE, and
Data/Sotto-disabled settings. Artifacts: `firmware/k6-aura/out-explore-ab-base-after/flux-explore-base-after.bin`
and `firmware/k6-aura/out-explore-ab-scan/flux-explore-ab-scan.bin`. The earlier
104364-byte Base artifact is
`firmware/k6-aura/out-fd6818b-preserved-base-cardstore-gated-20261118/flux-base-cardstore-gated-check.bin`.
Before the release-diagnostic cleanup, the Base image was 2,880 bytes above the
96 KiB design goal. The goal remains advisory, not a build limit. Safe identical
code folding saved 0 bytes; a forced Cortex-M0 target increased the image by
9,480 bytes. The Base build retained two detailed calibration dumps formatted
through Rust `Debug` even though release `DebugUart` discards its output. The
shared trim patcher now compiles those two dumps only in debug builds; debug
behavior is unchanged and release behavior was already silent. Matched release
links measure 1,152 B saved in Base (101,204 to 100,052 B) and 1,156 B in
Base+Scan+Designer+Data (122,964 to 121,808 B). The latter now leaves 1,072 B
under the 120 KiB hard ceiling. The 96 KiB Base design goal is exceeded by
1,748 B.

The release-diagnostic gate was followed by a PXK6 cable-store extraction.
Base had retained the PC cable record list/read/write/erase handlers and C
store/validator routines without the Data pack. Firmware references now compile
only with Data, allowing the linker to omit the store routines from Base; the
common cable session, module API slot, and fail-closed Base
callback remain stable. Matched Base links fell from 100,052 to 96,972 B, a
3,080 B saving. Base is now 1,332 B below the 96 KiB design goal. The
Base+Scan+Designer image measures 117,964 B without Data; the full
Base+Scan+Designer+Data image measures 121,824 B, with 1,056 B below the hard
limit. Data adds 3,860 B in that matched pair. Base+Data alone measures
100,828 B. Linked section totals and artifact paths are recorded in
`docs/k6-firmware-size-audit.md` and `config/k6-flash-estimates.json`.

Native frequency Search is already removed from the normal Blowfang host. It
is a separate mode from the Scan pack's Explore repeater sweep and ranking;
those Scan functions remain available when selected. Do not count native
Search as a new Base savings opportunity.

Safe identical-code folding still saves 0 bytes. No transmit authorization,
module loading, or module API offsets changed. PXK6 record management over the
PC cable is now part of Data; help-card deck installs remain separate.

Existing signed library slots are not automatically rewritten as CRC slots.
Preserve them; use explicit slot removal/reinstallation after backing up as
appropriate. Never interpret CRC as authentication. Legacy radios without a
capability proof are refused by the pack provisioning path; explicit physical
bootloader recovery remains available.

Next: extract Sotto/pager decoder, codebooks, playback and air transport
while preserving the common module loader, cable protocol and TX authorization.

### Follow-up: radio shortcuts and Designer

- Explorer: advertise stable key action 34; verify module build and native key assignment.
- APRS GPS Sync: register an installed-module settings action adjacent to LAT/LON; hide when absent, fail closed for duplicate providers and use the normal module dispatcher.
- Designer: opt4 linked at 105068 B (228 B saved from opt3), retaining separate memory-name widgets.

### VFO mode extension

See [VFO mode module design spike](k6-vfo-mode-modules.md) for the cooperative ABI and staged RX-first implementation.

### SURF tone handoff (after VFO mode hook)

SURF currently transfers only frequency and modulation via level-16
vfo_b_tune. It displays stored repeater tone data, not a live decode.
Reuse the level-18 managed tone_start/step/stop service while parked in
FM with a confirmed signal. Reset detection on retune/resume, display
confirmed CTCSS/DCS and preserve an unknown state. Add a versioned VFO B
handoff carrying optional confirmed RX tone; do not infer a repeater's TX
tone or offset from its downlink. Test no-tone, stale-tone, DCS polarity,
signal loss and old-host fallback. Keep Explorer grading independent.

#### SURF confirmed-tone visual marker

Keep the normal remembered-peak caret for RF-only confirmation. Use a
distinct diamond or capped caret for a live confirmed CTCSS/DCS observation,
even after the operator moves to another candidate, until that peak expires.
Display the decoded value for the selected peak. Do not use stored repeater
database tones as live observations. A tone is strong evidence, not proof
of station identity. Prefer parked FM observation first, with optional
bounded scan dwell later; never slow every sweep by default.
The existing pm_t is eight bytes, with 128 entries (1024 bytes). Prototype
a small sparse frequency-keyed tone cache rather than growing every peak;
invalidate on band change, expiry, slot reuse and ambiguous frequency match.
Measure module image + scratch without reducing peak capacity unnecessarily.
Both Scan (managed tone API) and capable host version are required for live
decode; ordinary SURF remains usable on Base. Test glyph collisions in a
shared display bin and ensure stale observations cannot enter VFO B.


SURF tone marker: give confirmed-tone peaks a distinct outline/filled glyph
on the spectrum, rather than increasing their RSSI or changing Explorer
ranking. Keep the ordinary caret for energy-only candidates. Store tone only
after managed decoder confirmation, associate it with the exact tuned
channel (not a wide coarse bin), invalidate on reuse/expiry/frequency change,
and reset the decoder on leaving parked FM. A bounded sparse tone cache is
preferable to enlarging all 128 peak records (currently 8 bytes each).
The managed tone service is currently Scan-gated; preserve ordinary SURF
operation without Scan and revisit whether to split the small tone service
out if desired. Data gates resident VFO modes, not this tone feature.
