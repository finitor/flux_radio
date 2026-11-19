# FD6818B firmware size audit

## Normal Blowfang Base (2026-11-17)

The normal VFO host at `019093c` links **110,256 bytes**, including 97,192 B of
text and 12,848 B of read-only data. This is 11,952 B above the 96 KiB Base
policy and leaves 12,624 B before the physical 120 KiB application limit.
The build used `fd6818b,spilib,txdog-quiet,lean,blowfang-host` with
`K6_SCAN_SERVICE=0` and `K6_FSK_RX_SERVICE=0`, matching the Base build plan.
Use `tools/k6_flash_budget.py` on the freshly linked Base ELF for attribution.

Neither built-in Explore nor the compact scan loop is present in this Base
ELF. The compact scanner entry points resolve to unavailable stubs. The
module API still references the Explore frame renderer, header callback, and
candidate ranking, retaining their code even with the Scan gate off. CW
services have independent module consumers and need a separate dependency
audit before gating them.

The earlier investigation recorded the figures below. Its 3,360-byte Explore
entry was an estimate, not measured evidence. A current matched Base comparison
below now establishes 3,180 bytes of actual savings for the completed extraction.

| Trial | Flash | Reduction vs. control | Behavior to account for |
|---|---:|---:|---|
| Stub Explore frame, header and candidate ranking (estimate, unverified) | 106,888 B | 3,360 B estimated | Keep the module API slot layout and retain real callbacks in Scan builds. |
| Omit satellite and SSTV startup loads and their Aura CPS commands | 109,328 B | 920 B | Legacy programming clients lose those specific records and commands. |
| Disable FM and Search through assignable-key dispatch | 109,820 B | 428 B | Existing assignments need a visible unavailable state or replacement. This trial only removes the tested entry paths. |
| Disable the native APRS beacon action and transmit dispatch | 107,608 B | 2,640 B | This removes native beacon TX while retaining the APRS settings and module AFSK API. The current APRS pack supplies RX. |
| All four changes | 102,924 B | 7,324 B | 4,620 B above the Base design goal with the tradeoffs above. |

At the time of this audit, the next change was to finish the Scan gate for Explore's
renderer and ranking. Follow-up work should profile the shared display/text path and native
settings/key dispatch. The largest named symbols in scope are inlined
aggregates, so their symbol sizes alone do not estimate removable bytes.

## Implemented host trimming

Scan now owns Explore rendering and ranking and native broadcast FM. The
normal Blowfang host removes native frequency Search, including its launcher,
display, key handling and polling. That Search mode is distinct from Scan's
Explore repeater sweep and candidate ranking; the latter remain in the Scan
feature set. Native APRS beacon transmission, plus satellite and SSTV startup
loading and Aura programming commands, were removed from the host paths. APRS
RX and the module AFSK API remain available through their existing interfaces.
Stored record formats were preserved.

| Profile | Linked flash | Budget status |
|---|---:|---|
| Base | 104,748 B | 6,444 B over 96 KiB |
| Base + Scan | 116,232 B | 6,648 B free |
| Base + APRS | 105,140 B | 17,740 B free |
| Base + Scan + APRS | 116,624 B | 6,256 B free |

## Explore extraction measurement (2026-11-18)

With identical pinned Aura, CE profile, and Data/Sotto-disabled settings, the
Base linked image fell from 104364 B to 101184 B after moving shared CW decode
and managed tone observation behind the Scan gate: **3180 B measured savings**.
The matched Base + Scan image is 115832 B, retaining those services under Scan.
All three images are below the 120 KiB hard limit. The 96 KiB Base figure is a
design goal only.

## Current post-Explore profile pair (2026-11-18)

Fresh linked builds for the current refactor measure Base at 101,184 B,
Base+Scan at 115,832 B, Base+Scan+Designer at 122,200 B, and
Base+Scan+Designer+Data at 122,964 B. Data therefore adds 764 B to this matched pair. The combined image
is 84 B over the 122,880 B hard application limit; the previous catalog
estimate was 76 B low because it combined deltas from different baselines.
The 96 KiB Base design goal is exceeded by 2,880 B and does not block builds.
Safe identical-code folding yielded no reduction; forcing Cortex-M0 increased
the linked image by 9,480 B. At that point the image still exceeded the hard
limit by 84 B; the following diagnostic cleanup resolves that overage.

The shared host trim patcher guards the raw calibration debug dumps with
`debug_assertions`. Release `DebugUart::write_str` already discards these logs,
so release behavior is unchanged; debug builds retain both messages. Matched
links measured 1,152 B saved in Base (101,204 to 100,052 B) and 1,156 B in
Base+Scan+Designer+Data (122,964 to 121,808 B).

## PXK6 cable storage moved to Data (2026-11-18)

Base still linked the PXK6 cable list/read/write/erase handlers and their C
record-store validator even when the Data pack and Card Link module were
disabled. The pack service gate now compiles those firmware references and
handlers only when Data is enabled, allowing the linker to omit the `pxk6_*`
store code from Base. The shared CPS cable session
and stable module API slot remain in Base; the module append callback continues
to use its existing unavailable stub there. This moves the cable card-record
management capability to Data without changing cable framing or module API
offsets.

Matched release links measure 3,080 B removed from Base: 100,052 to 96,972 B.
Base is now 1,332 B below the 96 KiB design goal. The no-Data
Base+Scan+Designer image is 117,964 B; enabling Data produces 121,824 B, so
Data adds 3,860 B in that matched pair and the full image leaves 1,056 B under
the 122,880 B hard limit. A Base+Data link measures 100,828 B. Artifacts:
`firmware/k6-aura/build/linked-size-audit-20261118/base-card-cable-gated/size.txt`,
`base-data-card-cable-gated/size.txt`,
`design-scan-card-cable-gated/size.txt`, and
`design-scan-data-card-cable-gated/size.txt`. The Data-enabled ELF retains the
PXK6 store and validator symbols; Base removes them.

## Historical Explore/pager image audit (2026-11-17)

The findings below describe the older image. Use the normal-host measurements
above for current Base decisions.

Baseline: `pager-explore,fd6818b,spilib,txdog` release image, 103,796 / 122,880 flash bytes; 19,084 free. Reproduce with `tools/k6_flash_budget.py` on the release ELF. Estimates below are hypotheses, not additive savings.

## Display

- `ui::draw_pager_only`: 5,312 linked bytes; contains pager, module picker and Explore screen routing. Most expensive UI function; a refactor that isolates screen variants may reduce generic/inlined code, but could also increase call overhead. **Potential 200–1,000 B; medium risk**.
- `ui::mod_flush`: 1,528 linked bytes; it is the module's display path. It calls `draw_mod_screen` for the *current* non-shared-LCD configuration; the `draw_mod_page` implementation is compiled only for `shared_lcd` or `blowfang-host` variants. These are alternatives, not both necessarily present. **Do not delete either** without auditing all images.
- `ui/pager.rs` has two renderers for module screens (graphics and raw controller pages), and a dedicated Explore frame renderer. There is common glyph/rectangle logic, but differing display buffer ownership is intentional. Sharing drawing primitives is worth a small A/B size experiment, not an automatic rewrite. **Potential 0–500 B; medium risk**.
- The current `pager-explore` image has neither `shared_lcd` nor `banded` enabled; `voice-explore` and `blowfang-host` have different rendering constraints. Validate all three before accepting a display refactor.

## Module host

- `app::pager::dispatch`: 2,860 linked bytes; handles many modes and actions. Splitting dispatch paths may help readability but will not necessarily save flash. **Potential 0–500 B; medium risk**.
- `app::pager::mod_vfo_b_tune`: 924 linked bytes. Some operations overlap VFO switching; factoring the shared update sequence may help if the same routine is linked elsewhere. **Potential 0–300 B; medium risk**.
- `app::pager::run_module`: 580 linked bytes; not a major code-size hotspot. However, the generated `run_module` body has repeated identical stack checks (`room < 512` and `module_stack_bytes() < 768`). They are redundant in source; LTO may already remove them. Deduplicate for maintainability, then measure. **Potential 0–100 B; low risk**.
- The build pipeline applies many `apply-*.py` transformations to a pinned Aura checkout. The checked-out generated Rust files have repeated `#[cfg(not(feature = "blowfang-host"))]` attributes and repeated stack checks. Audit patcher idempotence before optimizing generated code: source duplication is not necessarily linked-code duplication.
- The module API table is ABI-sensitive. Do not reorder or delete API entries to save bytes: existing modules rely on stable offsets and API levels.

## Scanner cross-check

Both `xs_step` (2,740 bytes) and `kmx_xs_step` (1,840 bytes) are linked. `xs_step` serves the built-in Explore path; `kmx_xs_step` is exposed to sideloaded Explore modules. Different state ownership and interfaces may justify both. A merger requires behavior/API tests, not a size-only change.

## Recommended controlled experiments

1. Compare `draw_pager_only` before/after extracting a non-generic common draw helper, using the same feature set and exact flash section sum.
2. Try sharing the module-screen rectangle primitive with the Explore renderer, but accept only a measured reduction and pixel-identical output.
3. Fix repeated patcher insertions in the host source, then compare final linked image. Keep patches idempotent across repeated builds.
4. Record the flash delta and functionality tests for every candidate; revert any change that increases size or degrades rendering.

The PXK6 cable card-record commands are unavailable in Base and available in
Data builds. Help-card deck installation through the normal module library is
separate and remains available in Base.

## Follow-up measurements

- The two linked scanner steps are **the same `c/k6/xscan.c` source compiled twice**, not separate implementations. `tools/k6_build.sh` compiles the full `xscan.o` with default `XS_HOT=10`, `XS_COLS=128`, and a compact `xscan_modhost.o` with `XS_HOT=4`, `XS_COLS=1`, `XS_MODULE_NO_PEEK`, `XS_MODULE_NO_SWEEP_DIAG`, `XS_MODULE_NO_REFINE`, and `kmx_` symbol renaming. The latter is only built when `K6_EXPLORE_HOST=1`. Both can be linked in a host+Explore image because their data layouts differ. **Sharing a single scanner implementation requires reconciling ABI and state layout, not algorithm merging.** The savings ceiling from removing the compact implementation is not just `kmx_xs_step`'s 1,840 bytes; its related linked functions also count. Do not remove it until callers and compatibility are tested.
- `run_module` had 56 identical non-host stack checks and 55 identical host stack checks in the persistent generated checkout. A new post-patch normalization script reduces them to one of each. **Measured flash savings: 0 bytes** (LLVM already folded the unreachable duplicates); the source is much easier to inspect. Release build passed.
- A trial display control-flow rewrite (`if/else` to early return) compiled successfully but changed flash by **0 bytes**; reverted. No claim of display savings yet.
