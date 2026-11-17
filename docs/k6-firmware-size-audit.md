# Firmware size audit — display and module host (2026-11-17)

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
