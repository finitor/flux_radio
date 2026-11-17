#!/usr/bin/env python3
"""Use scheduler ticks for CW break-in hang timing and give Full a usable gap."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src"

mod = root / "app/mod.rs"
text = mod.read_text()
text = text.replace(
    "/// BK-IN=Full's equivalent: much shorter\nconst CW_FULL_HANG_TICKS: u16 = 6;",
    "/// BK-IN=Full's hang bridges element gaps while keeping break-in shorter than Semi.\n"
    "const CW_FULL_HANG_TICKS: u16 = 12;",
    1,
)
old = '''    pub fn poll_cw_hang(&mut self, syst: &mut SYST) {
        tx::poll_cw_hang(self, syst);
    }
'''.replace("+", "")
new = '''    pub fn poll_cw_hang(&mut self, syst: &mut SYST, ticks_10ms: u16) {
        tx::poll_cw_hang(self, syst, ticks_10ms);
    }
'''.replace("+", "")
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit("app/mod.rs: cannot locate CW hang wrapper")
mod.write_text(text)

tx = root / "app/tx.rs"
text = tx.read_text()
old = '''pub(super) fn poll_cw_hang(app: &mut App, syst: &mut SYST) {
    if app.cw_hang_ticks == 0 {
        return;
    }
    app.cw_hang_ticks -= 1;
    if app.cw_hang_ticks == 0 && !app.cw_key_down {
'''.replace("+", "")
new = '''pub(super) fn poll_cw_hang(app: &mut App, syst: &mut SYST, ticks_10ms: u16) {
    if app.cw_hang_ticks == 0 || ticks_10ms == 0 {
        return;
    }
    app.cw_hang_ticks = app.cw_hang_ticks.saturating_sub(ticks_10ms);
    if app.cw_hang_ticks == 0 && !app.cw_key_down {
'''.replace("+", "")
if old in text:
    tx.write_text(text.replace(old, new, 1))
elif new not in text:
    raise SystemExit("app/tx.rs: cannot locate CW hang countdown")

main = root / "main.rs"
text = main.read_text()
old = "        app.poll_cw_hang(&mut cp.SYST);\n"
new = "        app.poll_cw_hang(&mut cp.SYST, due.ticks_10ms);\n"
if old in text:
    main.write_text(text.replace(old, new, 1))
elif new not in text:
    raise SystemExit("main.rs: cannot locate CW hang poll")

print("Applied scheduler-based CW break-in timing")
