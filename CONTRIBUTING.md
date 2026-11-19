# Contributing to Flux

Flux is experimental; keep contributions focused and identify the exact radio/chip variant and firmware revision involved. Open an issue for hardware reports and include reproduction steps, logs with private data removed, and whether the behavior was observed in the simulator or on a physical radio.

- Initialize submodules, install dependencies and follow the README build instructions.
- Run `python -m pytest` from the repository root. The root suite excludes the independent Sotto suite; the tooling CI workflow runs a smaller smoke-test subset.
- Keep UI behavior consistent with `docs/k6-ui-conventions.md`, and update documentation and tests alongside changes.
- Do not commit generated firmware, radio dumps, device-specific calibration, signing keys or local build outputs. The unsigned SDK example bundle is the deliberate exception; regenerate its manifest if changing it.
- Preserve upstream copyright notices and applicable licenses. See `THIRD_PARTY.md`.
- Never treat emulator results as proof of RF performance; use appropriate test equipment and operate within applicable rules.

Do not expose the unauthenticated local catalog or simulator to untrusted networks. Report security-sensitive findings privately to the maintainer rather than publishing secrets or exploitable device data.
