# K6 feature packs: dependency plan

The radio has two different storage budgets: MCU flash for common code/API and external library storage for modules. Build packs should declare **firmware capabilities** separately from **module artifacts**. Firmware provides reusable radio services; modules provide UI, policy, and workflows. Do not compile the same scanner or decoder separately into every module.

`config/k6-feature-packs.json` is the machine-readable package catalog. `python3 tools/k6_feature_packs.py scan data` resolves transitive dependencies and prints a deterministic plan. `tools/k6_pack_build.py` can assemble the selected linked firmware and module bundles; it does not flash the radio. Physical RF and device runtime checks remain separate.

| Pack | Firmware capability | Bundled modules | Status |
| --- | --- | --- | --- |
| base | module loader and shared cable transport | vfo | linked |
| scan | scanner/candidate API, Explore UI and shared observation | surf, explore_scan | linked behind Scan gate |
| data | raw FD6818 FSK and PXK6 cable record store | cardlink | linked behind Data gate |
| designer | SPI theme renderer | none | linked behind Designer gate |
| sotto | pager decoder and playback | none | linked behind Sotto gate |
| ota | authenticated module upload | none | linked behind OTA gate |

## Install design

1. Resolve dependencies and validate target, firmware API level, module API minimums, external-flash slot space and firmware flash budget.
2. Build a reproducible firmware image and slot-independent module bundles; record hashes and a lockfile binding module artifacts to the firmware ABI/capability set.
3. Flash the firmware after the user chooses the guided action, wait for the new cable session, then replace changed bundled modules by stable identity using the existing `k6_install` slot allocator. Keep separate flash and install actions for recovery.
4. Keep compatibility APIs across upgrades; refuse installation when a module requires an absent capability. Never silently erase other installed modules.

The guided action is a sequence, not an atomic transaction. It checks artifact hashes, the linked firmware receipt, the running radio's build identity and capabilities, and module destinations before replacing a module. It leaves unrelated modules and data slots intact. A first-boot format prompt interrupts the sequence; complete the prompt, then choose the separate Install modules action on the same build.

On a finished build's page, choose **Flash firmware + update modules**. The equivalent CLI action is `python3 tools/k6.py flash-install-pack PACK --port /dev/ttyUSB0 --yes`. It leaves an already-current bundled module installed and replaces a changed version only after the destination has been checked. A separately installed theme package still needs its own empty slot and install action.

## Scanner migration

`xscan_hot.c` is the first shared engine primitive. It is linked once into firmware and receives consumer-owned hot arrays, preserving the compact module ABI. Further extraction must avoid sharing UI or policy code. Before promoting the scanner pack to a production build option, fix the host patcher build and measure the complete linked image.

## Pack assembly prototype

`python3 tools/k6_pack_build.py scan data` invokes the existing FD6818B firmware build and packages resolved modules with the existing `k6_install.cmd_module_bundle` compiler. The output includes the firmware image, module artifacts, and a lockfile with hashes, module API levels, target, selected packs and declared capabilities. `--skip-firmware-build --firmware PATH --output DIR` can stage a prebuilt image; verify that image against its declared capabilities before use.

An earlier Scan+APRS bundle was assembled against a 98,424-byte host image; that artifact predates the current feature-gated links. Current linked builds gate Scan and Data-owned services. The PXK6 cable record handlers and validator are Data-only, while the shared cable transport and stable module API layout remain in Base. Physical RF and runtime behavior still require the separate radio checks listed in the roadmap.

## Profile safety checkpoint

The resolver now checks each selected module's declared firmware-capability requirements. A lockfile records `firmware.capabilities_verified=false` until a capability-aware firmware linker/validator exists. Prebuilt firmware staging now requires the explicit `--allow-unverified-firmware` flag. These checks are **build-planning guardrails**, not proof that a running firmware image implements a capability or accepts the module's ABI. The existing build still links scanner services even for a `base` profile. Do not offer automatic install or mark profiles hardware-ready yet.

The recommended next implementation is compile-time gating at the Rust API initializer **and** C archive object selection, using a single generated capability definition; otherwise removing the scanner object would leave unresolved `kmx_xs_*` symbols. Keep the core module ABI stable and reject absent capabilities before loading a module. Profiles should become tested combinations rather than manually edited compiler switches.

## Flash budget policy (enforced by pack builds)

Application flash is limited to 120 KiB (122,880 bytes). **96 KiB (98,304 bytes)** is the Base design goal, not a build limit. `tools/k6_flash_policy.py` evaluates actual linked ELF sections, not module sizes or a guessed feature cost. `tools/k6_pack_build.py` rejects freshly built images that exceed the 120 KiB limit.

This is an initial **budget enforcement mechanism**, not proof that two arbitrary feature packs fit: actual feature-specific linking and individual per-pack size measurements are still needed. The existing 98,424-byte host build is **120 bytes above the Base design goal**; it is not a Base-only build, and cannot establish Base's size. It does fit the 120 KiB limit with 24,456 bytes free. A true Base build must disable scanner and other optional services before its size can be compared meaningfully with the design goal.

## Installer validation checkpoint

`python3 tools/k6_pack_install.py PACK --inspect-unverified` validates the staged pack's firmware hash, every module binary and manifest hash, declared module identities/API levels, and resolves the capability dependency graph again. Without `--inspect-unverified`, an un-attested firmware image is refused. This command **does not flash or install anything**; the existing `k6_install.py` remains the sole radio-writing implementation. Do not manually flip `capabilities_verified` to true: real firmware service gating, a cryptographically bound capability record, and a radio-side compatibility handshake are still required before enabling the guided install transaction.

## Multi-feature matrix

`tools/k6_pack_matrix.py --size-dir DIR --output report.json` consumes **independently linked** `base/size.txt`, `base-scan/size.txt`, `base-aprs/size.txt`, and `base-scan-aprs/size.txt` (from `llvm-size -A`). It reports whether Base meets the 96 KiB design goal and rejects profiles over 120 KiB or a missing required combination. Without separately built linked images, it deliberately refuses to claim a successful matrix. Use `python3 tools/k6.py matrix --build` to compile all four profiles sequentially. Current gates select compact scanner and FSK RX callbacks, but do not yet prove complete isolation of all legacy services.

The pack inspector also refuses all radio-writing readiness claims regardless of the mutable `capabilities_verified` lockfile field: that field alone cannot establish firmware ABI compatibility. An independent firmware capability attestation and matching radio-side handshake are required before the installer may be enabled.

## First measured selective linking: compact scanner engine

`K6_SCAN_SERVICE=0` on the FD6818B firmware build replaces the compact host scanner (`xscan_modhost.o`) with a small, ABI-preserving unavailable-service implementation. The module API field layout stays stable; scanner initialization and stepping fail instead of calling missing code. `tools/k6_pack_build.py` now selects this automatically when the `scan` pack is absent. The full scanner engine and legacy Explore application are **not yet entirely removed** from Base; APRS-specific service gating and runtime capability negotiation remain to be implemented.

Measured with the same `pager-explore,fd6818b,spilib,txdog,blowfang-host` Cargo features on the local workstation:

| Service configuration | Linked MCU flash | Headroom to 120 KiB |
| --- | ---: | ---: |
| Scanner host disabled | 94,900 bytes | 27,980 bytes |
| Scanner host enabled | 98,424 bytes | 24,456 bytes |

This saves **3,524 bytes** and meets the 96 KiB Base design goal, but is not yet a verified feature-complete Base/Scanner/APRS profile matrix. The images were unkeyed, not flashed, and not hardware tested.

## FD6818B FSK receive service gate

`K6_FSK_RX_SERVICE=0` excludes the real FD6818B FSK RX callbacks from the Rust link and supplies failure-returning API-compatible stubs. The APRS pack selects `K6_FSK_RX_SERVICE=1`; the Base and Scan-only packs select 0. The original hardware radio driver and other FSK/TX paths may still be referenced elsewhere, so this is **callback-level gating**, not yet a complete APRS-only subsystem split.

Measured on the same host, with scanner service disabled: Base with FSK RX disabled **94,500 bytes**; with FSK RX enabled **94,900 bytes** (400 bytes incremental). Both are below the 120 KiB application limit and the 96 KiB Base design goal. The disabled build must explicitly retain `-C link-arg=-Tlink.x` when supplying `RUSTFLAGS`, or Cargo can silently produce an invalid 24-byte image; the build script now preserves that linker argument. These images are not hardware verified or ready for installation.

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
Switch the preview between VFO A and B. Give designs names and save them to
`~/.local/share/flux/themes.json` (or `FLUX_THEME_LIBRARY`); saved designs appear
in Choose a theme and can be selected for a build. Older browser-only saves stay
visible until saved again to the disk library.
The preview is illustrative, not an emulator screenshot.

Copy the theme code to share it, or paste one into the editor and choose Load code.
The custom theme code is directly portable to the CLI, e.g.:

    python3 tools/k6.py build base --theme custom-01-c0f0fcfefcf0c000

The two flags are top border and left rail (0/1); the sixteen hex digits are
eight row bytes, most significant bit first, with the low bit reserved/zero.
An entirely blank marker without either border is rejected. The immutable code
is included in the package lock and receipt so editing a saved browser theme
cannot change a previous build. No arbitrary source code is accepted.

With Designer enabled, a build also writes `theme.fluxtheme` beside the firmware.
Flashing the firmware does not install this data-only package. The build result
page can install it over the cable into an empty radio library slot after a
separate confirmation; themes and modules share slots. The radio checks the
package and the installer reads it back. Select `DISP > THEME > SLOT n` on the
radio afterward. This requires a Designer image with cable protocol 3.

The startup editor shows both boot paths. The full 128 × 64 bitmap comes from
`flux-art-kit/flux-arrays/splash.bin` and is staged in Designer builds as
`boot-splash.bin`. It is stored in the radio's boot-logo sector, separate from
firmware and theme library slots. The build result offers an explicit install
action that backs up the previous bitmap to `~/flux-backups`, writes the new
bitmap in 64-byte Aura cable chunks, and reads it back. A stored full-screen
bitmap takes precedence at boot; configured boot text covers its bottom 22 rows.
When that bitmap is absent, the icon-and-text startup screen appears. Its 16 × 16
icon can be edited as a sprite in the theme editor. Custom icon packages use
K6T v7 and named packages use K6T v8; existing K6T v6/v7 themes remain readable.
The radio's DISP > THEME setting discovers valid installed themes, skips empty
or unrelated module slots, and displays each package name. The installer can
choose a fully erased slot automatically, then verifies the package readback.

Select a built-in theme card or load it via Start from a built-in theme in the
editor. Flux — factory default uses the original border and rail, with no
bitmap marker; Classic and Minimal also have equivalent editable presets.
The built-in card retains its original build identifier until you edit the design.
