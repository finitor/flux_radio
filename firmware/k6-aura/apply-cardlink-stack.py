#!/usr/bin/env python3
"""Give CARD LINK a larger private stack from its otherwise spare module arena."""
from pathlib import Path
import re

path = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = path.read_text()

if "    stack_from_arena: bool," not in text:
    text = text.replace("    scratch: usize,\n", "    scratch: usize,\n    stack_from_arena: bool,\n", 1)
if "    stack_from_arena: false," not in text:
    text = text.replace("    scratch: 0,\n", "    scratch: 0,\n    stack_from_arena: false,\n", 1)
text = text.replace("    stack_from_arena: bool,\n    stack_from_arena: bool,\n", "    stack_from_arena: bool,\n")
text = text.replace("    stack_from_arena: false,\n    stack_from_arena: false,\n", "    stack_from_arena: false,\n")

old_start = text.find('#[cfg(feature = "blowfang-host")]\nfn module_stack_top()')
old_end = text.find("struct ModCtx {", old_start)
if old_start < 0 or old_end < 0:
    raise SystemExit("could not locate the module stack block")
new = '''#[cfg(feature = "blowfang-host")]
fn module_stack_top() -> *mut u8 {
    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {
        arena::end() as *mut u8
    } else {
        unsafe { core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>().add(1152) }
    }
}
#[cfg(feature = "blowfang-host")]
fn module_stack_bytes() -> usize { if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } { 2048 } else { 1152 } }

#[cfg(feature = "blowfang-host")]
fn cardlink_module_loaded() -> bool {
    let p = arena::base();
    unsafe {
        *p.add(16) == b'K' && *p.add(17) == b'6' && *p.add(18) == b'N' && *p.add(19) == b'M' &&
        *p.add(20) == b'C' && *p.add(21) == b'A' && *p.add(22) == b'R' && *p.add(23) == b'D' &&
        *p.add(24) == b' ' && *p.add(25) == b'L' && *p.add(26) == b'I' && *p.add(27) == b'N' &&
        *p.add(28) == b'K'
    }
}
#[cfg(feature = "blowfang-host")]
unsafe fn restore_module_page_buffer() {
    crate::restore_module_page_buffer(core::ptr::addr_of_mut!(crate::MODULE_PAGE_BUFFER_STORAGE).cast::<u8>());
}
'''
text = text[:old_start] + new + text[old_end:]

old = '''            scratch,
            tx_until: 0,
'''
new = '''            scratch,
            stack_from_arena: cardlink_module_loaded(),
            tx_until: 0,
'''
if "stack_from_arena: cardlink_module_loaded()" not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one module context initializer, got {text.count(old)}")
    text = text.replace(old, new, 1)
text = re.sub(
    r"(?:            #\[cfg\(feature = \"blowfang-host\"\)\]\n)*"
    r"            stack_from_arena: cardlink_module_loaded\(\),\n"
    r"(?:            #\[cfg\(not\(feature = \"blowfang-host\"\)\)\]\n"
    r"            stack_from_arena: false,\n)*",
    "            #[cfg(feature = \"blowfang-host\")]\n            stack_from_arena: cardlink_module_loaded(),\n"
    "            #[cfg(not(feature = \"blowfang-host\"))]\n            stack_from_arena: false,\n",
    text,
)
session_anchor = "            scratch: arena::end(), // none: the store and the ring are in use\n"
if "scratch: arena::end(), // none: the store and the ring are in use\n            stack_from_arena:" not in text:
    if text.count(session_anchor) != 1:
        raise SystemExit("could not find module-session ModCtx initializer")
    text = text.replace(session_anchor, session_anchor + "            stack_from_arena: false,\n", 1)

old = '''fn scratch_end() -> usize {
    arena::end()
}
'''
new = '''fn scratch_end() -> usize {
    if unsafe { (*addr_of!(MOD_CTX)).stack_from_arena } {
        arena::end().saturating_sub(2048)
    } else {
        arena::end()
    }
}
'''
if "arena::end().saturating_sub(2048)" not in text:
    if text.count(old) != 1:
        raise SystemExit(f"expected one lean scratch_end function, got {text.count(old)}")
    text = text.replace(old, new, 1)

path.write_text(text)

# EXPLORE runs with a module context too, but never borrows the dedicated CARD LINK stack.
explore = path.parent / "pager" / "explore.rs"
if explore.exists():
    source = explore.read_text()
    anchor = "            scratch: arena::end(), // none: EXPLORE has the store and the ring\n"
    if "stack_from_arena: false," not in source:
        if source.count(anchor) != 1:
            raise SystemExit("could not find EXPLORE ModCtx initializer")
        source = source.replace(anchor, anchor + "            stack_from_arena: false,\n", 1)
        explore.write_text(source)
