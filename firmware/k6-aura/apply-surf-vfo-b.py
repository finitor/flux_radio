#!/usr/bin/env python3
"""Expose SURF tuning and add long A/B and V/M radio operations."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src"
pager = root / "app/pager.rs"
text = pager.read_text()

api_field = '        pub vfo_b_tune: unsafe extern "C" fn(u32, u8) -> i32,'
while text.count(api_field) > 1:
    duplicate = '        // level 16: tune and activate Aura VFO B from the currently parked SURF signal.\n' + api_field + '\n'
    text = text.replace(duplicate, '', 1)
if api_field not in text:
    text = text.replace(
        '        pub settings_read: unsafe extern "C" fn(*mut u8, u16) -> i32,\n',
        '        pub settings_read: unsafe extern "C" fn(*mut u8, u16) -> i32,\n'
        "        // level 16: tune and activate Aura VFO B from the currently parked SURF signal.\n"
        + api_field + '\n',
        1,
    )
text = text.replace(
    '    level: if cfg!(feature = "fd6818b") { 15 } else { 9 },',
    '    level: if cfg!(feature = "fd6818b") { 16 } else { 9 },',
    1,
)
if "vfo_b_tune: mod_vfo_b_tune" not in text:
    text = text.replace(
        "    settings_read: mod_settings_read,\n};",
        "    settings_read: mod_settings_read,\n    vfo_b_tune: mod_vfo_b_tune,\n};",
        1,
    )
anchor = "/// Level 15: copy the complete, serialized radio settings snapshot into the module.\n"
func = '''/// Level 16: tune VFO B to a parked SURF signal and return to Aura with B active.
unsafe extern "C" fn mod_vfo_b_tune(hz: u32, mode: u8) -> i32 {
    let modulation = match mode {
        0 => Modulation::Fm,
        1 => Modulation::Am,
        2 => Modulation::Usb,
        _ => return -1,
    };
    if !(100_000_000..=520_000_000).contains(&hz) {
        return -1;
    }
    let (app, _) = unsafe { mod_ctx() };
    let side = &mut app.sides[1];
    side.restore_vfo_from_backup();
    side.vfo_chan = ChVfoMode::Vfo;
    side.channel_num = 0;
    side.rx_freq_hz = hz;
    side.freq_dir = 0;
    side.offset_hz = 0;
    side.reversed = false;
    side.ani_target = None;
    side.cfg.modulation = modulation;
    side.refresh_cfg_freqs();
    side.vfo_backup.rx_freq_hz = hz;
    side.vfo_backup.freq_dir = 0;
    side.vfo_backup.offset_hz = 0;
    side.vfo_backup.ani_target = None;
    app.master = 1;
    app.input.clear();
    app.ani_target_override = None;
    app.save_vfo();
    app.save_channel_state();
    unsafe { write_volatile(addr_of_mut!(MOD_EXIT_TO_AURA), true) };
    0
}

'''
if 'unsafe extern "C" fn mod_vfo_b_tune' not in text:
    if text.count(anchor) != 1:
        raise SystemExit("pager.rs: cannot find level-15 API insertion point")
    text = text.replace(anchor, func + anchor, 1)
pager.write_text(text)

keys = root / "app/keys.rs"
text = keys.read_text()
text = text.replace(
    '    DUAL_STANDBY_HOLD_TICKS, RTONE_HZ_DIV_10, VFO_INPUT_DIGITS, VOX_HOLD_AFTER_KEY_TICKS,',
    '    DUAL_STANDBY_HOLD_TICKS, MAX_CHANNEL_NUM, NO_CHANNELS_HOLD_TICKS, RTONE_HZ_DIV_10,\n'
    '    VFO_INPUT_DIGITS, VOX_HOLD_AFTER_KEY_TICKS,',
    1,
)
if 'use crate::flash_map;' not in text:
    text = text.replace('use crate::device::radio::Modulation;\n',
                        'use crate::device::radio::Modulation;\nuse crate::flash_map;\n', 1)
anchor = "fn dispatch_standby(app: &mut App, syst: &mut SYST, ev: KeyEvent) {\n"
helper = '''fn copy_active_vfo_to_other(app: &mut App, syst: &mut SYST) {
    let source = app.master;
    if app.sides[source].vfo_chan != ChVfoMode::Vfo {
        return;
    }
    app.sides[1 - source] = app.sides[source].clone();
    app.save_vfo();
    app.save_channel_state();
    if app.watching == 1 - source {
        app.apply_watching_to_radio(syst);
    }
}

const BF_CHANNEL_MODE_MAGIC: u32 = 0xBF6D_0000;

fn save_vfo_as_channel(app: &mut App, syst: &mut SYST) {
    let source = app.sides[app.master].clone();
    let start = source.channel_num.wrapping_add(1) % (MAX_CHANNEL_NUM + 1);
    let mut slot = None;
    for delta in 0..=MAX_CHANNEL_NUM {
        let candidate = (start + delta) % (MAX_CHANNEL_NUM + 1);
        if app.storage.is_channel_empty(candidate) {
            slot = Some(candidate);
            break;
        }
    }
    let Some(slot) = slot else {
        app.no_channels_ticks = NO_CHANNELS_HOLD_TICKS;
        return;
    };
    let mut channel = flash_map::Channel::from_bytes(&[0; flash_map::addr::CHAN_SIZE as usize]);
    channel.set_rx_freq_deci_hz(source.cfg.freq_hz / 10);
    channel.set_tx_freq_deci_hz(source.cfg.tx_freq_hz / 10);
    channel.rx_dcs_cts_num = super::convert::subaudio_to_code(source.cfg.subaudio_rx);
    channel.tx_dcs_cts_num = super::convert::subaudio_to_code(source.cfg.subaudio_tx);
    channel.tx_power = super::convert::power_to_raw(source.cfg.power);
    channel.set_wide_narrow(!source.cfg.wide_band);
    channel.set_ani_target(source.ani_target);
    channel.name[..10].copy_from_slice(b"VFO MEMORY");
    channel.decoder_code = BF_CHANNEL_MODE_MAGIC
        | super::convert::modulation_to_raw(source.cfg.modulation) as u32;
    app.storage_mut().write_channel_rmw(slot, &channel);
    let side = &mut app.sides[app.master];
    side.vfo_backup = super::side::VfoBackup {
        rx_freq_hz: side.rx_freq_hz,
        freq_dir: side.freq_dir,
        offset_hz: side.offset_hz,
        wide_band: side.cfg.wide_band,
        power: side.cfg.power,
        subaudio_tx: side.cfg.subaudio_tx,
        subaudio_rx: side.cfg.subaudio_rx,
        ani_target: side.ani_target,
    };
    // Preserve the VFO snapshot as the return target for the ordinary short V/M toggle.
    app.save_vfo();
    let channel = app.storage.read_channel(slot);
    app.sides[app.master].load_channel(slot, &channel);
    app.save_channel_state();
    app.sync_watching_to_master(syst);
}

fn recall_channel_to_vfo(app: &mut App, syst: &mut SYST) {
    let i = app.master;
    let side = &mut app.sides[i];
    if side.vfo_chan != ChVfoMode::Channel {
        return;
    }
    let ch = app.storage.read_channel(side.channel_num);
    let rx = side.rx_freq_hz;
    let tx = side.tx_freq_hz;
    let (freq_dir, offset_hz) = if tx > rx {
        (1, tx - rx)
    } else if tx < rx {
        (2, rx - tx)
    } else {
        (0, 0)
    };
    side.vfo_chan = ChVfoMode::Vfo;
    side.name = [0; 12];
    side.freq_dir = freq_dir;
    side.offset_hz = offset_hz;
    side.reversed = false;
    if ch.decoder_code & 0xFFFF_FF00 == BF_CHANNEL_MODE_MAGIC {
        side.cfg.modulation = super::convert::modulation_from_raw(ch.decoder_code as u8);
    }
    side.vfo_backup = super::side::VfoBackup {
        rx_freq_hz: rx,
        freq_dir,
        offset_hz,
        wide_band: side.cfg.wide_band,
        power: side.cfg.power,
        subaudio_tx: side.cfg.subaudio_tx,
        subaudio_rx: side.cfg.subaudio_rx,
        ani_target: side.ani_target,
    };
    side.refresh_cfg_freqs();
    app.input.clear();
    app.ani_target_override = None;
    app.save_vfo();
    app.save_channel_state();
    app.sync_watching_to_master(syst);
}

'''
if "fn copy_active_vfo_to_other(" not in text:
    if text.count(anchor) != 1:
        raise SystemExit("keys.rs: cannot find standby dispatcher")
    text = text.replace(anchor, helper + anchor, 1)
old = '''            KeyId::Pound => scan::enter(app, syst),
            KeyId::Side1 | KeyId::Side2 | KeyId::Band => {
'''.replace("+", "")
new = '''            KeyId::Pound => scan::enter(app, syst),
            KeyId::Ab => copy_active_vfo_to_other(app, syst),
            KeyId::Vm if app.sides[app.master].vfo_chan == ChVfoMode::Vfo => {
                save_vfo_as_channel(app, syst)
            }
            KeyId::Vm => recall_channel_to_vfo(app, syst),
            KeyId::Side1 | KeyId::Side2 | KeyId::Band => {
'''.replace("+", "")
if old in text:
    text = text.replace(old, new, 1)
elif "KeyId::Ab => copy_active_vfo_to_other(app, syst)," not in text:
    raise SystemExit("keys.rs: cannot find long-press key match")
keys.write_text(text)

keypad = root / "device/keypad.rs"
text = keypad.read_text()
if '| KeyId::Ab' not in text[text.find('fn supports_long'):text.find('fn supports_repeat')]:
    text = text.replace('                | KeyId::Vm\n', '                | KeyId::Vm\n                | KeyId::Ab\n', 1)
keypad.write_text(text)

side = root / "app/side.rs"
text = side.read_text()
text = text.replace('use crate::device::radio::{ChannelConfig, Power, SubAudio};',
                    'use crate::device::radio::{ChannelConfig, Modulation, Power, SubAudio};', 1)
needle = '        self.cfg.subaudio_rx = subaudio_from_code(ch.rx_dcs_cts_num);\n'
addon = needle + '''        if ch.decoder_code & 0xFFFF_FF00 == 0xBF6D_0000 {
            self.cfg.modulation = match ch.decoder_code as u8 {
                1 => Modulation::Am,
                2 => Modulation::Usb,
                3 => Modulation::Cw,
                4 => Modulation::Cwf,
                _ => Modulation::Fm,
            };
        }
'''
if '0xBF6D_0000' not in text:
    if text.count(needle) != 1:
        raise SystemExit('side.rs: cannot find channel load insertion point')
    text = text.replace(needle, addon, 1)
side.write_text(text)

app = root / "app/mod.rs"
text = app.read_text()
old = '''                if is_channel && !storage.is_channel_empty(num) {
                    let ch = storage.read_channel(num);
                    s.load_channel(num, &ch);
                }
                s.cfg.modulation = modulation_from_raw(state[6 + half]);'''
new = '''                s.cfg.modulation = modulation_from_raw(state[6 + half]);
                if is_channel && !storage.is_channel_empty(num) {
                    let ch = storage.read_channel(num);
                    s.load_channel(num, &ch);
                }'''
if old in text:
    text = text.replace(old, new, 1)
elif new not in text:
    raise SystemExit('app/mod.rs: cannot preserve saved channel modulation during startup')
app.write_text(text)

# Add REV SWAP as an assignable side/BAND key function and teach REV to add
# the conventional repeater split when invoked from a simplex VFO.
keyfn = root / "app/keyfn.rs"
text = keyfn.read_text()
if "ReverseSwap" not in text:
    text = text.replace("    Reverse,\n    AprsBeacon,", "    Reverse,\n    ReverseSwap,\n    AprsBeacon,", 1)
    text = text.replace('            KeyFunction::Reverse => "REVERSE",\n',
                        '            KeyFunction::Reverse => "REVERSE",\n            KeyFunction::ReverseSwap => "REV SWAP",\n', 1)
    text = text.replace('        11 => KeyFunction::AprsBeacon,\n',
                        '        11 => KeyFunction::AprsBeacon,\n        12 => KeyFunction::ReverseSwap,\n', 1)
    text = text.replace('        KeyFunction::Reverse => app.toggle_reverse(syst),\n',
                        '        KeyFunction::Reverse => app.toggle_reverse(syst),\n'
                        '        KeyFunction::ReverseSwap => super::side_ops::reverse_swap(app, syst),\n', 1)
keyfn.write_text(text)

settings_ops = root / "app/settings_ops.rs"
text = settings_ops.read_text().replace('clamp_step(cur, up, 0, 11)',
                                        'clamp_step(cur, up, 0, 12)', 1)
settings_ops.write_text(text)

side_ops = root / "app/side_ops.rs"
text = side_ops.read_text()
old = '''pub(super) fn toggle_reverse(app: &mut App, syst: &mut SYST) {
    let s = &mut app.sides[app.master];
    s.reversed = !s.reversed;
    s.refresh_cfg_freqs();
    sync_watching_to_master(app, syst);
}
'''.replace("+", "")
new = '''fn standard_repeater_split(freq_hz: u32) -> Option<(u8, u32)> {
    // Common North American FM pairs. dir=1 is TX above RX; dir=2 is below.
    // Inputs and outputs are both recognized so REV SWAP can normalize a
    // discovered input frequency into the corresponding repeater output.
    if (145_200_000..=145_500_000).contains(&freq_hz)
        || (146_610_000..=146_970_000).contains(&freq_hz)
    {
        Some((2, 600_000))
    } else if (144_600_000..=144_900_000).contains(&freq_hz)
        || (146_010_000..=146_370_000).contains(&freq_hz)
    {
        Some((1, 600_000))
    } else if (147_000_000..=147_390_000).contains(&freq_hz) {
        Some((1, 600_000))
    } else if (147_600_000..=147_990_000).contains(&freq_hz) {
        Some((2, 600_000))
    } else if (440_000_000..445_000_000).contains(&freq_hz) {
        Some((1, 5_000_000))
    } else if (447_000_000..=450_000_000).contains(&freq_hz) {
        Some((2, 5_000_000))
    } else {
        None
    }
}

pub(super) fn toggle_reverse(app: &mut App, syst: &mut SYST) {
    let s = &mut app.sides[app.master];
    if s.vfo_chan == ChVfoMode::Vfo && (s.freq_dir == 0 || s.offset_hz == 0) {
        if let Some((dir, offset)) = standard_repeater_split(s.cfg.freq_hz) {
            s.freq_dir = dir;
            s.offset_hz = offset;
            s.reversed = false;
            s.refresh_cfg_freqs();
            commit_side_change(app, syst);
        }
        return;
    }
    s.reversed = !s.reversed;
    s.refresh_cfg_freqs();
    sync_watching_to_master(app, syst);
}

pub(super) fn reverse_swap(app: &mut App, syst: &mut SYST) {
    let s = &mut app.sides[app.master];
    if s.vfo_chan != ChVfoMode::Vfo || s.freq_dir == 0 || s.offset_hz == 0 {
        return;
    }
    let old_rx = s.cfg.freq_hz;
    let old_tx = s.cfg.tx_freq_hz;
    if old_rx == old_tx {
        return;
    }
    // Make the old TX frequency the new RX frequency and transmit back on
    // the old RX frequency; store this as a normal, non-reversed VFO pair.
    s.rx_freq_hz = old_tx;
    s.freq_dir = if old_rx > old_tx { 1 } else { 2 };
    s.offset_hz = old_rx.abs_diff(old_tx);
    s.reversed = false;
    s.refresh_cfg_freqs();
    commit_side_change(app, syst);
}
'''
if old in text:
    text = text.replace(old, new, 1)
elif "fn standard_repeater_split(" not in text:
    raise SystemExit("side_ops.rs: cannot find toggle_reverse for repeater split behavior")
side_ops.write_text(text)
print("Applied SURF-to-VFO-B handoff and long A/B copy")
