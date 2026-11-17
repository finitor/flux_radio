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

## Flash budget policy (enforced by pack builds)

Application flash is 120 KiB (122,880 bytes). The Base-only profile is capped at **96 KiB (98,304 bytes)**, reserving **24 KiB (24,576 bytes)** for optional firmware capabilities. Combined profiles are capped at 120 KiB; `tools/k6_flash_policy.py` evaluates actual linked ELF sections, not module sizes or a guessed feature cost. `tools/k6_pack_build.py` now rejects over-budget freshly built images. Tests cover both caps and exclude RAM-only `.bss`.

This is an initial **budget enforcement mechanism**, not proof that two arbitrary feature packs fit: actual feature-specific linking and individual per-pack size measurements are still needed. The existing 98,424-byte host build is **120 bytes above the proposed Base-only ceiling**; it is not a Base-only build, and cannot establish Base's size. It does fit the combined-profile 120 KiB limit with 24,456 bytes free. A true Base build must disable scanner and other optional services before its 96 KiB check is meaningful.

## Installer validation checkpoint

`python3 tools/k6_pack_install.py PACK --inspect-unverified` validates the staged pack's firmware hash, every module binary and manifest hash, declared module identities/API levels, and resolves the capability dependency graph again. Without `--inspect-unverified`, an un-attested firmware image is refused. This command **does not flash or install anything**; the existing `k6_install.py` remains the sole radio-writing implementation. Do not manually flip `capabilities_verified` to true: real firmware service gating, a cryptographically bound capability record, and a radio-side compatibility handshake are still required before enabling the guided install transaction.

## Multi-feature matrix

`tools/k6_pack_matrix.py --size-dir DIR --output report.json` consumes **independently linked** `base/size.txt`, `base-scan/size.txt`, `base-aprs/size.txt`, and `base-scan-aprs/size.txt` (from `llvm-size -A`). It fails if Base exceeds 96 KiB, any profile exceeds 120 KiB, or the required Scanner+APRS combination is missing or over budget. Without separately built linked images, it deliberately refuses to claim a successful matrix. Use `python3 tools/k6.py matrix --build` to compile all four profiles sequentially. Current gates select compact scanner and FSK RX callbacks, but do not yet prove complete isolation of all legacy services.

The pack inspector also refuses all radio-writing readiness claims regardless of the mutable `capabilities_verified` lockfile field: that field alone cannot establish firmware ABI compatibility. An independent firmware capability attestation and matching radio-side handshake are required before the installer may be enabled.

## First measured selective linking: compact scanner engine

`K6_SCAN_SERVICE=0` on the FD6818B firmware build replaces the compact host scanner (`xscan_modhost.o`) with a small, ABI-preserving unavailable-service implementation. The module API field layout stays stable; scanner initialization and stepping fail instead of calling missing code. `tools/k6_pack_build.py` now selects this automatically when the `scan` pack is absent. The full scanner engine and legacy Explore application are **not yet entirely removed** from Base; APRS-specific service gating and runtime capability negotiation remain to be implemented.

Measured with the same `pager-explore,fd6818b,spilib,txdog,blowfang-host` Cargo features on the local workstation:

| Service configuration | Linked MCU flash | Headroom to 120 KiB |
| --- | ---: | ---: |
| Scanner host disabled | 94,900 bytes | 27,980 bytes |
| Scanner host enabled | 98,424 bytes | 24,456 bytes |

This saves **3,524 bytes** and passes the 96 KiB Base budget, but is not yet a verified feature-complete Base/Scanner/APRS profile matrix. The images were unkeyed, not flashed, and not hardware tested.

## FD6818B FSK receive service gate

`K6_FSK_RX_SERVICE=0` excludes the real FD6818B FSK RX callbacks from the Rust link and supplies failure-returning API-compatible stubs. The APRS pack selects `K6_FSK_RX_SERVICE=1`; the Base and Scan-only packs select 0. The original hardware radio driver and other FSK/TX paths may still be referenced elsewhere, so this is **callback-level gating**, not yet a complete APRS-only subsystem split.

Measured on the same host, with scanner service disabled: Base with FSK RX disabled **94,500 bytes**; with FSK RX enabled **94,900 bytes** (400 bytes incremental). Both are below the 120 KiB application limit; Base is below its 96 KiB ceiling. The disabled build must explicitly retain `-C link-arg=-Tlink.x` when supplying `RUSTFLAGS`, or Cargo can silently produce an invalid 24-byte image; the build script now preserves that linker argument. These images are not hardware verified or ready for installation.

## Build-time LCD themes

The firmware builder offers Flux (default), Classic and Minimal active-VFO styles.
Flux uses a one-pixel top border and left rail, Classic uses the original VFO
arrow, and Minimal uses the left rail alone. These are compile-time presentation
choices; they do not change capabilities, key assignments or module ABI. Module
screens retain their own layouts. Browser previews are illustrative, not emulator
screenshots. A build is still explicit and its actual flash budget is checked after linking.

    python3 tools/k6.py plan scan aprs --theme classic
    python3 tools/k6.py build scan aprs --theme minimal

The theme is recorded in the pack lock; non-default themes are also bound to the
host build receipt. Legacy receipts and packs without a theme mean Flux.


### Visual theme editor

Open the Catalog firmware builder at `/profiles`. The theme editor draws a
seven-by-eight pixel active VFO marker, with optional top border and left rail.
Switch the preview between VFO A and B. Give designs names and save them in
browser-local storage; selecting a saved design makes it the active build theme.
The preview is illustrative, not an emulator screenshot.

Copy the theme code to share it, or paste one into the editor and choose Load code.
The custom theme code is directly portable to the CLI, e.g.:

    python3 tools/k6.py build base --theme custom-01-c0f0fcfefcf0c000

The two flags are top border and left rail (0/1); the sixteen hex digits are
eight row bytes, most significant bit first, with the low bit reserved/zero.
An entirely blank marker without either border is rejected. The immutable code
is included in the package lock and receipt so editing a saved browser theme
cannot change a previous build. No arbitrary source code is accepted.
