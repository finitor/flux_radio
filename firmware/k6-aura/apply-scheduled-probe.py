#!/usr/bin/env python3
"""Opt-in scheduler smoke test: periodic diagnostic, never RF TX."""
from pathlib import Path
src=Path(__file__).parent/'build/aura-fd6818b-port/src'
cfg='#[cfg(all(k6_scheduled_probe, k6_vfo_probe, not(k6_no_fsk_rx), feature = "blowfang-host"))]'
def edit(path, old, new):
    p=src/path
    s=p.read_text()
    if new in s:return
    assert s.count(old)==1,(path,old)
    p.write_text(s.replace(old,new,1))
edit('main.rs','        resident_probe.tick(&app);','''        resident_probe.tick(&app);
        '''+cfg+'''
        scheduled_probe.poll(&mut resident_probe, &app, due.ticks_10ms, audio_open);''')
edit('main.rs','    let mut resident_probe = vfo_mode_runtime::Runtime::new();','''    let mut resident_probe = vfo_mode_runtime::Runtime::new();
    '''+cfg+'''
    let mut scheduled_probe = vfo_mode_runtime::ScheduledProbe::new();''')
if 'pub fn scheduled_rf_idle(' not in (src/'app/mod.rs').read_text():
    edit('app/mod.rs','    pub fn side_modulation(&self, index: usize) -> Modulation {','    '+cfg+'''
    pub fn scheduled_rf_idle(&self) -> bool {
        !self.radio.ptt_asserted() && !self.rssi_open() && !self.is_transmitting()
            && !self.cw_key_down() && !self.power_save_is_asleep()
            && self.mode() == Mode::Standby
    }
    pub fn side_modulation(&self, index: usize) -> Modulation {''')
p=src/'vfo_mode_runtime.rs'
s=p.read_text()
addition=Path(__file__).with_name('scheduled-probe.rs').read_text()
if addition not in s:p.write_text(s+'\n'+addition)
p=src.parent/'build.rs'
s=p.read_text()
check='    println!("cargo:rustc-check-cfg=cfg(k6_scheduled_probe)");'
if check not in s:p.write_text(s.replace('fn main() {','fn main() {\n'+check,1))
