# Project guidance

- This is the canonical checkout for this work: `/home/tyler/dev/ag7su-blowfang` (resolved path
  `/storage5/dev/ag7su-blowfang`). Keep future AG7SU Blowfang work here; do not switch to the
  sibling `/home/tyler/dev/blowfang` checkout unless Tyler explicitly asks.
- Keep the K6 browser workbench (`sim/k6ide.py` and `sim/k6ide_templates/`) aligned with changes
  to the emulator and app UI.
- The workbench should bind to `0.0.0.0:5056` by default so it can be followed from another
  machine. Preserve its per-run API token requirement for remote access.
- Keep simulator outputs, virtual SPI images, radio backups, firmware build outputs, and signing
  keys out of Git. Update `.gitignore` when a new generated path is introduced.
- Commit small, coherent workbench changes as they are completed. Inspect status first and stage
  only files for the current change; preserve unrelated in-progress work.
- Emulator evidence does not establish physical-radio or RF behavior.
