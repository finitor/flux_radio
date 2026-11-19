#!/usr/bin/env python3
"""Opt-in first selectable resident mode; keep legacy probe images unchanged."""
from pathlib import Path
src=Path(__file__).parent/'build/aura-fd6818b-port/src'
cfg='#[cfg(all(k6_vfo_probe, k6_vfo_spi_probe, k6_vfo_selector, not(k6_no_fsk_rx), feature = "blowfang-host"))]'
def edit(path, old, new):
    p=src/path
    s=p.read_text()
    if new in s: return
    if s.count(old)!=1: raise SystemExit(f'{path}: expected one anchor: {old}')
    p.write_text(s.replace(old,new,1))
edit('app/mod.rs','    sides: [side::Side; 2],', '    sides: [side::Side; 2],\n    '+cfg+'\n    resident_selected: [bool; 2],')
edit('app/mod.rs','            master: 0,','            '+cfg+'\n            resident_selected: [false; 2],\n            master: 0,')
if 'pub fn resident_selected(' not in (src/'app/mod.rs').read_text():
    edit('app/mod.rs','    pub fn side_modulation(&self, index: usize) -> Modulation {', '    '+cfg+'''
    pub fn resident_selected(&self, index: usize) -> bool { self.resident_selected[index] }
    pub fn side_modulation(&self, index: usize) -> Modulation {''')
edit('app/side_ops.rs','    let s = &mut app.sides[app.master];\n    s.cfg.modulation = match s.cfg.modulation {','    '+cfg+'''
    {
        let side = app.master;
        if app.resident_selected[side] {
            app.resident_selected[side] = false;
            app.sides[side].cfg.modulation = Modulation::Fm;
            sync_watching_to_master(app, syst);
            return;
        }
        if !app.side_is_channel_mode(side) && cfg!(k6_no_sotto)
            && app.sides[side].cfg.modulation == Modulation::Cwf
            && app.resident_probe_slot() >= 0 {
            app.resident_selected[side] = true;
            app.sides[side].cfg.modulation = Modulation::Fm;
            sync_watching_to_master(app, syst);
            return;
        }
    }
    let s = &mut app.sides[app.master];
    s.cfg.modulation = match s.cfg.modulation {''')
# Inhibit PTT and VOX centrally; CW has a separate entry point.
edit('app/tx.rs','pub(super) fn set_ptt(app: &mut App, syst: &mut SYST, pressed: bool) {','pub(super) fn set_ptt(app: &mut App, syst: &mut SYST, pressed: bool) {\n    '+cfg+'\n    if pressed && app.resident_selected(app.master_index()) { return; }')
edit('app/tx.rs','fn set_cw_key(app: &mut App, syst: &mut SYST, down: bool) {','fn set_cw_key(app: &mut App, syst: &mut SYST, down: bool) {\n    '+cfg+'\n    if down && app.resident_selected(app.master_index()) { return; }')
edit('ui/standby.rs','    let is_cw_master = i == app.master_index()','    '+cfg+'\n    let modulation = if app.resident_selected(i) { "PROBE" } else { modulation };\n    let is_cw_master = i == app.master_index()')
edit('vfo_mode_runtime.rs','        let side = app.watching_index();','        let side = app.watching_index();\n        '+cfg+'\n        if !app.resident_selected(side) || app.side_is_channel_mode(side) || app.side_modulation(side) != crate::device::radio::Modulation::Fm { self.stop(); return; }')
p=src.parent/'build.rs'
s=p.read_text()
check='    println!("cargo:rustc-check-cfg=cfg(k6_vfo_selector)");'
if check not in s:p.write_text(s.replace('fn main() {','fn main() {\n'+check,1))
