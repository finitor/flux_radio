#!/usr/bin/env python3
"""Expose shared CW decoding and managed FD6818 CTCSS/DCS observation services."""
from pathlib import Path
import re

pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()

def once(old: str, new: str, label: str) -> None:
    global text
    if new in text:
        return
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"pager.rs: expected one {label} anchor, found {count}")
    text = text.replace(old, new, 1)

once(
    '        pub fn km_crc_diag() -> u32;',
    '        pub fn km_crc_diag() -> u32;\n'
    '        pub fn km_cw_init(state: *mut core::ffi::c_void);\n'
    '        pub fn km_cw_feed(state: *mut core::ffi::c_void, ms: u32, keyed: i32) -> i32;\n'
    '        pub fn km_cw_flush(state: *mut core::ffi::c_void, ms: u32) -> i32;\n'
    '        pub fn km_cw_call(text: *const u8, call: *mut u8, flags: *mut u8) -> i32;\n'
    '        pub fn km_tone_decode(r68: u16, r69: u16, r6a: u16) -> u16;',
    "C decoder FFI",
)

if "pub cw_init:" not in text:
    once(
        '        pub vfo_b_tune: unsafe extern "C" fn(u32, u8) -> i32,\n',
        '        pub vfo_b_tune: unsafe extern "C" fn(u32, u8) -> i32,\n'
        '        // level 17: shared caller-owned CW decode state and standard sub-audio sample decode.\n'
        '        pub cw_init: unsafe extern "C" fn(*mut core::ffi::c_void),\n'
        '        pub cw_feed: unsafe extern "C" fn(*mut core::ffi::c_void, u32, i32) -> i32,\n'
        '        pub cw_flush: unsafe extern "C" fn(*mut core::ffi::c_void, u32) -> i32,\n'
        '        pub cw_call: unsafe extern "C" fn(*const u8, *mut u8, *mut u8) -> i32,\n'
        '        pub tone_decode: unsafe extern "C" fn(u16, u16, u16) -> u16,\n',
        "K6Api level 17 fields",
    )
if "pub tone_start:" not in text:
    once(
        '        pub tone_decode: unsafe extern "C" fn(u16, u16, u16) -> u16,\n',
        '        pub tone_decode: unsafe extern "C" fn(u16, u16, u16) -> u16,\n'
        '        // level 18: managed FD6818 sub-audio scan, including cleanup on module return.\n'
        '        pub tone_start: unsafe extern "C" fn() -> i32,\n'
        '        pub tone_step: unsafe extern "C" fn() -> i32,\n'
        '        pub tone_stop: unsafe extern "C" fn(),\n',
        "K6Api level 18 fields",
    )
if not any(f'level: if cfg!(feature = "fd6818b") {{ {level} }} else {{ 9 }},' in text
           for level in (18, 19, 20, 21, 22)):
    for old in (16, 17):
        anchor = f'    level: if cfg!(feature = "fd6818b") {{ {old} }} else {{ 9 }},'
        if anchor in text:
            text = text.replace(anchor, '    level: if cfg!(feature = "fd6818b") { 18 } else { 9 },', 1)
            break
    else:
        raise SystemExit("pager.rs: cannot locate module API level 16/17 initializer")

if "    cw_init: ffi::km_cw_init," not in text:
    once(
        '    vfo_b_tune: mod_vfo_b_tune,\n',
        '    vfo_b_tune: mod_vfo_b_tune,\n'
        '    cw_init: ffi::km_cw_init,\n'
        '    cw_feed: ffi::km_cw_feed,\n'
        '    cw_flush: ffi::km_cw_flush,\n'
        '    cw_call: ffi::km_cw_call,\n'
        '    tone_decode: ffi::km_tone_decode,\n',
        "module API level 17 initializer",
    )
if "    tone_start: mod_tone_start," not in text:
    once(
        '    tone_decode: ffi::km_tone_decode,\n',
        '    tone_decode: ffi::km_tone_decode,\n'
        '    tone_start: mod_tone_start,\n'
        '    tone_step: mod_tone_step,\n'
        '    tone_stop: mod_tone_stop,\n',
        "module API level 18 initializer",
    )

ctx_anchor = '''    /// bytes of say lines kept for the over-the-air report (0: none)
    tlm_cap: u16,
}'''
ctx_replacement = '''    /// bytes of say lines kept for the over-the-air report (0: none)
    tlm_cap: u16,
    tone_saved: u16,
    tone_candidate: u16,
    tone_count: u8,
    tone_active: bool,
}'''
once(ctx_anchor, ctx_replacement, "managed tone context fields")
tone_anchor = '''unsafe extern "C" fn mod_fsk_rx_start() -> i32 {'''
tone_start_anchor = '''unsafe extern "C" fn mod_tone_start() -> i32 {'''
fsk_comment = '''/// Level 10's explicit FD6818B receive path. Keep modules off the raw FD6818 register recipe:
/// the B chip has a different FSK programming sequence and exposes fixed 16-byte FIFO frames.
'''
tone_funcs = '''unsafe extern "C" fn mod_tone_start() -> i32 {
    if !cfg!(feature = "fd6818b") { return -1; }
    mod_tx_guard();
    let (app, syst) = unsafe { mod_ctx() };
    let c = unsafe { &mut *addr_of_mut!(MOD_CTX) };
    if c.app.is_null() || c.tx || c.tone_active { return -1; }
    c.tone_saved = app.radio.fd6818.reg_read(syst, 0x51);
    app.radio.fd6818.reg_write(syst, 0x51, 0x0300);
    c.tone_candidate = 0;
    c.tone_count = 0;
    c.tone_active = true;
    0
}

unsafe extern "C" fn mod_tone_step() -> i32 {
    if !cfg!(feature = "fd6818b") { return -1; }
    let (app, syst) = unsafe { mod_ctx() };
    let c = unsafe { &mut *addr_of_mut!(MOD_CTX) };
    if c.app.is_null() || c.tx || !c.tone_active { return -1; }
    let r69 = app.radio.fd6818.reg_read(syst, 0x69);
    let r6a = if r69 & 0x8000 == 0 { app.radio.fd6818.reg_read(syst, 0x6A) } else { 0 };
    let mut decoded = unsafe { ffi::km_tone_decode(0x8000, r69, r6a) };
    if decoded == 0 {
        let r68 = app.radio.fd6818.reg_read(syst, 0x68);
        decoded = unsafe { ffi::km_tone_decode(r68, 0x8000, 0) };
    }
    if decoded == 0 {
        c.tone_candidate = 0;
        c.tone_count = 0;
    } else if decoded == c.tone_candidate {
        c.tone_count = c.tone_count.saturating_add(1);
        if c.tone_count >= 2 { return decoded as i32; }
    } else {
        c.tone_candidate = decoded;
        c.tone_count = 1;
    }
    0
}

unsafe extern "C" fn mod_tone_stop() {
    let c = unsafe { &mut *addr_of_mut!(MOD_CTX) };
    if !c.tone_active || c.app.is_null() || c.syst.is_null() { return; }
    let (app, syst) = unsafe { mod_ctx() };
    app.radio.fd6818.reg_write(syst, 0x51, c.tone_saved);
    c.tone_active = false;
    c.tone_candidate = 0;
    c.tone_count = 0;
}

'''
text = text.replace(fsk_comment, "", 1)
tone_start = text.find(tone_start_anchor)
tone_end = text.find(tone_anchor, tone_start if tone_start >= 0 else 0)
if tone_end < 0:
    raise SystemExit("pager.rs: cannot locate managed tone service insertion point")
if tone_start < 0:
    text = text[:tone_end] + '/// Level 18: managed FD6818B sub-audio scan with automatic restoration.\n' + tone_funcs + text[tone_end:]
else:
    text = text[:tone_start] + '/// Level 18: managed FD6818B sub-audio scan with automatic restoration.\n' + tone_funcs + text[tone_end:]
tone_end = text.find(tone_anchor)
text = text[:tone_end] + fsk_comment + text[tone_end:]
tone_doc = '/// Level 18: managed FD6818B sub-audio scan with automatic restoration.\n'
text = re.sub(r'(?m)(?:^/// Level 18: managed FD6818B sub-audio scan with automatic restoration\.\n)+', tone_doc, text)

once(
    '    let (live, tx, hz) = unsafe {\n'
    '        let c = &*addr_of!(MOD_CTX);\n'
    '        (!c.app.is_null(), c.tx, c.rx_hz)\n'
    '    };',
    '    let (live, tx, tone_active, hz) = unsafe {\n'
    '        let c = &*addr_of!(MOD_CTX);\n'
    '        (!c.app.is_null(), c.tx, c.tone_active, c.rx_hz)\n'
    '    };',
    "TX guard context",
)
once(
    '    if tx {\n        return -2;\n    }\n    let ms = max_ms.clamp(1, MOD_TX_MAX_MS);',
    '    if tx {\n        return -2;\n    }\n'
    '    if tone_active { return -1; }\n'
    '    let ms = max_ms.clamp(1, MOD_TX_MAX_MS);',
    "TX and tone detector exclusion",
)

once(
    '    unsafe { restore_module_page_buffer(); }\n'
    '    unsafe { mod_tx_off() }; // a module that left the transmitter on',
    '    unsafe { restore_module_page_buffer(); }\n'
    '    unsafe { mod_tone_stop() }; // restore the detector even if the module forgot\n'
    '    unsafe { mod_tx_off() }; // a module that left the transmitter on',
    "tone cleanup after module run",
)

# EXPLORE and IFP use temporary ModCtx literals too; keep the new detector state zeroed there.
pager.write_text(text)
for source in (pager, pager.parent / "pager" / "explore.rs"):
    if not source.exists():
        continue
    body = source.read_text()
    body = re.sub(
        r'(?m)^(\s*)tlm_cap: 0,\n\1tone_saved: 0,\n\1tone_candidate: 0,\n'
        r'\1tone_count: 0,\n\1tone_active: false,\n'
        r'(?:\1tone_saved: 0,\n\1tone_candidate: 0,\n\1tone_count: 0,\n\1tone_active: false,\n)+',
        r'\1tlm_cap: 0,\n\1tone_saved: 0,\n\1tone_candidate: 0,\n'
        r'\1tone_count: 0,\n\1tone_active: false,\n',
        body,
    )
    body = re.sub(
        r'(?m)^(\s*)tlm_cap: 0,\n(?![ \t]*tone_saved:)',
        r'\1tlm_cap: 0,\n'
        r'\1tone_saved: 0,\n'
        r'\1tone_candidate: 0,\n'
        r'\1tone_count: 0,\n'
        r'\1tone_active: false,\n',
        body,
    )
    source.write_text(body)
    if source == pager:
        text = body

pager.write_text(text)
print("Applied shared CW and managed CTCSS/DCS APIs (level 18)")
