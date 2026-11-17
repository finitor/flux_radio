#!/usr/bin/env python3
"""Show the configured APRS callsign in Aura's Blowfang-host status bar."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src"
standby = root / "ui/standby.rs"
text = standby.read_text()

old = '''        if app.dual_standby_enabled() {
            Text::new("DWR", Point::new(16, FONT_5X8.baseline as i32), small)
                .draw(lcd)
                .ok();
        }
'''
new = '''        let call = &app.settings().aprs_callsign;
        let call_len = call.iter().position(|&b| b == 0).unwrap_or(6).min(6);
        let call = core::str::from_utf8(&call[..call_len]).unwrap_or("");
        if !call.is_empty() {
            Text::new(call, Point::new(16, FONT_5X8.baseline as i32), small)
                .draw(lcd)
                .ok();
        }
        if app.dual_standby_enabled() {
            let x = if call.is_empty() { 16 } else { 16 + call.len() as i32 * 6 + 5 };
            Text::new("DW", Point::new(x, FONT_5X8.baseline as i32), small)
                .draw(lcd)
                .ok();
        }
'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit("standby.rs: cannot find unique DWR status indicator")
    text = text.replace(old, new, 1)

standby.write_text(text)
print("Applied callsign and dual-watch status labels")
