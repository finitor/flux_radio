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

The experiments below used a private copy of the generated source and built
against an unmodified control from that same copy (110,248 B, 8 B below the
production baseline). These are link-size experiments. They have no runtime
validation and were not applied to the firmware.

| Trial | Flash | Reduction vs. control | Behavior to account for |
|---|---:|---:|---|
| Stub Explore frame, header and candidate ranking | 106,888 B | 3,360 B | Keep the module API slot layout and retain real callbacks in Scan builds. |
| Omit satellite and SSTV startup loads and their Aura CPS commands | 109,328 B | 920 B | Legacy programming clients lose those specific records and commands. |
| Disable FM and Search through assignable-key dispatch | 109,820 B | 428 B | Existing assignments need a visible unavailable state or replacement. This trial only removes the tested entry paths. |
| Disable the native APRS beacon action and transmit dispatch | 107,608 B | 2,640 B | This removes native beacon TX while retaining the APRS settings and module AFSK API. The current APRS pack supplies RX. |
| All four changes | 102,924 B | 7,324 B | 4,620 B above the Base policy with the tradeoffs above. |

The lowest-impact next change is to finish the Scan gate for Explore's
renderer and ranking. Then profile the shared display/text path and native
settings/key dispatch. The largest named symbols in scope are inlined
aggregates, so their symbol sizes alone do not estimate removable bytes.

## Implemented host trimming

Scan now owns Explore rendering and ranking and native broadcast FM. The
normal host retains native frequency Search, including launcher, display,
key handling and polling. Native APRS beacon transmission, plus satellite
and SSTV startup loading and Aura programming commands, were removed from
the host paths. APRS RX and the module AFSK API remain available through
their existing interfaces. Stored record formats were preserved.

| Profile | Linked flash | Budget status |
|---|---:|---|
| Base | 104,748 B | 6,444 B over 96 KiB |
| Base + Scan | 116,232 B | 6,648 B free |
| Base + APRS | 105,140 B | 17,740 B free |
| Base + Scan + APRS | 116,624 B | 6,256 B free |

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

**No functionality removed during this audit.**

## Follow-up measurements

- The two linked scanner steps are **the same `c/k6/xscan.c` source compiled twice**, not separate implementations. `tools/k6_build.sh` compiles the full `xscan.o` with default `XS_HOT=10`, `XS_COLS=128`, and a compact `xscan_modhost.o` with `XS_HOT=4`, `XS_COLS=1`, `XS_MODULE_NO_PEEK`, `XS_MODULE_NO_SWEEP_DIAG`, `XS_MODULE_NO_REFINE`, and `kmx_` symbol renaming. The latter is only built when `K6_EXPLORE_HOST=1`. Both can be linked in a host+Explore image because their data layouts differ. **Sharing a single scanner implementation requires reconciling ABI and state layout, not algorithm merging.** The savings ceiling from removing the compact implementation is not just `kmx_xs_step`'s 1,840 bytes; its related linked functions also count. Do not remove it until callers and compatibility are tested.
- `run_module` had 56 identical non-host stack checks and 55 identical host stack checks in the persistent generated checkout. A new post-patch normalization script reduces them to one of each. **Measured flash savings: 0 bytes** (LLVM already folded the unreachable duplicates); the source is much easier to inspect. Release build passed.
- A trial display control-flow rewrite (`if/else` to early return) compiled successfully but changed flash by **0 bytes**; reverted. No claim of display savings yet.
