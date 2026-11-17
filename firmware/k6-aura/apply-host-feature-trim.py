#!/usr/bin/env python3
"""Keep native Search and gate FM and Explore services on the normal host."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src"


def edit(path, transform):
    source = ROOT / path
    source.write_text(transform(source.read_text()))


def replace(text, old, new):
    if new and new in text:
        return text
    if text.count(old) != 1:
        raise SystemExit(f"Host feature trim: unexpected anchor {old!r}")
    return text.replace(old, new, 1)


def guard(text, line, condition=None):
    """Replace earlier host exclusions, including duplicates in existing worktrees."""
    pattern = r'(?m)^(?:[ \t]*#\[cfg\((?:not\(feature = "blowfang-host"\)|not\(k6_no_scan\))\)\]\n)*' + re.escape(line)
    updated, count = re.subn(pattern, (f"{line[:len(line) - len(line.lstrip())]}#[cfg({condition})]\n" if condition else "") + line, text)
    if count != 1:
        raise SystemExit(f"Host feature trim: unexpected guarded line {line!r}")
    return updated


def module_api(text):
    callbacks = (
        ("ex_init", "_state: Ptr, _entries: Ptr, _cap: u32", "", ""),
        ("ex_view", "_state: Ptr, _index: u32", " -> Ptr", "core::ptr::null_mut()"),
        ("ex_view_n", "_state: *const core::ffi::c_void", " -> u32", "0"),
        ("ex_tone", "_state: Ptr, _hz: u32, _tone: u16", "", ""),
        ("ex_cw", "_state: Ptr, _hz: u32, _call: *const u8", "", ""),
    )
    for name, *_ in callbacks:
        field = f"    explore_{name}: "
        old = field + f"ffi::{name},"
        new = f"    #[cfg(not(k6_no_scan))]\n{old}\n    #[cfg(k6_no_scan)]\n{field}unavailable_explore::{name},"
        text = replace(text, old, new)
    marker = "#[cfg(k6_no_scan)]\nmod unavailable_explore {"
    if marker not in text:
        stubs = [marker, "    type Ptr = *mut core::ffi::c_void;"]
        for name, args, result, body in callbacks:
            stubs.append(f'    pub(super) unsafe extern "C" fn {name}({args}){result} {{ {body} }}')
        stubs += ["}", "", ""]
        anchor = "static MOD_API: ffi::K6Api"
        text = replace(text, anchor, "\n".join(stubs) + anchor)
    for name, args in (
        ("mod_lcd_explore_header", "_band: *const u8, _found: u32, _gaze: i32"),
        ("mod_lcd_explore_frame", "_frame: *const ModExploreFrame"),
    ):
        anchor = f'unsafe extern "C" fn {name}('
        stub = f'#[cfg(k6_no_scan)]\n{anchor}{args}) {{}}\n'
        if stub not in text:
            text = replace(text, anchor, stub + "#[cfg(not(k6_no_scan))]\n" + anchor)
    return text


def keys(text):
    for line in (
        "        Mode::Search => search::dispatch(app, syst, ev),",
        "                        LauncherEntry::Search => search::enter(app, syst),",
    ):
        text = guard(text, line)
    for line in (
        "        Mode::Fm => fm::dispatch(app, syst, ev),",
        "                        LauncherEntry::FmRadio => fm::enter(app, syst),",
        "            if app.mode == Mode::Fm {",
        "    if app.mode == Mode::Fm && matches!(ev.key, KeyId::Side1 | KeyId::Side2 | KeyId::Band) {",
    ):
        text = guard(text, line, "not(k6_no_scan)")
    return text


def launcher(text):
    for indent, suffix in (
        ("    ", "Search,"),
        ("            ", 'LauncherEntry::Search => "FREQ HUNT",'),
        ("            ", "LauncherEntry::Search => true,"),
        ("            ", "LauncherEntry::Search => Mode::Search,"),
    ):
        text = guard(text, indent + suffix)
    for line in (
        "    FmRadio,",
        '            LauncherEntry::FmRadio => "FM RADIO",',
        "            LauncherEntry::FmRadio => true,",
        "            LauncherEntry::FmRadio => Mode::Fm,",
    ):
        text = guard(text, line, "not(k6_no_scan)")
    return replace(text, "    LauncherEntry::Blowfang,\n];\n\n#[cfg(not", "    LauncherEntry::Search,\n    #[cfg(not(k6_no_scan))]\n    LauncherEntry::FmRadio,\n    LauncherEntry::Blowfang,\n];\n\n#[cfg(not")


def key_functions(text):
    text = guard(text, "        5 => KeyFunction::FmRadio,", "not(k6_no_scan)")
    text = guard(text, "        KeyFunction::FmRadio => fm::enter(app, syst),", "not(k6_no_scan)")
    text = replace(text, "        KeyFunction::None | KeyFunction::TxTone => {}", "        KeyFunction::None | KeyFunction::TxTone => {}\n        #[cfg(k6_no_scan)]\n        KeyFunction::FmRadio => {},")
    for line in (
        "    AprsBeacon,",
        '            KeyFunction::AprsBeacon => "APRS TX",',
        "        11 => KeyFunction::AprsBeacon,",
        "        KeyFunction::AprsBeacon => super::aprs_ops::send_beacon(app),",
    ):
        text = text.replace(line + "\n", "", 1)
    return text


def main_loop(text):
    text = guard(text, "        app.poll_search(&mut cp.SYST);")
    text = guard(text, "        app.poll_fm(&mut cp.SYST);", "not(k6_no_scan)")
    return re.sub(r'        // APRS beacon TX: draw overlay before blocking transmission\n        if app\.aprs_beacon_active\(\) \{\n.*?^        \}\n\n', "", text, count=1, flags=re.M | re.S)


def native_storage(text):
    text = replace(text, "let sats = storage.load_satellites();", "let sats = [None; MAX_SATELLITES];")
    text = replace(text, "let has_sstv_image = storage.has_sstv_image();", "let has_sstv_image = false;")
    return text


def cps(text):
    text = re.sub(r'            frame::CMD_SSTV_ERASE => .*?^            frame::CMD_READ_FLASH_RAW', '            frame::CMD_READ_FLASH_RAW', text, count=1, flags=re.M | re.S)
    for fallback in ("None", "false"):
        text = re.sub(r'    \} else if \(SAT_CPS_BASE\.\.SAT_CPS_BASE.*?^    \} else \{\n        '+fallback+r'\n    \};', '    } else {\n        '+fallback+'\n    };', text, count=1, flags=re.M | re.S)
    return text


edit("app/pager.rs", module_api)
edit("ui/pager.rs", lambda s: guard(s, "    if !s.explore.is_null() {", "not(k6_no_scan)"))
edit("app/keys.rs", keys)
edit("app/launcher.rs", launcher)
edit("app/keyfn.rs", key_functions)
edit("ui/mod.rs", lambda s: guard(guard(s, "        app::Mode::Search => draw_search(display.as_draw_target(), &*app),"), "        app::Mode::Fm => draw_fm(display.as_draw_target(), &*app),", "not(k6_no_scan)"))
edit("app/settings_ops.rs", lambda s: replace(
    s, "| SettingItem::BandLong => clamp_step(cur, up, 0, 12),",
    """| SettingItem::BandLong => {
            let next = clamp_step(cur, up, 0, 12);
            if next != 0 && keyfn::from_u8(next as u8) == keyfn::KeyFunction::None {
                clamp_step(next, up, 0, 12)
            } else {
                next
            }
        },""",
))
edit("main.rs", main_loop)
edit("app/mod.rs", native_storage)
edit("cps/mod.rs", cps)
edit("ui/standby.rs", lambda s: replace(s, "    if app.aprs_beacon_active() {\n        draw_aprs_beacon_overlay(lcd);\n    } else if app.tx_prohibited() {", "    if app.tx_prohibited() {"))
