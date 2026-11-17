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
