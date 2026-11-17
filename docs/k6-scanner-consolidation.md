# Scanner engine consolidation: compatibility-first plan

## Finding

The core and module-host scanner are **two builds of the same `c/k6/xscan.c`**. This is not algorithm divergence. The host build uses `XS_HOT=4`, `XS_COLS=1`, disables peek, sweep diagnostics, and refinement, and renames exported functions to `kmx_xs_*`. Core uses `XS_HOT=10`, `XS_COLS=128` and all features. The module's `explore_t` embeds the compact `xs_t` by value and supplies a 401-byte scan buffer reused for CW decoding. Its API is an existing level-20+ binary contract.

## Why an alias is unsafe

The scanner stores `hot[XS_HOT]` **inside** `xs_t`, followed by other fields, and `XS_COLS` changes the scan buffer size. Both change offsets/size. Replacing `kmx_xs_step` with `xs_step` or passing a compact `xs_t` to the full implementation would overrun module-owned memory. The module also intentionally disables costly frequency refinement and peek; full engine must preserve those settings.

## Preferred design

Keep existing API function pointers and module layout intact. Extract the scanner's core step logic into one internal implementation that takes an explicit state *view*: pointers to common fields, hot array and capacity, row buffer and column count, and optional callbacks/feature flags. Provide two small adapters (`xs_*` and `kmx_xs_*`) that marshal each legacy layout into the view. This can retain current state sizes and behavior without a module ABI bump. A simpler alternative is a single common state with a versioned new module API, but that requires migrating/rebuilding all modules and more RAM; do not silently change existing ABI.

The view/adapter approach is not guaranteed to save flash: marshaling can cost more than the removed duplicate code. Test the linked release size before adopting. A third option is retaining the full engine and exporting a new module-only service with host-owned state, preserving the old API as compatibility shim; this is larger short-term but allows later migration.

## Flash ceiling and measurement

Current ELF has `xs_step` 2,740 bytes and `kmx_xs_step` 1,840 bytes, plus their helpers. The maximum practical savings is *less than the entire compact scanner*, because adapters and dynamic-capacity loops will remain. **Initial target: 1–2 KiB**, conditional on a measured build. A scanner-size comparison must use a build with `blowfang-host` and both engines actually linked. The earlier 103,796-byte release image was compiled using the default `pager-explore,fd6818b,spilib,txdog` Cargo features but appears to retain host symbols in the current generated checkout; do not assume it represents a clean host-enabled build. Rebuild both variants with the exact same feature flags and fresh C archive.

## Validation gates

1. Baseline both actual release configurations, including `blowfang-host`, with clean C archive and fresh Rust link.
2. Add compile-time assertions on `sizeof(xs_t)`, offsets of the hot array and tail, and `sizeof(explore_t)` for the compact module; test with M0 Clang and host tests.
3. Record deterministic scan traces from core and module engines: sweep/floor, weak signals, repeated overs, spur rejection, hot-list replacement, pause/resume, and long-running scans. Compare old/new outputs per variant.
4. Keep the existing `explore_xs_*` API function offsets and behavior. Validate Surf and sideloadable Explore UI, waterfall, manual Try, and tone/CW identification.
5. Run scanner unit tests and release builds for both variants; hardware test on radio before considering it production-safe.

## Existing failures unrelated to this refactor

The 2026-11-17 baseline test run had 36 passing, two failing: the expected unresolved symbol whitelist omitted `ex_seen`, and the weak-one-off scenario found a candidate despite weak `W` lines. Fix or characterize those **before** using test results to certify the consolidation.

**Status: design investigation only. No scanner behavior or module ABI modified.**
