#!/usr/bin/env python3
"""Add narrow serial checkpoints around module entry and the FD6818B FSK start."""
from pathlib import Path

pager = Path(__file__).parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = pager.read_text()

ffi_anchor = '        pub fn km_run(arena: *mut u8, api: *const K6Api) -> i32;'
stack_decl = '        pub fn km_run_on_stack(arena: *mut u8, api: *const K6Api, stack_top: *mut u8) -> i32;'
if stack_decl not in text:
    if text.count(ffi_anchor) != 1:
        raise SystemExit(f"expected one km_run FFI anchor, found {text.count(ffi_anchor)}")
    text = text.replace(ffi_anchor, ffi_anchor + '\n' + stack_decl, 1)
host_call_decl = '        pub fn km_call_host_stack(f: unsafe extern "C" fn(*mut core::ffi::c_void), arg: *mut core::ffi::c_void, stack_top: *mut u8);'
text = text.replace(
    '        pub fn km_call_host_stack(f: unsafe extern "C" fn(*mut core::ffi::c_void), arg: *mut core::ffi::c_void);',
    host_call_decl,
)
if host_call_decl not in text:
    if text.count(stack_decl) != 1:
        raise SystemExit(f"expected one km_run_on_stack FFI anchor, found {text.count(stack_decl)}")
    text = text.replace(stack_decl, stack_decl + '\n' + host_call_decl, 1)

replacements = (
    (
        '    let gpio = app.radio.fd6818.reg_read(syst, MOD_GPIO);',
        '    let gpio = app.radio.fd6818.reg_read(syst, MOD_GPIO);',
    ),
    (
        '    let ret = unsafe { ffi::km_run(arena::base(), &MOD_API) };',
        '    #[cfg(feature = "blowfang-host")]\n'
        '    let ret = unsafe { ffi::km_run_on_stack(arena::base(), &MOD_API, module_stack_top()) };\n'
        '    #[cfg(not(feature = "blowfang-host"))]\n'
        '    let ret = unsafe { ffi::km_run(arena::base(), &MOD_API) };\n'
        '    #[cfg(feature = "blowfang-host")]\n'
        '    unsafe { if let Some(reset) = MOD_STACK_RESET { reset(MOD_STACK_RESET_BUF as *mut u8); } }\n'
        '',
    ),
    (
        '        app.radio.fd6818.enter_fsk_mode(syst);',
        '        rl!("K6 FSK start begin");\n'
        '        app.radio.fd6818.enter_fsk_mode(syst);\n'
        '        rl!("K6 FSK start done");',
    ),
    (
        '        let _ = (app, syst);\n        return;',
        '        #[cfg(feature = "spilib")]\n'
        '        poll_library_queue(app, syst);\n'
        '        return;',
    ),
    (
        'lib_run(app, syst, m.slots[(sel - MENU_CORE) as usize]);',
        'queue_lib_run(m.slots[(sel - MENU_CORE) as usize]);',
    ),
    (
        'KeyId::Side1 => lib_run(app, syst, AGAIN_SLOT),',
        'KeyId::Side1 => queue_lib_run(AGAIN_SLOT),',
    ),
    (
        '        lib_run(app, syst, vv);',
        '        queue_lib_run(vv);',
    ),
    (
        '    slots: [u8; KL_SLOTS as usize],',
        '    slots: [u8; KL_SLOTS as usize],\n'
        '    /// names captured during the deferred SPI scan; drawing never reads SPI\n'
        '    names: [[u8; 12]; KL_SLOTS as usize],',
    ),
    (
        'static mut MENU: Menu = Menu { on: false, sel: 0, n: 0, slots: [0; KL_SLOTS as usize] };',
        'static mut MENU: Menu = Menu { on: false, sel: 0, n: 0, slots: [0; KL_SLOTS as usize], names: [[0; 12]; KL_SLOTS as usize] };',
    ),
    (
        '    let mut inf = ffi::KlInfo::default();\n'
        '    if unsafe { ffi::kl_info(slot as i32, &LIB_FL, &mut inf) } == 0 && inf.name[0] != 0 {\n'
        '        let n = inf.name.iter().position(|&c| c == 0).unwrap_or(inf.name.len());\n'
        '        out[..n].copy_from_slice(&inf.name[..n]);\n'
        '        return n;\n'
        '    }',
        '    let name = &m.names[(i - MENU_CORE) as usize];\n'
        '    if name[0] != 0 {\n'
        '        let n = name.iter().position(|&c| c == 0).unwrap_or(name.len());\n'
        '        out[..n].copy_from_slice(&name[..n]);\n'
        '        return n;\n'
        '    }',
    ),
    (
        '            m.slots[m.n as usize] = n as u8;\n'
        '            m.n += 1;',
        '            let index = m.n as usize;\n'
        '            m.slots[index] = n as u8;\n'
        '            m.names[index] = i.name;\n'
        '            m.n += 1;',
    ),
    (
        '        menu_open(app);',
        '        unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_MENU_OPEN), true) };\n'
        '        rl!("K6 MENU open queued");\n'
        '        return true;',
    ),
    (
        '        scratch_end().saturating_sub(scratch)\n    );',
        '        scratch_end().saturating_sub(scratch)\n    );\n'
        '    #[cfg(not(feature = "blowfang-host"))]\n'
        '    if room < 512 {\n'
        '        rl!("K6 MOD refused: only {} B stack before dispatch", room);\n'
        '        unsafe { ffi::km_reset() };\n'
        '        return;\n'
        '    }\n'
        '    #[cfg(feature = "blowfang-host")]\n'
        '    if module_stack_bytes() < 768 {\n'
        '        rl!("K6 MOD refused: dedicated stack is only {} B", module_stack_bytes());\n'
        '        unsafe { ffi::km_reset() };\n'
        '        return;\n'
        '    }',
    ),
)

for old, new in replacements:
    if new in text:
        continue
    count = text.count(old)
    if old == 'lib_run(app, syst, m.slots[(sel - MENU_CORE) as usize]);':
        if count == 0:
            raise SystemExit(f"expected source anchor, found {count}: {old!r}")
        text = text.replace(old, new)
        continue
    if old == '        let _ = (app, syst);\n        return;':
        if count != 2:
            raise SystemExit(f"expected the poll and disarm anchors, found {count}")
        first = text.find(old)
        second = text.find(old, first + len(old))
        text = text[:second] + new + text[second + len(old):]
        continue
    if count != 1:
        raise SystemExit(f"expected one source anchor, found {count}: {old!r}")
    text = text.replace(old, new, 1)

# The fd6818b pager's normal poll routine has a large frame. The compact Aura host must service
# library/menu work through a shallow helper so that a selected module gets the stack the poller
# otherwise reserves for voice decoding and pager state.
inline_queue = (
    '            let open = unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_MENU_OPEN)) };\n'
    '            if open {\n'
    '                unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_MENU_OPEN), false) };\n'
    '                menu_open(app);\n'
    '            }\n'
    '            let slot = unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_LIB_SLOT)) };\n'
    '            if slot != 255 {\n'
    '                unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_LIB_SLOT), 255) };\n'
    '                rl!("K6 MENU dispatch queued slot={}", slot);\n'
    '                lib_run(app, syst, slot);\n'
    '            }'
)
text = text.replace(inline_queue, '            poll_library_queue(app, syst);')

if 'fn poll_library_queue(' not in text:
    anchor = (
        'fn lib_run(app: &mut App, syst: &mut SYST, mut n: u8) {\n'
    )
    queue_helper = (
        'fn queue_lib_run(slot: u8) {\n'
        '    unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_LIB_SLOT), slot) };\n'
        '    rl!("K6 MENU queued slot={}", slot);\n'
        '}\n\n'
        '#[cfg(feature = "spilib")]\n'
        '#[inline(never)]\n'
        'pub(super) fn poll_library_queue(app: &mut App, syst: &mut SYST) {\n'
        '    let open = unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_MENU_OPEN)) };\n'
        '    if open {\n'
        '        unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_MENU_OPEN), false) };\n'
        '        menu_open(app);\n'
        '    }\n'
        '    let slot = unsafe { core::ptr::read_volatile(core::ptr::addr_of!(PENDING_LIB_SLOT)) };\n'
        '    if slot != 255 {\n'
        '        unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_LIB_SLOT), 255) };\n'
        '        rl!("K6 MENU dispatch queued slot={}", slot);\n'
        '        lib_run(app, syst, slot);\n'
        '    }\n'
        '}\n'
        '\n'
        + anchor
    )
    if text.count(anchor) != 1:
        raise SystemExit(f"expected one queue function anchor, found {text.count(anchor)}")
    text = text.replace(anchor, queue_helper, 1)

if 'fn set_module_stack(' not in text:
    marker = 'struct ModCtx {'
    module_stack = (
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_START: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_TOP: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_RESET: Option<unsafe extern "C" fn(*mut u8)> = None;\n\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_RESET_BUF: usize = 0;\n\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK: [u8; 1152] = [0; 1152];\n\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'pub fn set_module_stack(buf: *mut u8, bytes: usize, reset: unsafe extern "C" fn(*mut u8)) {\n'
        '    let _ = bytes; // the page buffer is restored after module return, not used as stack\n'
        '    let start = core::ptr::addr_of_mut!(MOD_STACK) as *mut u8 as usize;\n'
        '    let top = start.saturating_add(1152) & !7usize;\n'
        '    unsafe {\n'
        '        MOD_STACK_START = start;\n'
        '        MOD_STACK_TOP = top;\n'
        '        MOD_STACK_RESET = Some(reset);\n'
        '        MOD_STACK_RESET_BUF = buf as usize;\n'
        '    }\n'
        '}\n\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_stack_top() -> *mut u8 { unsafe { MOD_STACK_TOP as *mut u8 } }\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_stack_bytes() -> usize { unsafe { MOD_STACK_TOP.saturating_sub(MOD_STACK_START) } }\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_lcd_stack_top() -> *mut u8 {\n'
        '    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {\n'
        '        unsafe { core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>().add(1152) }\n'
        '    } else { arena::end() as *mut u8 }\n'
        '}\n\n'
    )
    if text.count(marker) != 1:
        raise SystemExit(f"expected one ModCtx anchor, found {text.count(marker)}")
    text = text.replace(marker, module_stack + marker, 1)
else:
    # Keep the generated Aura checkout upgradeable while updating this injected block.
    old_globals = (
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_START: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_TOP: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_RESET: Option<unsafe extern "C" fn(*mut u8)> = None;\n\n'
    )
    new_globals = (
        old_globals +
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_RESET_BUF: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK: [u8; 1152] = [0; 1152];\n\n'
    )
    if old_globals in text and 'static mut MOD_STACK_RESET_BUF' not in text:
        text = text.replace(old_globals, new_globals, 1)
    stack_globals = (
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK_RESET_BUF: usize = 0;\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'static mut MOD_STACK: [u8; 1152] = [0; 1152];\n\n'
    )
    first = text.find(stack_globals)
    if first >= 0:
        tail = text[first + len(stack_globals):].replace(stack_globals, '')
        text = text[:first + len(stack_globals)] + tail
    old_setup = (
        '    let start = buf as usize;\n'
        '    let top = start.saturating_add(bytes) & !7usize;\n'
        '    unsafe {\n'
        '        MOD_STACK_START = start;\n'
        '        MOD_STACK_TOP = top;\n'
        '        MOD_STACK_RESET = Some(reset);\n'
        '    }\n'
    )
    new_setup = (
        '    let _ = bytes; // the page buffer is restored after module return, not used as stack\n'
        '    let start = core::ptr::addr_of_mut!(MOD_STACK) as *mut u8 as usize;\n'
        '    let top = start.saturating_add(1152) & !7usize;\n'
        '    unsafe {\n'
        '        MOD_STACK_START = start;\n'
        '        MOD_STACK_TOP = top;\n'
        '        MOD_STACK_RESET = Some(reset);\n'
        '        MOD_STACK_RESET_BUF = buf as usize;\n'
        '    }\n'
    )
    if old_setup in text:
        text = text.replace(old_setup, new_setup, 1)

if 'static mut PENDING_LIB_SLOT' not in text:
    marker = '// ---- the coded 4FSK receiver (PHY G) ----'
    declarations = (
        '#[cfg(feature = "spilib")]\n'
        'static mut PENDING_LIB_SLOT: u8 = 255;\n\n'
        '#[cfg(feature = "spilib")]\n'
        'static mut PENDING_MENU_OPEN: bool = false;\n\n'
    )
    if text.count(marker) != 1:
        raise SystemExit(f"expected one declaration marker, found {text.count(marker)}")
    text = text.replace(marker, declarations + marker, 1)

# Normalize the injected guards/dispatch block on repeated builds. The checked-out Aura tree is
# intentionally persistent, so replacing only anchors above would otherwise accumulate wrappers.
guard_start = text.find('    #[cfg(not(feature = "blowfang-host"))]\n    if room < 512 {')
gpio_anchor = '    let gpio = app.radio.fd6818.reg_read(syst, MOD_GPIO);'
gpio_start = text.find(gpio_anchor, guard_start)
if guard_start >= 0 and gpio_start >= 0:
    text = (text[:guard_start] +
            '    #[cfg(not(feature = "blowfang-host"))]\n'
            '    if room < 512 {\n'
            '        rl!("K6 MOD refused: only {} B stack before dispatch", room);\n'
            '        unsafe { ffi::km_reset() };\n'
            '        return;\n'
            '    }\n'
            + text[gpio_start:])
text = text.replace('    rl!("K6 MOD stage gpio-read begin");\n', '')
text = text.replace('    rl!("K6 MOD stage gpio-read done value={:#06x}", gpio);\n', '')
# The compact host stays in Aura Standby and never enters the pager code that normally paints
# the free-stack watermark. Initialize it once at boot so run_module does not treat unpainted
# RAM as a genuine zero-byte stack margin and force a reset on return.
if 'fn prepare_host_stack()' not in text:
    anchor = 'fn free_ram() -> u32 {'
    if text.count(anchor) != 1:
        raise SystemExit(f"expected one free_ram anchor, found {text.count(anchor)}")
    text = text.replace(anchor,
        '#[cfg(feature = "blowfang-host")]\n'
        'pub fn prepare_host_stack() { paint_free_ram(); }\n\n' + anchor, 1)
# Keep module stack storage and its restoration metadata together in one reserved RAM object.
# Separate static mut globals can be coalesced with the large ModCtx by LLVM's data layout.
stack_start = text.find('#[cfg(feature = "blowfang-host")]\nstatic mut MOD_STACK_START: usize = 0;')
if stack_start < 0:
    stack_start = text.find('#[cfg(feature = "blowfang-host")]\nstruct ModuleStack {')
if stack_start < 0:
    stack_start = text.find('#[cfg(feature = "blowfang-host")]\nfn module_stack_top()')
stack_end = text.find('struct ModCtx {', stack_start)
if stack_start >= 0 and stack_end >= 0:
    stack_state = (
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_stack_top() -> *mut u8 { unsafe { core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>().add(1152) } }\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_stack_bytes() -> usize { 1152 }\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'fn module_lcd_stack_top() -> *mut u8 {\n'
        '    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {\n'
        '        unsafe { core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>().add(1152) }\n'
        '    } else { arena::end() as *mut u8 }\n'
        '}\n'
        '#[cfg(feature = "blowfang-host")]\n'
        'unsafe fn restore_module_page_buffer() {\n'
        '    crate::restore_module_page_buffer(core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>());\n'
        '}\n\n'
    )
    text = text[:stack_start] + stack_state + text[stack_end:]
    first_stack_state = text.find(stack_state)
    if first_stack_state >= 0:
        tail = text[first_stack_state + len(stack_state):].replace(stack_state, '')
        text = text[:first_stack_state + len(stack_state)] + tail
text = text.replace(
    '    unsafe { if let Some(reset) = MOD_STACK_RESET { reset(MOD_STACK_RESET_BUF as *mut u8); } }',
    '    #[cfg(feature = "blowfang-host")]\n    unsafe { restore_module_page_buffer(); }',
)
text = text.replace('''        arena::end()
    }
}

unsafe extern "C" fn mod_key_down()''', '''        arena::end().saturating_sub(1024) // reserve isolated LCD callback stack
    }
}

unsafe extern "C" fn mod_key_down()''')
run_module_start = text.find('fn run_module(')
dispatch_start = text.find('    mod_screen_clear();\n', run_module_start)
dispatch_end = text.find('    unsafe { mod_tx_off() };', dispatch_start)
if dispatch_start >= 0 and dispatch_end >= 0:
    text = (text[:dispatch_start] +
            '    mod_screen_clear();\n'
            '    #[cfg(feature = "blowfang-host")]\n'
            '    paint_free_ram(); // refresh the MSP watermark immediately before switching stacks\n'
            '    #[cfg(feature = "blowfang-host")]\n'
            '    let ret = unsafe { ffi::km_run_on_stack(arena::base(), &MOD_API, module_stack_top()) };\n'
            '    #[cfg(not(feature = "blowfang-host"))]\n'
            '    let ret = unsafe { ffi::km_run(arena::base(), &MOD_API) };\n'
            '    #[cfg(feature = "blowfang-host")]\n'
            '    unsafe { restore_module_page_buffer(); }\n'
            + text[dispatch_end:])

pager.write_text(text)

main = pager.parents[1] / "main.rs"
main_text = main.read_text()
restore_anchor = '#[entry]\nfn main() -> ! {'
restore_fn = (
    '#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n'
    'pub(crate) static mut MODULE_PAGE_BUFFER_STORAGE: [u32; 288] = [0; 288];\n\n'
    '#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n'
    'pub(crate) unsafe fn restore_module_page_buffer(buf: *mut u8) {\n'
    '    let page = unsafe { &mut *(buf as *mut st7565::GraphicsPageBuffer<128, 8>) };\n'
    '    page.mark_dirty();\n'
    '}\n\n'
)
if 'fn restore_module_page_buffer(' not in main_text:
    if main_text.count(restore_anchor) != 1:
        raise SystemExit(f"expected one main entry anchor, found {main_text.count(restore_anchor)}")
    main_text = main_text.replace(restore_anchor, restore_fn + restore_anchor, 1)
elif 'static mut MODULE_PAGE_BUFFER_STORAGE' not in main_text:
    main_text = main_text.replace(restore_anchor,
        '#[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n'
        'pub(crate) static mut MODULE_PAGE_BUFFER_STORAGE: [u32; 288] = [0; 288];\n\n' + restore_anchor, 1)
if 'pub(crate) static mut MODULE_PAGE_BUFFER_STORAGE:' not in main_text:
    main_text = main_text.replace('static mut MODULE_PAGE_BUFFER_STORAGE:',
                                  'pub(crate) static mut MODULE_PAGE_BUFFER_STORAGE:')
main_text = main_text.replace('unsafe extern "C" fn restore_module_page_buffer(',
                              'pub(crate) unsafe fn restore_module_page_buffer(')

old_page_buffer = ('    #[cfg(not(shared_lcd))]\n'
                   '    let mut page_buffer: st7565::GraphicsPageBuffer<128, 8> = st7565::GraphicsPageBuffer::new();\n'
                   '    #[cfg(not(shared_lcd))]\n'
                   '    let page_buffer = &mut page_buffer;')
host_page_buffer = ('    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n'
                    '    let page_buffer = unsafe { &mut *(core::ptr::addr_of_mut!(MODULE_PAGE_BUFFER_STORAGE) as *mut st7565::GraphicsPageBuffer<128, 8>) };\n'
                    '    #[cfg(all(not(feature = "blowfang-host"), not(shared_lcd)))]\n'
                    '    let mut page_buffer: st7565::GraphicsPageBuffer<128, 8> = st7565::GraphicsPageBuffer::new();\n'
                    '    #[cfg(all(not(feature = "blowfang-host"), not(shared_lcd)))]\n'
                    '    let page_buffer = &mut page_buffer;')
if old_page_buffer in main_text:
    main_text = main_text.replace(old_page_buffer, host_page_buffer, 1)
elif host_page_buffer not in main_text:
    raise SystemExit("could not locate main page-buffer declaration")
main_text = main_text.replace('        core::mem::size_of_val(page_buffer),\n', '        1152,\n')
main_text = main_text.replace(
    '    #[cfg(all(feature = "blowfang-host", not(shared_lcd), not(banded)))]\n'
    '    app::pager::set_module_stack(\n'
    '        page_buffer as *mut _ as *mut u8,\n'
    '        1152,\n'
    '        restore_module_page_buffer,\n'
    '    );\n', '')

anchor = '        app.poll_keys(&mut cp.SYST);'
if anchor not in main_text and '        poll_keys_on_arena(&mut app, &mut cp.SYST);' in main_text:
    anchor = '        poll_keys_on_arena(&mut app, &mut cp.SYST);'
replacement = (
    anchor + '\n'
    '        #[cfg(feature = "blowfang-host")]\n'
    '        app.poll_pager(&mut cp.SYST); // shallow host path services queued modules after key handling'
)
if replacement not in main_text:
    if main_text.count(anchor) != 1:
        raise SystemExit(f"expected one main-loop anchor, found {main_text.count(anchor)}")
    main_text = main_text.replace(anchor, replacement, 1)
prepare_anchor = '    ui::glyph::set_flash(&mut app.storage_mut().norflash, false);'
prepare_call = ('    #[cfg(feature = "blowfang-host")]\n'
                '    app::pager::prepare_host_stack();\n'
                + prepare_anchor)
if prepare_call not in main_text:
    if main_text.count(prepare_anchor) != 1:
        raise SystemExit(f"expected one host stack preparation anchor, found {main_text.count(prepare_anchor)}")
    main_text = main_text.replace(prepare_anchor, prepare_call, 1)
main.write_text(main_text)

app_mod = pager.parents[1] / "app/mod.rs"
app_text = app_mod.read_text()
old = ('    pub fn poll_pager(&mut self, syst: &mut SYST) {\n'
       '        pager::poll(self, syst);\n'
       '    }')
new = ('    pub fn poll_pager(&mut self, syst: &mut SYST) {\n'
       '        #[cfg(feature = "blowfang-host")]\n'
       '        pager::poll_library_queue(self, syst);\n'
       '        #[cfg(not(feature = "blowfang-host"))]\n'
       '        pager::poll(self, syst);\n'
       '    }')
new_sotto = ('    pub fn poll_pager(&mut self, syst: &mut SYST) {\n'
             '        #[cfg(all(feature = "blowfang-host", k6_no_sotto))]\n'
             '        pager::poll_library_queue(self, syst);\n'
             '        #[cfg(any(not(feature = "blowfang-host"), not(k6_no_sotto)))]\n'
             '        pager::poll(self, syst);\n'
             '    }')
if new not in app_text and new_sotto not in app_text:
    if app_text.count(old) != 1:
        raise SystemExit(f"expected one poll_pager wrapper anchor, found {app_text.count(old)}")
    app_mod.write_text(app_text.replace(old, new, 1))
