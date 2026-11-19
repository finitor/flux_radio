# Project guidance

- Work in the intended Flux checkout; inspect Git status and preserve unrelated work.
- Keep the K6 browser workbench (`sim/k6ide.py` and `sim/k6ide_templates/`) aligned with changes
  to the emulator and app UI.
- The workbench should bind to `0.0.0.0:5056` by default so it can be followed from another
  machine. The workbench is unauthenticated; bind to loopback on untrusted networks. Do not expose it publicly.
- Keep simulator outputs, virtual SPI images, radio backups, firmware build outputs, and signing
  keys out of Git. Update `.gitignore` when a new generated path is introduced.
- Commit small, coherent workbench changes as they are completed. Inspect status first and stage
  only files for the current change; preserve unrelated in-progress work.
- Emulator evidence does not establish physical-radio or RF behavior.
- For new firmware/module UI work, consult `docs/k6-ui-conventions.md` and keep key semantics, VFO handoff and simulator interactions consistent; document deliberate exceptions.
