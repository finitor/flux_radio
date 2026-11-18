#!/usr/bin/env python3
"""Show the standard FM repeater split that REV will apply from a simplex VFO."""
from pathlib import Path

path = Path(__file__).parent / "build/aura-fd6818b-port/src/ui/standby.rs"
text = path.read_text()
anchor = '''    let bandwidth = if app.side_wide_band(i) { "WIDE" } else { "NAR" };
    let reversed = if app.side_reversed(i) { "R" } else { "" };
'''
replacement = '''    let bandwidth = if app.side_wide_band(i) { "WIDE" } else { "NAR" };
    let reversed = if app.side_reversed(i) { "R" } else { "" };
    let rpt_hint = if app.side_modulation(i) == Modulation::Fm
        && !app.side_is_channel_mode(i)
        && app.side_offset_hz(i) == 0
    {
        match standard_repeater_split(app.side_freq_hz(i)) {
            Some((1, offset)) => if offset == 600_000 { "REV +600" } else { "REV +5M" },
            Some((2, offset)) => if offset == 600_000 { "REV -600" } else { "REV -5M" },
            _ => "",
        }
    } else {
        ""
    };
'''
if replacement not in text:
    if text.count(anchor) != 1:
        raise SystemExit(f"standby.rs: expected one mode-line anchor, got {text.count(anchor)}")
    text = text.replace(anchor, replacement, 1)

anchor = '''        &[modulation, power, tone, dir, bandwidth, reversed, bk_in],
'''
replacement = '''        &[modulation, power, tone, dir, bandwidth, reversed, bk_in, rpt_hint],
'''
if replacement not in text and "[modulation, power, tone, dir, bandwidth, reversed, bk_in, rpt_hint]" not in text:
    if text.count(anchor) != 1:
        raise SystemExit(f"standby.rs: expected one mode-line fields anchor, got {text.count(anchor)}")
    text = text.replace(anchor, replacement, 1)

helper_anchor = '''fn draw_mode_line<D>(lcd: &mut D, app: &app::App, i: usize, baseline_y: i32)
'''
helper = '''fn standard_repeater_split(freq_hz: u32) -> Option<(u8, u32)> {
    if (145_200_000..=145_500_000).contains(&freq_hz)
        || (146_610_000..=146_970_000).contains(&freq_hz)
    {
        Some((2, 600_000))
    } else if (144_600_000..=144_900_000).contains(&freq_hz)
        || (146_010_000..=146_370_000).contains(&freq_hz)
    {
        Some((1, 600_000))
    } else if (147_000_000..=147_390_000).contains(&freq_hz)
        || (440_000_000..445_000_000).contains(&freq_hz)
    {
        Some((1, if freq_hz >= 420_000_000 { 5_000_000 } else { 600_000 }))
    } else if (147_600_000..=147_990_000).contains(&freq_hz)
        || (447_000_000..=450_000_000).contains(&freq_hz)
    {
        Some((2, if freq_hz >= 420_000_000 { 5_000_000 } else { 600_000 }))
    } else {
        None
    }
}

'''
if helper not in text:
    if text.count(helper_anchor) != 1:
        raise SystemExit("standby.rs: cannot locate draw_mode_line")
    text = text.replace(helper_anchor, helper + helper_anchor, 1)

path.write_text(text)
print("Applied VFO repeater split hint")
