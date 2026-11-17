# K6 feature packs: dependency plan

The radio has two different storage budgets: MCU flash for common code/API and external library storage for modules. Build packs should declare **firmware capabilities** separately from **module artifacts**. Firmware provides reusable radio services; modules provide UI, policy, and workflows. Do not compile the same scanner or decoder separately into every module.

`config/k6-feature-packs.json` is the first machine-readable package catalog. `python3 tools/k6_feature_packs.py scan aprs` resolves transitive dependencies, deduplicates module names, and prints a deterministic plan. This is a **dry-run resolver**, not yet a build orchestrator or installer: the existing firmware build still includes capabilities unconditionally and the tool does not flash the radio. `sotto` is intentionally rejected until its decoder and module dependencies are defined.

| Pack | Firmware capability | Bundled modules | Status |
| --- | --- | --- | --- |
| base | module loader | vfo, cardlink | prototype manifest |
| scan | scanner/candidate API, shared observation | surf, explore_scan | prototype manifest |
| aprs | FD6818 FSK RX API | aprsdfsk | prototype manifest |
| sotto | decoder service | pager module TBD | blocked/planned |

## Install design

1. Resolve dependencies and validate target, firmware API level, module API minimums, external-flash slot space and firmware flash budget.
2. Build a reproducible firmware image and slot-independent module bundles; record hashes and a lockfile binding module artifacts to the firmware ABI/capability set.
3. Flash the firmware **only after explicit approval**, then install selected modules using the existing `k6_install` module catalog/slot allocator. Provide a separate manual install action and eventually an opt-in guided transaction.
4. Keep compatibility APIs across upgrades; refuse installation when a module requires an absent capability. Never silently erase other installed modules.

The existing `tools/k6_install.py` already handles module bundles and slot allocation. Extend it with capability/dependency checks instead of building a second independent package manager. For now there is no automatic installation at firmware flash time, and no assumption that firmware flashing can atomically update module storage.

## Scanner migration

`xscan_hot.c` is the first shared engine primitive. It is linked once into firmware and receives consumer-owned hot arrays, preserving the compact module ABI. Further extraction must avoid sharing UI or policy code. Before promoting the scanner pack to a production build option, fix the host patcher build and measure the complete linked image.

## Pack assembly prototype

`python3 tools/k6_pack_build.py scan aprs` invokes the existing FD6818B firmware build and packages all resolved modules with the existing `k6_install.cmd_module_bundle` compiler. The output is `firmware/k6-aura/out-fd6818b/packs/firmware.bin`, `modules/<name>/{module.bin,manifest.json}`, and `pack.lock.json` with SHA-256 hashes, module API levels, target, selected packs and declared capabilities. `--skip-firmware-build --firmware PATH --output DIR` can stage a prebuilt image; use this only if you have verified the image matches the declared capabilities. It does **not** verify that the image implements those capabilities.

An actual Scan+APRS bundle was assembled with five modules against the previously built 98,424-byte host image. This proves compilation and artifact generation, **not** runtime module compatibility: the image is unkeyed and refuses modules, and no physical radio was flashed. Firmware capabilities are still linked unconditionally in the existing build; feature selection does **not yet remove unused services from flash**. Next implement capability-gated C/Rust builds and a compatibility validator before installing bundles. Installation remains an explicit separate action.

## Profile safety checkpoint

The resolver now checks each selected module's declared firmware-capability requirements. A lockfile records `firmware.capabilities_verified=false` until a capability-aware firmware linker/validator exists. Prebuilt firmware staging now requires the explicit `--allow-unverified-firmware` flag. These checks are **build-planning guardrails**, not proof that a running firmware image implements a capability or accepts the module's ABI. The existing build still links scanner services even for a `base` profile. Do not offer automatic install or mark profiles hardware-ready yet.

The recommended next implementation is compile-time gating at the Rust API initializer **and** C archive object selection, using a single generated capability definition; otherwise removing the scanner object would leave unresolved `kmx_xs_*` symbols. Keep the core module ABI stable and reject absent capabilities before loading a module. Profiles should become tested combinations rather than manually edited compiler switches.
