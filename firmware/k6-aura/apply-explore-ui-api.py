#!/usr/bin/env python3
"""Expose the host-rendered Explore frame and install its compact original-style renderer."""
from pathlib import Path

HERE = Path(__file__).parent
WORK = HERE / "build/aura-fd6818b-port/src"
pager = WORK / "app/pager.rs"
text = pager.read_text()

api_anchor = '        pub explore_ex_cw: unsafe extern "C" fn(*mut core::ffi::c_void, u32, *const u8),\n'
api_field = api_anchor + '        // level 21: host-rendered compact replica of the original EXPLORE list UI.\n' \
    + '        pub lcd_explore_frame: unsafe extern "C" fn(*const super::ModExploreFrame),\n'
if "pub lcd_explore_frame:" not in text:
    if text.count(api_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate level 20 Explore API end")
    text = text.replace(api_anchor, api_field, 1)

level_old = '    level: if cfg!(feature = "fd6818b") { 20 } else { 9 },'
level_new = '    level: if cfg!(feature = "fd6818b") { 21 } else { 9 },'
if level_old in text:
    text = text.replace(level_old, level_new, 1)
elif level_new not in text and not any(
    f'    level: if cfg!(feature = "fd6818b") {{ {level} }} else {{ 9 }},' in text
    for level in (22,)
):
    raise SystemExit("pager.rs: cannot locate FD6818B API level 20")

init_anchor = '    explore_ex_cw: ffi::ex_cw,\n'
if "lcd_explore_frame: mod_lcd_explore_frame," not in text:
    if text.count(init_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate Explore API initializer")
    text = text.replace(init_anchor, init_anchor + '    lcd_explore_frame: mod_lcd_explore_frame,\n', 1)

struct_anchor = 'pub struct ModScreen {\n'
frame_struct = '''#[repr(C)]
pub struct ModExploreRow {
    pub hz: u32,
    pub off_hz: i32,
    pub overs: u16,
    pub tone: u16,
    pub hi: i16,
    pub score: i8,
    pub flags: u8,
    pub grade: u8,
    pub call: [u8; 10],
}
#[repr(C)]
pub struct ModExploreFrame {
    pub view: u8,
    pub band: u8,
    pub gaze: u8,
    pub selected: u8,
    pub count: u8,
    pub found: u32,
    pub sweeps: u32,
    pub scan_hz: u32,
    pub level: i16,
    pub pad: [u8; 2],
    pub rows: [ModExploreRow; 7],
}

'''
if "pub struct ModExploreFrame" not in text:
    if text.count(struct_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate ModScreen")
    text = text.replace(struct_anchor, frame_struct + struct_anchor, 1)

field_anchor = '    pub gl_n: i32,\n'
if '    pub explore: *const ModExploreFrame,\n' not in text:
    if text.count(field_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module glyph state")
    text = text.replace(field_anchor, field_anchor + '    pub explore: *const ModExploreFrame,\n', 1)
init_anchor = '    gl_n: 0,\n'
if '    explore: core::ptr::null(),\n' not in text:
    if text.count(init_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module screen initializer")
    text = text.replace(init_anchor, init_anchor + '    explore: core::ptr::null(),\n', 1)
clear_anchor = '    s.gl_n = 0;\n'
if '    s.explore = core::ptr::null();\n' not in text:
    if text.count(clear_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module screen clear")
    text = text.replace(clear_anchor, clear_anchor + '    s.explore = core::ptr::null();\n', 1)

callback_anchor = 'unsafe extern "C" fn mod_lcd_glyphs(cols: *const u16, n: i32) {'
callback = '''unsafe extern "C" fn mod_lcd_explore_frame(frame: *const ModExploreFrame) {
    let screen = unsafe { &mut *addr_of_mut!(MOD_SCREEN) };
    screen.explore = frame;
    screen.wf = core::ptr::null();
    screen.wf_rows = 0;
}

'''
if 'unsafe extern "C" fn mod_lcd_explore_frame(' not in text:
    if text.count(callback_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module glyph callback")
    text = text.replace(callback_anchor, callback + callback_anchor, 1)
pager.write_text(text)

glyph = WORK / "ui/glyph.rs"
glyph_text = glyph.read_text()
glyph_impl = (HERE / "explore-small-font.rs.inc").read_text()
if "pub fn text_small_page" not in glyph_text:
    glyph.write_text(glyph_text.rstrip() + "\n\n" + glyph_impl + "\n")

ui = WORK / "ui/pager.rs"
ui_text = ui.read_text()
branch = '''    if !s.explore.is_null() {
        draw_explore_page(buf, page, unsafe { &*s.explore });
        return;
    }
'''
anchor = '    use app::pager::{MOD_COLS, MOD_GLYPH_COLS, MOD_LINES, WF_TOP};\n'
if "draw_explore_page(buf, page" not in ui_text:
    if ui_text.count(anchor) != 1:
        raise SystemExit("ui/pager.rs: cannot locate module page renderer")
    ui_text = ui_text.replace(anchor, anchor + branch, 1)
    ui.write_text(ui_text.rstrip() + "\n\n" + (HERE / "explore-render-page.rs.inc").read_text() + "\n")

print("Applied host-rendered EXPLORE UI API (level 21)")
