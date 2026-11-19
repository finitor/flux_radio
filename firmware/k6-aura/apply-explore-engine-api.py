#!/usr/bin/env python3
"""Expose the compact shared xscan engine to sideloaded EXPLORE modules (API 20)."""
from pathlib import Path

pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()

extern_anchor = "        pub fn km_tone_decode(r68: u16, r69: u16, r6a: u16) -> u16;\n"
externs = extern_anchor + '''        // Compact EXPLORE scanner linked in host flash; state remains module-owned.
        pub fn kmx_xs_defaults(scan: *mut core::ffi::c_void);
        pub fn kmx_xs_init(scan: *mut core::ffi::c_void, api: *const K6Api,
                           candidates: *mut core::ffi::c_void, mem: *mut u8, bytes: u32) -> i32;
        pub fn kmx_xs_step(scan: *mut core::ffi::c_void) -> i32;
        pub fn kmx_xs_close(scan: *mut core::ffi::c_void);
        pub fn kmx_xs_resume(scan: *mut core::ffi::c_void);
        pub fn ex_init(state: *mut core::ffi::c_void, entries: *mut core::ffi::c_void, cap: u32);
        pub fn ex_view(state: *mut core::ffi::c_void, index: u32) -> *mut core::ffi::c_void;
        pub fn ex_view_n(state: *const core::ffi::c_void) -> u32;
        pub fn ex_tone(state: *mut core::ffi::c_void, hz: u32, tone: u16);
        pub fn ex_cw(state: *mut core::ffi::c_void, hz: u32, call: *const u8);
'''
if "pub fn kmx_xs_defaults" not in text:
    if text.count(extern_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate managed tone API declaration")
    text = text.replace(extern_anchor, externs, 1)

field_anchor = "        pub lcd_explore_header: unsafe extern \"C\" fn(*const u8, u32, i32),\n"
fields = field_anchor + '''        // level 20: shared compact scanner engine; its working state is still caller supplied.
        pub explore_xs_defaults: unsafe extern "C" fn(*mut core::ffi::c_void),
        pub explore_xs_init: unsafe extern "C" fn(*mut core::ffi::c_void, *const K6Api,
            *mut core::ffi::c_void, *mut u8, u32) -> i32,
        pub explore_xs_step: unsafe extern "C" fn(*mut core::ffi::c_void) -> i32,
        pub explore_xs_close: unsafe extern "C" fn(*mut core::ffi::c_void),
        pub explore_xs_resume: unsafe extern "C" fn(*mut core::ffi::c_void),
        pub explore_ex_init: unsafe extern "C" fn(*mut core::ffi::c_void,
            *mut core::ffi::c_void, u32),
        pub explore_ex_view: unsafe extern "C" fn(*mut core::ffi::c_void, u32)
            -> *mut core::ffi::c_void,
        pub explore_ex_view_n: unsafe extern "C" fn(*const core::ffi::c_void) -> u32,
        pub explore_ex_tone: unsafe extern "C" fn(*mut core::ffi::c_void, u32, u16),
        pub explore_ex_cw: unsafe extern "C" fn(*mut core::ffi::c_void, u32, *const u8),
'''
if "pub explore_xs_defaults:" not in text:
    if text.count(field_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate level 19 EXPLORE header field")
    text = text.replace(field_anchor, fields, 1)

level_old = '    level: if cfg!(feature = "fd6818b") { 19 } else { 9 },'
level_new = '    level: if cfg!(feature = "fd6818b") { 20 } else { 9 },'
if level_old in text:
    text = text.replace(level_old, level_new, 1)
elif not any(f'    level: if cfg!(feature = "fd6818b") {{ {level} }} else {{ 9 }},' in text
             for level in (20, 21, 22, 23)):
    raise SystemExit("pager.rs: cannot locate FD6818B API level")

init_anchor = "    lcd_explore_header: mod_lcd_explore_header,\n"
init = init_anchor + '''    explore_xs_defaults: ffi::kmx_xs_defaults,
    explore_xs_init: ffi::kmx_xs_init,
    explore_xs_step: ffi::kmx_xs_step,
    explore_xs_close: ffi::kmx_xs_close,
    explore_xs_resume: ffi::kmx_xs_resume,
    explore_ex_init: ffi::ex_init,
    explore_ex_view: ffi::ex_view,
    explore_ex_view_n: ffi::ex_view_n,
    explore_ex_tone: ffi::ex_tone,
    explore_ex_cw: ffi::ex_cw,
'''
if "explore_xs_defaults: ffi::kmx_xs_defaults" not in text:
    if text.count(init_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate EXPLORE header API initializer")
    text = text.replace(init_anchor, init, 1)

pager.write_text(text)
print("Applied shared EXPLORE scanner API (level 20)")
