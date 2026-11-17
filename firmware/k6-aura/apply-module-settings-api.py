#!/usr/bin/env python3
"""Append a bounded read-only snapshot of Aura's serialized radio settings (API level 15)."""
from pathlib import Path

pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()

field = '''        // level 15: serialized read-only snapshot of all 212 radio settings bytes.
        pub settings_read: unsafe extern "C" fn(*mut u8, u16) -> i32,
'''
struct_anchor = '''        pub serial_write: unsafe extern "C" fn(*const u8, u16) -> i32,
    }
'''.replace("+", "")
if field.strip() not in text:
    if text.count(struct_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate end of K6Api struct")
    text = text.replace(struct_anchor, struct_anchor.replace("    }", field + "    }"), 1)

api_anchor = '''    serial_write: mod_serial_write,
};
'''
if "    settings_read: mod_settings_read," not in text:
    if text.count(api_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate end of MOD_API initializer")
    text = text.replace(api_anchor, api_anchor.replace("};", "    settings_read: mod_settings_read,\n};"), 1)

text = text.replace(
    '    level: if cfg!(feature = "fd6818b") { 14 } else { 9 },',
    '    level: if cfg!(feature = "fd6818b") { 15 } else { 9 },',
    1,
)

anchor = '''/// Level 7: the green RX LED, for a module's own receive activity (and the coded 4FSK session's
'''
func = '''/// Level 15: copy the complete, serialized radio settings snapshot into the module.
unsafe extern "C" fn mod_settings_read(out: *mut u8, cap: u16) -> i32 {
    if out.is_null() || cap < crate::flash_map::SETTINGS_BYTES as u16 {
        return -1;
    }
    let (app, _) = unsafe { mod_ctx() };
    let bytes = app.settings.to_bytes();
    unsafe { core::ptr::copy_nonoverlapping(bytes.as_ptr(), out, bytes.len()); }
    bytes.len() as i32
}

'''
if "unsafe extern \"C\" fn mod_settings_read(" not in text:
    if text.count(anchor) != 1:
        raise SystemExit("pager.rs: cannot locate module API helper insertion point")
    text = text.replace(anchor, func + anchor, 1)

pager.write_text(text)
print("Applied read-only radio settings API (level 15)")
