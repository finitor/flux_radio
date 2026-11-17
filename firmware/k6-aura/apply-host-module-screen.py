#!/usr/bin/env python3
"""Enable module-screen rendering in the lean Blowfang host image."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src/ui"
mod = root / "mod.rs"
text = mod.read_text()
plain_display = '#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]\nstatic mut MOD_DISPLAY:'
linked_display = '#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]\n#[link_section = ".data.mod_display"]\nstatic mut MOD_DISPLAY:'
if plain_display in text:
    text = text.replace(plain_display, linked_display, 1)
replacements = (
    ('#[cfg(not(feature = "lean"))]\nstatic mut MOD_DISPLAY:',
     '#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]\n#[link_section = ".data.mod_display"]\nstatic mut MOD_DISPLAY:'),
    ('#[cfg(not(feature = "lean"))]\nunsafe fn mod_flush',
     '#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]\nunsafe fn mod_flush'),
    ('#[cfg(not(feature = "lean"))]\npub fn hook_mod_screen',
     '#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]\npub fn hook_mod_screen'),
    ('#[cfg(feature = "lean")]\npub fn hook_mod_screen',
     '#[cfg(all(feature = "lean", not(feature = "blowfang-host")))]\npub fn hook_mod_screen'),
)
for old, new in replacements:
    if new not in text:
        if text.count(old) != 1:
            raise SystemExit(f"expected one UI hook anchor, found {text.count(old)}: {old!r}")
        text = text.replace(old, new, 1)
mod.write_text(text)

pager = root / "pager.rs"
text = pager.read_text()
old = '#[cfg(all(not(feature = "lean"), not(shared_lcd)))]\npub fn draw_mod_screen'
new = '#[cfg(all(any(not(feature = "lean"), feature = "blowfang-host"), not(shared_lcd)))]\npub fn draw_mod_screen'
if new not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one module renderer anchor, found {text.count(old)}")
    pager.write_text(text.replace(old, new, 1))

# The Blowfang host is a lean, non-shared-LCD build. Its ordinary graphics page buffer doubles
# as the C module stack, so module screen flushes must write raw controller pages instead.
text = mod.read_text()
old_host = '''    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
    {
        app::pager::module_lcd_diag(3);
        d.draw_pages(|page, buf| pager::draw_mod_page(buf, page, s));
        app::pager::module_lcd_diag(9);
    }'''
new_host = '''    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
    d.draw_pages(|page, buf| pager::draw_mod_page(buf, page, s));'''
if new_host not in text:
    if text.count(old_host) == 1:
        text = text.replace(old_host, new_host, 1)
    elif text.count(new_host) == 1:
        pass
    else:
        old = '''    #[cfg(shared_lcd)]
    d.draw_pages(|page, buf| pager::draw_mod_page(buf, page, s));
    #[cfg(not(shared_lcd))]
    {
        pager::draw_mod_screen(d.as_draw_target(), s);
        d.flush();
    }
'''
        new = '''    #[cfg(shared_lcd)]
    d.draw_pages(|page, buf| pager::draw_mod_page(buf, page, s));
    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
    d.draw_pages(|page, buf| pager::draw_mod_page(buf, page, s));
    #[cfg(all(not(shared_lcd), not(feature = "blowfang-host")))]
    {
        pager::draw_mod_screen(d.as_draw_target(), s);
        d.flush();
    }
'''
        if text.count(old) != 1:
            raise SystemExit(f"expected one module flush body, found {text.count(old)}")
        text = text.replace(old, new, 1)
    mod.write_text(text)

app_pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()
old = '#[cfg(all(not(feature = "lean"), shared_lcd))]\npub fn draw_mod_page'
new = '#[cfg(any(all(not(feature = "lean"), shared_lcd), all(feature = "blowfang-host", not(banded))))]\npub fn draw_mod_page'
if new not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one page renderer cfg, found {text.count(old)}")
    pager.write_text(text.replace(old, new, 1))

# Store the callback used to restore MOD_LCD after run_module updates its context. The saved
# display pointer itself is stable for the lifetime of main.
text = mod.read_text()
old = '''#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]
pub fn hook_mod_screen<DI: WriteOnlyDataCommand + 'static>(display: &mut Display<'_, DI>) {
    unsafe { *core::ptr::addr_of_mut!(MOD_DISPLAY) = display as *mut Display<'_, DI> as *mut () };
    app::pager::set_mod_lcd(mod_flush::<DI>);
}
'''
new = '''#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]
unsafe fn refresh_mod_screen<DI: WriteOnlyDataCommand + 'static>() {
    app::pager::set_mod_lcd(mod_flush::<DI>);
}

#[cfg(any(not(feature = "lean"), feature = "blowfang-host"))]
pub fn hook_mod_screen<DI: WriteOnlyDataCommand + 'static>(display: &mut Display<'_, DI>) {
    unsafe { *core::ptr::addr_of_mut!(MOD_DISPLAY) = display as *mut Display<'_, DI> as *mut () };
    app::pager::set_mod_lcd(mod_flush::<DI>);
    #[cfg(feature = "blowfang-host")]
    app::pager::set_mod_lcd_refresh(refresh_mod_screen::<DI>);
}
'''
if new not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one module-screen hook, found {text.count(old)}")
    mod.write_text(text.replace(old, new, 1))

# Keep the graphics driver out of the module stack buffer.
display = root.parent / "device/display.rs"
text = display.read_text()
anchor = 'use display_interface::WriteOnlyDataCommand;\n'
insert = '''use display_interface::WriteOnlyDataCommand;
'''
text = text.replace('''#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
#[repr(align(8))]
pub(crate) struct HostDisplayStorage([u64; 16]);
#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
pub(crate) static mut HOST_DISPLAY_STORAGE: HostDisplayStorage = HostDisplayStorage([0; 16]);
''', '')
old_page_storage = '''#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
static mut MOD_LCD_PAGE: [u8; 128] = [0; 128];
'''
if 'static mut HOST_DISPLAY_STORAGE' not in text:
    if text.count(old_page_storage) == 1:
        text = text.replace(old_page_storage, insert.split('\n', 2)[2], 1)
    elif text.count(anchor) == 1:
        text = text.replace(anchor, insert, 1)
    else:
        raise SystemExit("expected display storage anchor")

anchor = '''    #[cfg(banded)]
    pub fn draw_pages(&mut self, mut draw: impl FnMut(u8, &mut [u8; 128])) {
'''
method = '''    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
    pub fn draw_pages(&mut self, mut draw: impl FnMut(u8, &mut [u8; 128])) {
        let (detached, mut interface) = self.lcd.take().unwrap().release_display_interface();
        let col = <display_spec::Sc5260Spec as st7565::DisplaySpecs<128, 64, 8>>::COLUMN_OFFSET;
        let mut buf = [0u8; 128];
        for page in 0..8u8 {
            buf.fill(0);
            draw(page, &mut buf);
            interface
                .send_commands(DataFormat::U8(&[0xB0 | page, 0x10 | (col >> 4), col & 0x0F]))
                .ok();
            interface.send_data(DataFormat::U8(&buf)).ok();
        }
        self.lcd = Some(detached.attach_display_interface(interface));
    }

'''
old_page_loop = '''        let buf = unsafe { &mut *core::ptr::addr_of_mut!(MOD_LCD_PAGE) };
        for page in 0..8u8 {
            buf.fill(0);
            draw(page, buf);
'''
new_page_loop = '''        let mut buf = [0u8; 128];
        for page in 0..8u8 {
            buf.fill(0);
            draw(page, &mut buf);
'''
if old_page_loop in text:
    text = text.replace(old_page_loop, new_page_loop, 1)
text = text.replace('interface.send_data(DataFormat::U8(buf)).ok();',
                    'interface.send_data(DataFormat::U8(&buf)).ok();')
if '#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n    pub fn draw_pages' not in text:
    if text.count(anchor) != 1:
        raise SystemExit("expected draw_pages method anchor")
    text = text.replace(anchor, method + anchor, 1)
display.write_text(text)

# Strip the temporary page-by-page checkpoints used during LCD bring-up.
text = display.read_text()
instrumented = '''        for page in 0..8u8 {
            let diag = page == 0 && unsafe { !MOD_LCD_DIAG_DONE };
            if diag {
                unsafe { MOD_LCD_DIAG_DONE = true; }
                crate::app::pager::module_lcd_diag(4);
            }
            buf.fill(0);
            draw(page, buf);
            if diag { crate::app::pager::module_lcd_diag(5); }
            if diag { crate::app::pager::module_lcd_diag(6); }
            interface
                .send_commands(DataFormat::U8(&[0xB0 | page, 0x10 | (col >> 4), col & 0x0F]))
                .ok();
            if diag { crate::app::pager::module_lcd_diag(7); }
            interface.send_data(DataFormat::U8(buf)).ok();
            if diag { crate::app::pager::module_lcd_diag(8); }
        }'''
plain = '''        for page in 0..8u8 {
            buf.fill(0);
            draw(page, buf);
            interface
                .send_commands(DataFormat::U8(&[0xB0 | page, 0x10 | (col >> 4), col & 0x0F]))
                .ok();
            interface.send_data(DataFormat::U8(buf)).ok();
        }'''
if instrumented in text:
    text = text.replace(instrumented, plain, 1)
text = text.replace('''#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]
static mut MOD_LCD_DIAG_DONE: bool = false;
''', '')
display.write_text(text)

# Reinstall the monomorphized callback after MOD_CTX is initialized and before C module dispatch.
app_pager = root.parent / "app/pager.rs"
text = app_pager.read_text()
if "fn module_lcd_stack_top()" not in text:
    anchor = '#[cfg(feature = "blowfang-host")]\nfn cardlink_module_loaded()'
    helper = """#[cfg(feature = "blowfang-host")]
fn module_lcd_stack_top() -> *mut u8 {
    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {
        unsafe { core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>().add(1152) }
    } else { arena::end() as *mut u8 }
}

"""
    if text.count(anchor) != 1:
        raise SystemExit("expected cardlink module helper anchor")
    text = text.replace(anchor, helper + anchor, 1)
text = text.replace("""fn scratch_end() -> usize {
    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {
        arena::end().saturating_sub(2048)
    } else {
        arena::end()
    }
}""", """fn scratch_end() -> usize {
    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {
        arena::end().saturating_sub(2048)
    } else {
        arena::end().saturating_sub(1024) // isolated LCD callback stack
    }
}""")
text = text.replace("""fn scratch_end() -> usize {
    if unsafe { (*addr_of!(MOD_CTX)).tlm_cap } != 0 {
        arena::tlm() as usize
    } else {
        arena::end()
    }
}""", """fn scratch_end() -> usize {
    if unsafe { (*addr_of!(MOD_CTX)).tlm_cap } != 0 {
        arena::tlm() as usize
    } else {
        arena::end().saturating_sub(1024) // isolated LCD callback stack
    }
}""")
old = '''unsafe extern "C" fn mod_lcd_flush() -> i32 {
    mod_tx_guard();
    if unsafe { (*addr_of!(MOD_CTX)).app.is_null() } {
        rl!("K6 LCD flush no module context");
        return -2;
    }
    match unsafe { *addr_of!(MOD_LCD) } {
        Some(f) => unsafe { f() },
        None => {
            rl!("K6 LCD flush no hook");
            -1
        }
    }
}
'''
new = '''#[cfg(feature = "blowfang-host")]
static mut MOD_LCD_RESULT: i32 = -1;

#[cfg(feature = "blowfang-host")]
unsafe extern "C" fn mod_lcd_call_host(_arg: *mut core::ffi::c_void) {
    let result = match unsafe { *addr_of!(MOD_LCD) } {
        Some(f) => unsafe { f() },
        None => {
            rl!("K6 LCD flush no hook");
            -1
        }
    };
    unsafe { *addr_of_mut!(MOD_LCD_RESULT) = result };
}

unsafe extern "C" fn mod_lcd_flush() -> i32 {
    mod_tx_guard();
    if unsafe { (*addr_of!(MOD_CTX)).app.is_null() } {
        rl!("K6 LCD flush no module context");
        return -2;
    }
    #[cfg(feature = "blowfang-host")]
    {
        unsafe { ffi::km_call_host_stack(mod_lcd_call_host, core::ptr::null_mut(), module_lcd_stack_top()) };
        unsafe { *addr_of!(MOD_LCD_RESULT) }
    }
    #[cfg(not(feature = "blowfang-host"))]
    match unsafe { *addr_of!(MOD_LCD) } {
        Some(f) => unsafe { f() },
        None => -1,
    }
}
'''
if new not in text:
    if text.count(old) == 1:
        text = text.replace(old, new, 1)
    else:
        start = text.find('#[cfg(feature = "blowfang-host")]\nstatic mut MOD_LCD_RESULT: i32 = -1;')
        end = text.find('// ---- telemetry:', start)
        if start < 0 or end < 0:
            raise SystemExit(f"expected one LCD callback function, found {text.count(old)}")
        text = text[:start] + new + '\n' + text[end:]

anchor = '''pub fn set_mod_lcd(f: unsafe fn() -> i32) {
    unsafe { *addr_of_mut!(MOD_LCD) = Some(f) };
    rl!("K6 LCD hook registered");
}
'''
replacement = anchor + '''
#[cfg(feature = "blowfang-host")]
static mut MOD_LCD_REFRESH: Option<unsafe fn()> = None;

#[cfg(feature = "blowfang-host")]
pub fn set_mod_lcd_refresh(f: unsafe fn()) {
    unsafe { *addr_of_mut!(MOD_LCD_REFRESH) = Some(f) };
}

#[cfg(feature = "blowfang-host")]
unsafe fn refresh_mod_lcd() {
    if let Some(f) = unsafe { *addr_of!(MOD_LCD_REFRESH) } {
        unsafe { f() };
    }
}
'''
if 'fn refresh_mod_lcd()' not in text:
    if text.count(anchor) != 1:
        raise SystemExit("expected set_mod_lcd anchor")
    text = text.replace(anchor, replacement, 1)

anchor = '''    mod_screen_clear();
'''
replacement = '''    mod_screen_clear();
    #[cfg(feature = "blowfang-host")]
    unsafe { refresh_mod_lcd(); }
'''
if replacement not in text:
    if text.count(anchor) != 1:
        raise SystemExit("expected module-dispatch anchor")
    text = text.replace(anchor, replacement, 1)
app_pager.write_text(text)

# The driver contains a reference into the page buffer. Keep it in main's frame rather than
# relocating it into an ad-hoc byte array; the module stack is switched independently.
main = root.parent / "main.rs"
text = main.read_text()
if 'let display_value = Display::new(lcd);' in text:
    start = text.index('    let display_value = Display::new(lcd);')
    end = text.index('    #[cfg(banded)]\n    display.draw_pages', start)
    text = text[:start] + '    let mut display = Display::new(lcd);\n' + text[end:]
main.write_text(text)
