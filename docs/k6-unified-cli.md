# Unified K6 CLI and feature-pack ownership

Use `python3 tools/k6.py` as the common entry point. It delegates to the existing, tested implementation of each operation rather than creating a second serial protocol or flashing implementation.

```sh
python3 tools/k6.py plan scan aprs
python3 tools/k6.py build scan aprs --output /tmp/k6-scan-aprs
python3 tools/k6.py inspect /tmp/k6-scan-aprs
python3 tools/k6.py matrix --size-dir /path/to/independently-linked/sizes
python3 tools/k6.py catalog                  # local web UI, default localhost:5055
python3 tools/k6.py radio --port /dev/ttyUSB0 status
python3 tools/k6.py radio --port /dev/ttyUSB0 backup -o /safe/place/spi.bin
```

**Radio writes:** `radio flash`, `radio load`, and `radio install` delegate directly to `k6_install.py`; they can modify a physical radio. Use them only with a verified compatible image and explicit operator approval. `build`, `plan`, `inspect`, and `matrix` never contact a radio. The feature-pack installer is deliberately read-only pending independent firmware capability attestation and radio-side negotiation. Do **not** use `radio flash` to bypass that protection for an unverified pack.

## Mandatory ownership policy

`config/k6-feature-packs.json` declares user-facing packs, module requirements, and capabilities. `config/k6-service-gates.json` maps each non-base capability to an owning pack and build environment gate. `tools/k6_pack_policy.py` rejects new capabilities unless they are explicitly declared always-on or assigned to a gate. `tools/k6_pack_build.py` checks this policy before building and derives the gate environment from the selected packs. This prevents silent omission of a gate decision in the pack planner, **but does not prove all implementation code has been excluded**. Each new capability still requires a linked-image comparison and, where relevant, ABI-safe unavailable-service behavior and runtime checks. A planned gate is not an implemented gate.

The catalog remains a separate web UI for now. `k6 catalog` launches it, and the long-term direction is to expose these same CLI operations through its backend, with a single authorization/compatibility policy rather than parallel flash logic.

## Catalog profile planner

The catalog now has a **Feature packs** page at `/profiles`, which uses the same `k6_feature_packs.resolve` and `k6_pack_policy.validate` functions as the CLI. It previews selected packs, module requirements and actual build environment gates; planned packs are disabled. This initial page is deliberately **read-only**: build jobs, progress streaming, flashing and installation are not yet exposed through the web interface. Never present a preview as evidence of a successfully linked or hardware-tested firmware image.

## Verified four-profile compilation and browser build jobs

Run `python3 tools/k6.py matrix --build --output /path/to/report.json` to compile Base, Base+Scan, Base+APRS and Base+Scan+APRS sequentially. The matrix stores each independently linked image, `size.txt`, and plan under `firmware/k6-aura/out-fd6818b/profile-matrix/<profile>/`, and checks the 96 KiB Base / 120 KiB total ceilings. Do not run concurrent matrix and pack builds: the underlying Aura build uses a shared working directory.

First measured four-profile matrix (FD6818B, local workstation):

| Profile | Linked flash bytes | Budget |
| --- | ---: | --- |
| Base | 94,500 | pass |
| Base+Scan | 98,024 | pass |
| Base+APRS | 94,900 | pass |
| Base+Scan+APRS | 98,424 | pass |

The catalog `/profiles` page now offers **Build this profile** after previewing the plan. It starts a single local background subprocess, redirects compiler output to a per-job log, and shows a status page that refreshes every four seconds. Only one browser-started build runs at a time. This is a prototype: jobs are in memory and do not survive web-server restarts, and CLI builds are not coordinated with browser builds. The output is a staged unverified pack, not a flashable, attested release. No serial commands are run by the job manager.

### Shared firmware build serialization

Pack builds and matrix builds now take the same OS-level `flock` lock around the shared Aura build output, including the image-copy and size-verification stages. This prevents two `k6.py build` / `k6.py matrix --build` invocations (including those launched by the catalog) from reading each other's generated images. Builds started directly via the lower-level shell script do not participate in this lock and must not be run concurrently. The catalog's in-memory job queue remains a UI concern; the filesystem lock is the cross-process safety boundary.

Muse Delegate read-only audit `8e2741232680` completed. Its findings on serial handshake identity, module-bundle trust, and rollback need independent verification against the full firmware and pack-install code before enabling any writes. No firmware attestation is claimed by the shared build lock.

### Install preflight trust boundary

`tools/k6_pack_install.py` verifies staged firmware and module SHA-256 hashes, resolved pack requirements, module identity and API level. It now also checks that any module-manifest `sha256` entry agrees with the locked module digest, and rejects modules that unexpectedly claim a firmware-specific build ID. These are **consistency and integrity checks against the supplied lockfile**, not authentication: a malicious actor could replace both payload and lockfile. The installation path remains fail-closed pending independently verifiable firmware identity and on-radio capability negotiation.

### Firmware build receipts (host-side only)

Newly compiled pack and matrix images include `firmware.receipt.json`, recording the firmware binary's SHA-256 and byte count, target, resolved packs, declared capabilities, Cargo features, and effective service gates. `tools/k6_capability_receipt.py` can regenerate and compare the receipt against an image and plan. This is **not** a cryptographic signature, a measurement of actual linked features, or evidence supplied by a running radio; a forged receipt can accompany a forged image. `radio_attested` is always false, and installation remains blocked. Prebuilt images staged with `--skip-firmware-build` do not receive a newly asserted build receipt.

A firmware-side capability protocol is still needed. The generated Aura CPS code lives in `firmware/k6-aura/build/aura-fd6818b-port/src/cps/`, so the implementation must be captured in a repeatable patch or apply script, not edited only in that generated checkout. Muse investigation `28b0985c5d6a` traced the existing CPS read/write dispatch and suggested a new read-only command instead of changing legacy responses; protocol compatibility and on-device behavior remain unverified.

### Experimental radio capability query (cable)

The reproducible Aura build now applies `firmware/k6-aura/apply-capability-query.py` after the cable stack patch. The Blowfang cable session accepts read-only command `0x49` (`I`) at address 0 with empty payload. It returns 16 bytes: `K6CP` magic (4), version `1` (1), capability flags (1: bit 0 module loader, bit 1 scanner, bit 2 FSK RX), module API ceiling (1), reserved zero (1), and eight reserved-zero identity bytes. The flags reflect **declared build gates**, not measured runtime behavior. The original `0x56` (`V`) INFO response remains unchanged. `Cable.capabilities()` in `tools/k6_install.py` parses the optional response and explicitly returns `authenticated=False` and `build_identity_verified=False`.

This is a protocol prototype, **not** proof of running firmware identity. Old firmware may reject `0x49`; callers must fail closed for install decisions. No installer uses this response to enable writes yet. Firmware-side and host-side protocol tests run without hardware; radio behavior remains untested.

### Connected-radio preflight

```sh
python3 tools/k6.py preflight path/to/pack --port /dev/ttyUSB0
```

This checks every staged artifact before connecting, then requests the versioned cable capability record and compares its declared services and module API ceiling to pack/module requirements. A successful comparison returns `capabilities_match: true`, but **always** returns `install_ready: false`, `authenticated: false`, and `build_identity_verified: false`. Missing services or unsupported module API levels produce exit status 1; malformed/unsupported responses or invalid artifacts fail with an error. The port must be supplied explicitly. No firmware or SPI writes are performed, but normal cable-session teardown (`CMD_END`) restarts the radio. Unkeyed builds may report loader code support while refusing all module signatures; this query does not establish key provisioning or operating readiness.

### Capability protocol 2: embedded build identifier

The reproducible FD6818B build now emits the existing 8-byte GNU fast linker build ID for `spilib` (as well as the legacy `voice-explore` build). Capability command `0x49` version 2 returns that ID in bytes 8–15; version 1 remains readable. The legacy INFO command is unchanged. Host receipts include the extracted ID (`null` for legacy images), and preflight independently extracts it from the hash-checked firmware binary and compares it with the radio report. Preflight exits successfully only when both capabilities and build ID match. A missing or mismatched ID fails the comparison. An aligned unique GNU note is required; the ID is not a cryptographic signature or hardware-backed measurement. Key insertion after linking does not change the ID. Key provisioning and key possession remain separate checks. In particular, `build_identity_verified`, `authenticated`, and `install_ready` remain false. No radio-side test or installation was performed.

### Authenticated capability preflight (optional key)

`python3 tools/k6.py preflight PACK --port /dev/ttyUSB0 --key-file PATH` uses a fresh random 16-byte nonce with cable command `0x49`, address zero. The radio returns its 16-byte capability record, one status byte (zero on success), and an 8-byte little-endian SipHash-2-4 tag over `K6CAPAU1 || record || nonce`, using the existing module key. An unprovisioned radio refuses the challenge. The fixed domain cannot be used as a general module-signing oracle. The host compares the tag in constant time, rejects stale/invalid replies, and reports `key_possession_verified` and `capability_report_authenticated` independently of profile compatibility. No module upload, execution, serial-counter advancement or flash write occurs. Without `--key-file`, legacy unauthenticated preflight remains available. Closing the cable session restarts the radio as before. This proves possession of the shared key and authenticates the reported record, **not** firmware measurement, secure boot, or package publisher identity; a device holding the key can lie about its build. `install_ready` remains false pending explicit installation/recovery work and hardware validation.
