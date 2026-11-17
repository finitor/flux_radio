#!/usr/bin/env python3
"""Add persistent, independent hold-action chirps and a guarded module host API."""
from pathlib import Path
root = Path(__file__).parent / 'build/aura-fd6818b-port/src'
def patch(path, old, new):
    p=root/path;s=p.read_text()
    if new in s:return
    if old not in s:raise RuntimeError(f'{path}: missing anchor {old[:75]!r}')
    p.write_text(s.replace(old,new,1))
patch('flash_map.rs','    pub beeps_switch: bool,','    pub beeps_switch: bool,\n    /// Independent confirmation for completed hold actions.\n    pub action_beep: bool,')
patch('flash_map.rs','        beeps_switch: true,','        beeps_switch: true,\n        action_beep: true,')
patch('flash_map.rs','            beeps_switch: buf[9] != 0,','            beeps_switch: buf[9] != 0,\n            // Byte 161 was reserved; 0 means legacy/default ON, 1 OFF, 2 ON.\n            action_beep: buf[161] != 1,')
patch('flash_map.rs','        buf[9] = self.beeps_switch as u8;','        buf[9] = self.beeps_switch as u8;\n        buf[161] = if self.action_beep { 2 } else { 1 };')
patch('app/settings.rs','    Beep,','    Beep,\n    ActionBeep,')
patch('app/settings.rs','                SettingItem::Beep,\n                SettingItem::Vox,','                SettingItem::Beep,\n                SettingItem::ActionBeep,\n                SettingItem::Vox,')
patch('app/settings.rs','pub const SETTINGS_ORDER: [SettingItem; 56]','pub const SETTINGS_ORDER: [SettingItem; 57]')
patch('app/settings.rs','            SettingItem::Beep => "BEEP",','            SettingItem::Beep => "BEEP",\n            SettingItem::ActionBeep => "ACTBEEP",')
patch('app/settings_ops.rs','        SettingItem::Beep => app.settings.beeps_switch as i32,','        SettingItem::Beep => app.settings.beeps_switch as i32,\n        SettingItem::ActionBeep => app.settings.action_beep as i32,')
patch('app/settings_ops.rs','        | SettingItem::Beep\n        | SettingItem::Wn','        | SettingItem::Beep\n        | SettingItem::ActionBeep\n        | SettingItem::Wn')
patch('app/settings_ops.rs','        SettingItem::Beep => {\n            app.settings.beeps_switch = v != 0;','        SettingItem::ActionBeep => app.settings.action_beep = v != 0,\n        SettingItem::Beep => {\n            app.settings.beeps_switch = v != 0;')
patch('app/settings_ops.rs','        | SettingItem::Beep\n        | SettingItem::Tail','        | SettingItem::Beep\n        | SettingItem::ActionBeep\n        | SettingItem::Tail')
patch('device/radio.rs','const BEEP_TONES: [(u16, u32); 1] = [(100, 60)];','const BEEP_TONES: [(u16, u32); 1] = [(100, 60)];\nconst ACTION_TONES: [(u16, u32); 1] = [(130, 45)];\nconst NEGATIVE_TONES: [(u16, u32); 2] = [(85, 35), (65, 55)];')
if 'pub fn play_action_beep(' not in (root/'device/radio.rs').read_text():
    patch('device/radio.rs','    fn play_roger_tone(&mut self, syst: &mut SYST) {','    /// Local-only feedback, independent of the ordinary keypress beep setting.\n    pub fn play_action_beep(&mut self, syst: &mut SYST, negative: bool) {\n        // Keep feedback audible even while monitoring; the tone path restores RX.\n        self.play_tone_sequence(syst, if negative { &NEGATIVE_TONES } else { &ACTION_TONES }, false, true);\n    }\n\n    fn play_roger_tone(&mut self, syst: &mut SYST) {')
patch('app/pager.rs','        pub tone_stop: unsafe extern "C" fn(),','        pub tone_stop: unsafe extern "C" fn(),') if False else None
patch('app/pager.rs','        pub lcd_explore_frame: unsafe extern "C" fn(*const super::ModExploreFrame),','        pub lcd_explore_frame: unsafe extern "C" fn(*const super::ModExploreFrame),\n        // level 22: local hold feedback (0 success, 1 unavailable).\n        pub action_chirp: unsafe extern "C" fn(u8) -> i32,')
patch('app/pager.rs','    lcd_explore_frame: mod_lcd_explore_frame,','    lcd_explore_frame: mod_lcd_explore_frame,\n    action_chirp: mod_action_chirp,')
patch('app/pager.rs','    level: if cfg!(feature = "fd6818b") { 21 } else { 9 },','    level: if cfg!(feature = "fd6818b") { 22 } else { 9 },')
p=root/'app/pager.rs';s=p.read_text()
if 'unsafe extern "C" fn mod_action_chirp(' not in s:
    anchor='/// Level 16: tune VFO B to a parked SURF signal and return to Aura with B active.\n'
    assert anchor in s
    s=s.replace(anchor,'''/// Level 22: local-only hold feedback, independently controlled by ACTBEEP.
unsafe extern "C" fn mod_action_chirp(kind: u8) -> i32 {
    let (app, syst) = unsafe { mod_ctx() };
    if !app.settings.action_beep { return 0; }
    if kind > 1 { return -1; }
    app.radio.play_action_beep(syst, kind == 1);
    0
}

'''+anchor,1)
    p.write_text(s)
p=root/'app/keys.rs';s=p.read_text()
anchor='    if matches!(ev.kind, KeyEventKind::Single | KeyEventKind::Long) {\n        app.radio.play_beep(syst);\n    }'
replacement='''    if matches!(ev.kind, KeyEventKind::Long) && app.settings.action_beep {
        app.radio.play_action_beep(syst, false);
    } else if matches!(ev.kind, KeyEventKind::Single) {
        app.radio.play_beep(syst);
    }'''
if replacement not in s:
    assert anchor in s
    s=s.replace(anchor,replacement,1);p.write_text(s)
p=root/'app/settings_ops.rs';s=p.read_text();s=s.replace('        | SettingItem::ActionBeep\n        | SettingItem::ActionBeep\n        | SettingItem::ActionBeep\n','        | SettingItem::ActionBeep\n');s=s.replace('        | SettingItem::Beep\n        | SettingItem::Tail\n','        | SettingItem::Beep\n        | SettingItem::ActionBeep\n        | SettingItem::Tail\n');p.write_text(s)
print('Action beep patches applied')
