#!/usr/bin/env python3
"""Run the entire Blowfang cable session on the reserved main stack."""
from pathlib import Path

path = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src/cps/mod.rs"
text = path.read_text()

# The previous experiment switched only each chunk. That leaves FrameReader and the cable
# session's other long-lived locals on Aura's shallow application stack, so move the whole
# non-returning cable session to the linker-reserved stack before constructing any of them.
text = text.replace('''                // The application stack has very little headroom at this point in the main
                // loop. Run the complete packet parse + optional SPI install on the reserved
                // arena stack, not just the C packet parser. Keep the tiny handoff context in
                // the unused tail of Frame::data so setting up the stack switch adds no locals
                // to this already-deep frame.
                let p = f.data.as_ptr() as *mut u8;
                unsafe { core::ptr::write_unaligned(p.add(64).cast::<u32>(), app as *mut App as u32); }
                unsafe extern "C" {
                    static _stack_start: u32;
                    fn km_call_on_stack(
                        stack_top: *mut u8,
                        f: unsafe extern "C" fn(*mut core::ffi::c_void),
                        arg: *mut core::ffi::c_void,
                    );
                }
                unsafe {
                    km_call_on_stack(
                        core::ptr::addr_of!(_stack_start) as *mut u8,
                        cable_chunk_on_arena_stack,
                        p.cast(),
                    );
                }
                let (r, have, count, put) = unsafe {
                    (*p.add(68).cast::<i8>(), *p.add(69), *p.add(70),
                     i32::from_le_bytes([*p.add(71), *p.add(72), *p.add(73), *p.add(74)]))
                };''',
'''                let (r, have, count, put) = app.cable_chunk(&f.data[..64]);''')

start = text.find('#[cfg(feature = "spilib")]\npub fn run_cable_session<DI: WriteOnlyDataCommand>')
if start >= 0:
    signature = '''#[cfg(feature = "spilib")]
pub fn run_cable_session<DI: WriteOnlyDataCommand>(
    app: &mut App,
    syst: &mut SYST,
    display: &mut Display<'_, DI>,
) -> ! {'''
    replacement = '''#[cfg(feature = "spilib")]
struct CableSessionArgs<'d, DI: WriteOnlyDataCommand> {
    app: *mut App,
    syst: *mut SYST,
    display: *mut Display<'d, DI>,
}

#[cfg(feature = "spilib")]
unsafe extern "C" fn cable_session_on_reserved_stack<'d, DI: WriteOnlyDataCommand + 'static>(
    raw: *mut core::ffi::c_void,
) {
    let args = unsafe { &mut *raw.cast::<CableSessionArgs<'d, DI>>() };
    run_cable_session_inner(unsafe { &mut *args.app }, unsafe { &mut *args.syst },
                            unsafe { &mut *args.display });
}

#[cfg(feature = "spilib")]
#[inline(never)]
pub fn run_cable_session<DI: WriteOnlyDataCommand + 'static>(
    app: &mut App,
    syst: &mut SYST,
    display: &mut Display<'_, DI>,
) -> ! {
    let mut args = CableSessionArgs { app, syst, display };
    unsafe extern "C" {
        static _stack_start: u32;
        fn km_call_on_stack(
            stack_top: *mut u8,
            f: unsafe extern "C" fn(*mut core::ffi::c_void),
            arg: *mut core::ffi::c_void,
        );
    }
    unsafe {
        km_call_on_stack(
            core::ptr::addr_of!(_stack_start) as *mut u8,
            cable_session_on_reserved_stack::<DI>,
            (&mut args as *mut CableSessionArgs<'_, DI>).cast(),
        );
    }
    loop { core::hint::spin_loop(); }
}

#[cfg(feature = "spilib")]
#[inline(never)]
fn run_cable_session_inner<DI: WriteOnlyDataCommand>(
    app: &mut App,
    syst: &mut SYST,
    display: &mut Display<'_, DI>,
) -> ! {'''
    if signature not in text:
        if 'fn run_cable_session_inner<' not in text:
            raise SystemExit("could not find cable session signature")
    else:
        text = text.replace(signature, replacement, 1)

# Drop the old per-chunk callback after moving the complete session instead.
marker = '\n#[cfg(feature = "spilib")]\nunsafe extern "C" fn cable_chunk_on_arena_stack('
idx = text.find(marker)
if idx >= 0:
    text = text[:idx] + '\n'

path.write_text(text)

# The packet parser now runs on the reserved stack as part of the session.
pager = path.parent.parent / "app/pager.rs"
pager_text = pager.read_text().replace(
    'ffi::km_packet_on_stack(pkt.as_ptr(), pkt.len() as i32, arena::base(), arena::ARENA_BYTES as u32)',
    'ffi::km_packet(pkt.as_ptr(), pkt.len() as i32, arena::base(), arena::ARENA_BYTES as u32)',
)
pager.write_text(pager_text)

# The cable session never returns and reuses the SRAM-top stack. Draw while
# the caller's stack-resident Display is still intact, using the idle arena.
text = path.read_text()
old_callback = """    run_cable_session_inner(unsafe { &mut *args.app }, unsafe { &mut *args.syst },
                            unsafe { &mut *args.display });
}
"""
new_callback = """    run_cable_session_inner(unsafe { &mut *args.app }, unsafe { &mut *args.syst });
}

#[cfg(feature = "spilib")]
unsafe extern "C" fn draw_cable_screen_on_arena<'d, DI: WriteOnlyDataCommand + 'static>(
    raw: *mut core::ffi::c_void,
) {
    let display = unsafe { &mut *raw.cast::<Display<'d, DI>>() };
    crate::screen!(display, |lcd| ui::cps::draw_lines(lcd, "FLUX", "CATALOG LOAD..."));
}
"""
if new_callback not in text and 'draw_cable_screen_on_arena' not in text:
    assert text.count(old_callback) == 1
    text = text.replace(old_callback, new_callback, 1)
    text = text.replace('struct CableSessionArgs<\'d, DI: WriteOnlyDataCommand> {', 'struct CableSessionArgs {', 1)
    text = text.replace("    display: *mut Display<'d, DI>,\n", "", 1)
    text = text.replace("raw.cast::<CableSessionArgs<'d, DI>>()", 'raw.cast::<CableSessionArgs>()', 1)
    text = text.replace('let mut args = CableSessionArgs { app, syst, display };', """static mut ARGS: CableSessionArgs = CableSessionArgs {
        app: core::ptr::null_mut(), syst: core::ptr::null_mut(),
    };
    unsafe { core::ptr::addr_of_mut!(ARGS).write(CableSessionArgs { app, syst }); }""", 1)
    text = text.replace("""        km_call_on_stack(
            core::ptr::addr_of!(_stack_start) as *mut u8,""", """        km_call_on_stack(
            crate::hal::arena::end() as *mut u8,
            draw_cable_screen_on_arena::<DI>,
            (display as *mut Display<'_, DI>).cast(),
        );
        km_call_on_stack(
            core::ptr::addr_of!(_stack_start) as *mut u8,""", 1)
    text = text.replace("(&mut args as *mut CableSessionArgs<'_, DI>).cast()", 'core::ptr::addr_of_mut!(ARGS).cast()', 1)
    old_inner = """fn run_cable_session_inner<DI: WriteOnlyDataCommand>(
    app: &mut App,
    syst: &mut SYST,
    display: &mut Display<'_, DI>,
) -> ! {"""
    assert text.count(old_inner) == 1
    text = text.replace(old_inner, 'fn run_cable_session_inner(app: &mut App, syst: &mut SYST) -> ! {', 1)
    old_draw = '    uart::send_byte(ACK);\n    crate::screen!(display, |lcd| ui::cps::draw_lines(lcd, "FLUX", "CATALOG LOAD..."));'
    assert text.count(old_draw) == 1
    text = text.replace(old_draw, '    uart::send_byte(ACK);', 1)
    path.write_text(text)
