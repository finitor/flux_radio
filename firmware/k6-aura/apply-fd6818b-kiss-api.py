#!/usr/bin/env python3
"""Add a module-owned raw KISS byte stream to the Blowfang UART API."""
from pathlib import Path

base = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src"
pager_path = base / "app/pager.rs"
uart_path = base / "hal/uart.rs"
out_path = base / "out.rs"
pager = pager_path.read_text()

field = '''        // level 14: module-owned KISS stream on the programming-cable UART.
        pub kiss_mode: unsafe extern "C" fn(i32) -> i32,
        pub serial_read: unsafe extern "C" fn() -> i32,
        pub serial_write: unsafe extern "C" fn(*const u8, u16) -> i32,
'''
if 'pub kiss_mode:' not in pager:
    anchor = '        pub afsk_tx_send: unsafe extern "C" fn(*const u8, u16) -> i32,\n'
    if pager.count(anchor) != 1: raise SystemExit("missing AFSK API field")
    pager = pager.replace(anchor, anchor + field, 1)
pager = pager.replace('level: if cfg!(feature = "fd6818b") { 13 } else { 9 },',
                      'level: if cfg!(feature = "fd6818b") { 14 } else { 9 },', 1)
if 'kiss_mode: mod_kiss_mode' not in pager:
    anchor = '    afsk_tx_send: mod_afsk_tx_send,\n'
    if pager.count(anchor) != 1: raise SystemExit("missing AFSK API initializer")
    pager = pager.replace(anchor, anchor + '''    kiss_mode: mod_kiss_mode,
    serial_read: mod_serial_read,
    serial_write: mod_serial_write,
''', 1)
if 'unsafe extern "C" fn mod_kiss_mode' not in pager:
    anchor = 'unsafe extern "C" fn mod_delay_us(mut us: u32) {'
    fns = '''/// Enter or leave the module-owned raw KISS UART mode. The global cable handshake
/// loop is suspended while the synchronous module runs; text reports are suppressed here.
unsafe extern "C" fn mod_kiss_mode(on: i32) -> i32 {
    if unsafe { (*addr_of!(MOD_CTX)).app.is_null() } { return -1; }
    crate::hal::uart::set_binary_mode(on != 0);
    0
}

/// Read one cable UART byte, or -1 when no byte is buffered.
unsafe extern "C" fn mod_serial_read() -> i32 {
    mod_tx_guard();
    crate::hal::uart::take_byte().map_or(-1, |b| b as i32)
}

/// Queue up to one KISS frame on the cable UART; the caller owns FEND/escaping.
unsafe extern "C" fn mod_serial_write(bytes: *const u8, count: u16) -> i32 {
    if bytes.is_null() || count > 512 || unsafe { (*addr_of!(MOD_CTX)).app.is_null() } {
        return -1;
    }
    for i in 0..count as usize {
        crate::hal::uart::send_byte(unsafe { *bytes.add(i) });
    }
    0
}

'''
    if pager.count(anchor) != 1: raise SystemExit("missing module delay insertion point")
    pager = pager.replace(anchor, fns + anchor, 1)
# Ensure a module that exits without closing KISS restores normal diagnostics.
if 'crate::hal::uart::set_binary_mode(false);' not in pager:
    anchor = '    let ret = unsafe { ffi::km_run_on_stack(arena::base(), &MOD_API, module_stack_top()) };'
    if anchor not in pager:
        anchor = '    let ret = unsafe { ffi::km_run(arena::base(), &MOD_API) };'
    if pager.count(anchor) != 1: raise SystemExit("missing module return anchor")
    pager = pager.replace(anchor, anchor + '\n    crate::hal::uart::set_binary_mode(false);', 1)
pager_path.write_text(pager)

uart = uart_path.read_text()
if 'pub fn set_binary_mode' not in uart:
    uart = 'use core::sync::atomic::{AtomicBool, Ordering};\n' + uart
    uart = uart.replace('const USER_VECTOR_USART1: usize = 1;\n', '''const USER_VECTOR_USART1: usize = 1;

static BINARY_MODE: AtomicBool = AtomicBool::new(false);

pub fn set_binary_mode(enabled: bool) { BINARY_MODE.store(enabled, Ordering::Relaxed); }
pub fn binary_mode() -> bool { BINARY_MODE.load(Ordering::Relaxed) }
''', 1)
uart_path.write_text(uart)

out = out_path.read_text()
old = '''impl Sink for Uart {
    fn bytes(&mut self, b: &[u8]) {
        for &c in b {
            crate::hal::uart::send_byte(c);
        }
    }
}'''
new = '''impl Sink for Uart {
    fn bytes(&mut self, b: &[u8]) {
        if crate::hal::uart::binary_mode() { return; }
        for &c in b {
            crate::hal::uart::send_byte(c);
        }
    }
}'''
if new not in out:
    if out.count(old) != 1: raise SystemExit("missing UART text sink")
    out = out.replace(old, new, 1)
out_path.write_text(out)
