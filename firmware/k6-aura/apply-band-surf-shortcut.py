#!/usr/bin/env python3
"""Route the Blowfang-host BAND short press to the installed SURF module."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src"
keys = root / "app/keys.rs"
text = keys.read_text()
import re

pattern = re.compile(r'(?ms)^([ \t]*)KeyId::Band => \{\n.*?^\1\}')
replacement = r"""\1KeyId::Band => {
                    #[cfg(all(feature = "blowfang-host", not(k6_no_scan)))]
                    pager::host_run_surf(app);
                    #[cfg(all(feature = "blowfang-host", k6_no_scan))]
                    scan::enter(app, syst);
                    #[cfg(not(feature = "blowfang-host"))]
                    {
                        let func = keyfn::from_u8(short_function(app, ev.key));
                        keyfn::invoke(app, syst, func);
                    }
                }"""
text2, count = pattern.subn(replacement, text, count=1)
if count != 1:
    raise SystemExit("keys.rs: cannot locate BAND shortcut block")
keys.write_text(text2)

pager = root / "app/pager.rs"
text = pager.read_text()
anchor = '''/// Enter Aura's sideloaded-module picker from the normal launcher.
#[cfg(feature = "blowfang-host")]
pub(super) fn host_enter(app: &mut App) {
'''
insert = '''/// Run the installed module named SURF from the Aura standby BAND key.
/// If it is not installed, leave the radio in standby and do nothing.
#[cfg(all(feature = "blowfang-host", feature = "spilib"))]
pub(super) fn host_run_surf(app: &mut App) {
    unsafe { CB_NOR = &mut app.storage.norflash as *mut _; }
    let mut found = None;
    for n in 0..KL_SLOTS {
        let mut info = ffi::KlInfo::default();
        if unsafe { ffi::kl_info(n, &LIB_FL, &mut info) } == 0 {
            let len = info.name.iter().position(|&c| c == 0).unwrap_or(info.name.len());
            if info.flags & 0x06 == 0 && &info.name[..len] == b"SURF" {
                found = Some(n as u8);
                break;
            }
        }
    }
    if let Some(slot) = found {
        unsafe {
            core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_MENU_OPEN), false);
            core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_LIB_SLOT), slot);
            core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_HOST_MENU_AFTER_LIB), false);
        }
        rl!("K6 BAND surf slot={}", slot);
    } else {
        rl!("K6 BAND surf unavailable");
    }
}

'''
if anchor in text and "pub(super) fn host_run_surf(app: &mut App)" not in text:
    text = text.replace(anchor, insert + anchor, 1)
elif "pub(super) fn host_run_surf(app: &mut App)" not in text:
    raise SystemExit("pager.rs: cannot locate host module picker")

# Host key shortcut runs should return to Aura; the regular module picker should reopen.
old_poll = '''        lib_run(app, syst, slot);
        #[cfg(feature = "blowfang-host")]
        menu_open(app);
'''
new_poll = '''        lib_run(app, syst, slot);
        #[cfg(feature = "blowfang-host")]
        {
            let reopen = unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_HOST_MENU_AFTER_LIB)) };
            unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_HOST_MENU_AFTER_LIB), true) };
            if reopen { menu_open(app); }
        }
'''
if old_poll in text:
    text = text.replace(old_poll, new_poll, 1)
elif new_poll not in text:
    raise SystemExit("pager.rs: cannot locate module-queue completion")

state = '''#[cfg(feature = "spilib")]
static mut PENDING_MENU_OPEN: bool = false;
'''
state_new = '''#[cfg(feature = "blowfang-host")]
static mut PENDING_HOST_MENU_AFTER_LIB: bool = true;
''' + state
if state in text and "static mut PENDING_HOST_MENU_AFTER_LIB" not in text:
    text = text.replace(state, state_new, 1)

pager.write_text(text)
print("Applied BAND-to-SURF shortcut")
