#!/usr/bin/env python3
"""Move EXPLORE's animated header glyphs and formatting into the Aura module host (API 19)."""
from pathlib import Path

pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()

field = '        pub tone_stop: unsafe extern "C" fn(),\n'
new_field = field + '        // level 19: firmware-rendered EXPLORE title, count, and animated eyes.\n' \
    + '        pub lcd_explore_header: unsafe extern "C" fn(*const u8, u32, i32),\n'
if "pub lcd_explore_header:" not in text:
    if text.count(field) != 1:
        raise SystemExit("pager.rs: cannot locate level 18 K6Api field")
    text = text.replace(field, new_field, 1)

text = text.replace(
    '    level: if cfg!(feature = "fd6818b") { 18 } else { 9 },',
    '    level: if cfg!(feature = "fd6818b") { 19 } else { 9 },', 1)
if not any(f'    level: if cfg!(feature = "fd6818b") {{ {level} }} else {{ 9 }},' in text
           for level in (19, 20, 21, 22)):
    raise SystemExit("pager.rs: cannot locate FD6818B API level 18/19")

init = '    tone_stop: mod_tone_stop,\n'
if "lcd_explore_header: mod_lcd_explore_header," not in text:
    if text.count(init) != 1:
        raise SystemExit("pager.rs: cannot locate level 18 K6Api initializer")
    text = text.replace(init, init + '    lcd_explore_header: mod_lcd_explore_header,\n', 1)

if "unsafe extern \"C\" fn mod_lcd_explore_header(" not in text:
    anchor = 'unsafe extern "C" fn mod_lcd_glyphs(cols: *const u16, n: i32) {'
    function = r'''// The eyes are firmware-owned so their artwork and title formatting do not consume a
// module's scarce code/scratch arena. Glyphs 0 and 1 are the two eye-gaze frames.
const EXPLORE_EYES: [u16; 12] = [
    0x030, 0x048, 0x0cc, 0x0fc, 0x078, 0x030,
    0x030, 0x078, 0x0fc, 0x0cc, 0x048, 0x030,
];

unsafe extern "C" fn mod_lcd_explore_header(band: *const u8, found: u32, gaze: i32) {
    if band.is_null() { return; }
    let screen = unsafe { &mut *addr_of_mut!(MOD_SCREEN) };
    screen.gl = EXPLORE_EYES.as_ptr();
    screen.gl_n = 2;
    let row = &mut screen.text[0];
    row.fill(0);
    let eye = 0x80 + (gaze & 1) as u8;
    row[0] = eye;
    row[1] = b' ';
    row[2] = eye;
    row[3] = b' ';
    let mut n = 0usize;
    while n < 5 {
        let b = unsafe { *band.add(n) };
        if b == 0 { break; }
        row[4 + n] = if b >= 0x20 && b < 0x7f { b } else { b'?'};
        n += 1;
    }
    let mut value = found.min(999);
    let mut digits = [0u8; 3];
    let mut count = 0usize;
    loop {
        digits[count] = b'0' + (value % 10) as u8;
        count += 1;
        value /= 10;
        if value == 0 { break; }
    }
    let mut at = 4 + n;
    row[at] = b' ';
    at += 1;
    while count > 0 {
        count -= 1;
        if at >= row.len() { return; }
        row[at] = digits[count];
        at += 1;
    }
    for b in b" found" {
        if at >= row.len() { break; }
        row[at] = *b;
        at += 1;
    }
}

'''
    if text.count(anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module glyph API helper")
    text = text.replace(anchor, function + anchor, 1)

pager.write_text(text)
print("Applied firmware-rendered EXPLORE header API (level 19)")
