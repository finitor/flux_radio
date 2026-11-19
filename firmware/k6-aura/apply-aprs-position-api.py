#!/usr/bin/env python3
"""Level 23: only APRS lat/lon, bounded and persisted through Aura settings."""
from pathlib import Path
p=Path(__file__).parent/"build/aura-fd6818b-port/src/app/pager.rs"
s=p.read_text()
def patch(old,new):
    global s
    if new in s:return
    if s.count(old)!=1:raise SystemExit("position API anchor: "+old)
    s=s.replace(old,new,1)
patch('        pub action_chirp: unsafe extern "C" fn(u8) -> i32,',
      '        pub action_chirp: unsafe extern "C" fn(u8) -> i32,\n        pub aprs_position_set: unsafe extern "C" fn(i32, i32) -> i32,')
patch('    action_chirp: mod_action_chirp,','    action_chirp: mod_action_chirp,\n    aprs_position_set: mod_aprs_position_set,')
patch('    level: if cfg!(feature = "fd6818b") { 22 } else { 9 },','    level: if cfg!(feature = "fd6818b") { 23 } else { 9 },')
patch('    cal_written: bool,','    cal_written: bool,\n    position_written: bool,')
if 'position_written: false,' not in s:
    s=s.replace('cal_written: false,','cal_written: false,\n            position_written: false,')
    s=s.replace('cal_written: true, // no calibration writes','cal_written: true, // no calibration writes\n            position_written: true,')
func='''/// Level 23: narrow position-only settings setter, once per module run.
unsafe extern "C" fn mod_aprs_position_set(lat: i32, lon: i32) -> i32 {
    if !(-9_000_000..=9_000_000).contains(&lat) ||
       !(-18_000_000..=18_000_000).contains(&lon) { return -1; }
    let c = unsafe { &mut *addr_of_mut!(MOD_CTX) };
    if c.app.is_null() || c.tx || c.position_written { return -1; }
    let app = unsafe { &mut *c.app };
    if app.settings.aprs_lat == lat && app.settings.aprs_lon == lon { return 0; }
    c.position_written = true;
    app.settings.aprs_lat = lat;
    app.settings.aprs_lon = lon;
    app.save_settings();
    1
}

'''
if 'fn mod_aprs_position_set(' not in s:
    anchor='/// Level 22: local-only hold feedback'
    if s.count(anchor)!=1:raise SystemExit("missing API helper anchor")
    s=s.replace(anchor,func+anchor,1)
p.write_text(s)
print("APRS position API level 23 applied")
