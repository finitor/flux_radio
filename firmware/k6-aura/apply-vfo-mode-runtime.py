#!/usr/bin/env python3
"""Install opt-in Data-only native lifecycle probe in the Aura main loop."""
from pathlib import Path
import re
here = Path(__file__).parent
src = here / 'build/aura-fd6818b-port/src'
main = src / 'main.rs'
text = main.read_text()
cfg = '#[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe))]'
def insert(anchor, addition):
    global text
    if addition in text:
        return
    if text.count(anchor) != 1:
        raise SystemExit(f'expected one native VFO anchor: {anchor}')
    text = text.replace(anchor, addition + anchor, 1)
insert('#[entry]\nfn main() -> ! {', cfg + '\nmod vfo_mode_runtime;\n')
insert('    // scheduler + main loop', '    ' + cfg + '\n    let mut resident_probe = vfo_mode_runtime::Runtime::new();\n')
# Release before cable work. For this milestone only a built-in probe is
# active; actual arena code and lease remain unsupported.
anchor = '        match host_handshake.poll() {'
if 'Some(cps::HostHandshake::Aura) => {' not in text:
    old = '''            Some(cps::HostHandshake::Aura) =>
                cps::run_session(&mut app, &mut cp.SYST, &mut display, &mut dbg),
            Some(cps::HostHandshake::Cable) if !app.is_transmitting() =>
                cps::run_cable_session(&mut app, &mut cp.SYST, &mut display),'''
    new = '''            Some(cps::HostHandshake::Aura) => {
                ''' + cfg + '''
                resident_probe.stop();
                cps::run_session(&mut app, &mut cp.SYST, &mut display, &mut dbg);
            }
            Some(cps::HostHandshake::Cable) if !app.is_transmitting() => {
                ''' + cfg + '''
                resident_probe.stop();
                cps::run_cable_session(&mut app, &mut cp.SYST, &mut display);
            }'''
    if text.count(old) != 1:
        raise SystemExit('missing host handshake routes')
    text = text.replace(old, new, 1)
insert('        // Screen: redraw on every_50ms', '        ' + cfg + '\n        resident_probe.tick(&app);\n\n')
# Earlier host overlays can reinsert the unguarded handshake on rebuild.
# Normalize to exactly one path, with cleanup before either cable session.
plain = """        #[cfg(feature = "blowfang-host")]
        match host_handshake.poll() {
            Some(cps::HostHandshake::Aura) =>
                cps::run_session(&mut app, &mut cp.SYST, &mut display, &mut dbg),
            Some(cps::HostHandshake::Cable) if !app.is_transmitting() =>
                cps::run_cable_session(&mut app, &mut cp.SYST, &mut display),
            _ => {}
        }
"""
if "resident_probe.stop();" in text:
    text = text.replace(plain, "")
if text.count("match host_handshake.poll() {") != 1:
    raise SystemExit("expected exactly one host handshake dispatcher")
text = text.replace('        #[cfg(not(feature = "blowfang-host"))]\n        #[cfg(not(feature = "blowfang-host"))]\n', '        #[cfg(not(feature = "blowfang-host"))]\n')
# Earlier diagnostics overlays may reinsert an unguarded queue poll on rebuild.
# Normalize the entire adjacent block: exactly one stop check and one queue poll.
pattern = (r'(        poll_keys_on_arena\(&mut app, &mut cp.SYST\);\n)'
           r'(?:(?:        #\[cfg\([^\n]+|'
           r'        if app.resident_arena_busy\(\) \{ resident_probe.stop\(\); \}|'
           r'        app.poll_pager\(&mut cp.SYST\); // shallow host path services queued modules after key handling)\n)+')
replacement = (r'\1' + '        ' + cfg + '\n'
               '        if app.resident_arena_busy() { resident_probe.stop(); }\n'
               '        #[cfg(feature = "blowfang-host")]\n'
               '        app.poll_pager(&mut cp.SYST); // shallow host path services queued modules after key handling\n')
text, matches = re.subn(pattern, replacement, text)
if matches != 1 or text.count('// shallow host path services queued modules after key handling') != 1:
    raise SystemExit('expected exactly one guarded foreground queue poll')
main.write_text(text)
(src / 'vfo_mode_runtime.rs').write_text((here / 'vfo-mode-runtime.rs').read_text())

build = src.parent / 'build.rs'
bt = build.read_text()
check = '    println!("cargo:rustc-check-cfg=cfg(k6_vfo_probe)");'
if check not in bt:
    anchor = 'fn main() {'
    assert bt.count(anchor) == 1
    build.write_text(bt.replace(anchor, anchor + '\n' + check, 1))

pager = src / 'app/pager.rs'
pt = pager.read_text()
helper = '''#[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe))]
pub(super) fn resident_arena_busy() -> bool {
    // Sotto may write the arena during receive even without a queued job.
    !cfg!(k6_no_sotto) || unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_LIB_SLOT)) != 255 }
}
'''
if helper not in pt:
    pager.write_text(pt + '\n' + helper)
app = src / 'app/mod.rs'
at = app.read_text()
helper = '''    #[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe))]
    pub fn resident_arena_busy(&self) -> bool {
        pager::resident_arena_busy()
    }
'''
if helper not in at:
    anchor = '    pub fn poll_pager(&mut self, syst: &mut SYST) {'
    assert at.count(anchor) == 1
    app.write_text(at.replace(anchor, helper + anchor, 1))

pt = pager.read_text()
helper = """#[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe))]
pub(super) fn resident_invalidate_cached_module() {
    unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(KEPT), false); }
}
"""
if helper not in pt:
    pager.write_text(pt + '\n' + helper)
at = app.read_text()
helper = """    #[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe))]
    pub fn resident_invalidate_cached_module(&self) {
        pager::resident_invalidate_cached_module();
    }
"""
if helper not in at:
    anchor = '    pub fn poll_pager(&mut self, syst: &mut SYST) {'
    assert at.count(anchor) == 1
    app.write_text(at.replace(anchor, helper + anchor, 1))

# Experimental SPI-backed probe uses the same library callbacks as foreground modules.
bt = build.read_text()
check = '    println!("cargo:rustc-check-cfg=cfg(k6_vfo_spi_probe)");'
if check not in bt:
    build.write_text(bt.replace('fn main() {', 'fn main() {\n' + check, 1))
pt = pager.read_text()
helper = """
#[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe, k6_vfo_spi_probe))]
pub(super) fn resident_probe_slot() -> i32 {
    extern "C" { fn kl_find_resident(id: u32, fl: *const ffi::KlFlash) -> i32; }
    unsafe { kl_find_resident(41, &LIB_FL) }
}
#[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe, k6_vfo_spi_probe))]
pub(super) fn resident_probe_load(slot: i32, cap: usize, info: &mut crate::vfo_mode_runtime::ResidentInfo) -> i32 {
    extern "C" {
        fn kl_load_resident(slot: i32, fl: *const ffi::KlFlash, dst: *mut u8, cap: u32,
                            id: u32, info: *mut crate::vfo_mode_runtime::ResidentInfo) -> i32;
    }
    unsafe {
        ffi::km_reset();
        kl_load_resident(slot, &LIB_FL, arena::base(), cap as u32, 41, info)
    }
}
"""
if helper not in pt:
    pager.write_text(pt + helper)
at = app.read_text()
helper = """    #[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe, k6_vfo_spi_probe))]
    pub fn resident_probe_slot(&self) -> i32 { pager::resident_probe_slot() }
    #[cfg(all(feature = "blowfang-host", not(k6_no_fsk_rx), k6_vfo_probe, k6_vfo_spi_probe))]
    pub fn resident_probe_load(&self, slot: i32, cap: usize, info: &mut crate::vfo_mode_runtime::ResidentInfo) -> i32 {
        pager::resident_probe_load(slot, cap, info)
    }
"""
if helper not in at:
    anchor = '    pub fn poll_pager(&mut self, syst: &mut SYST) {'
    assert at.count(anchor) == 1
    app.write_text(at.replace(anchor, helper + anchor, 1))
