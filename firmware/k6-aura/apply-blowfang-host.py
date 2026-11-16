#!/usr/bin/env python3
"""Wire the sideloaded module picker into Aura's normal launcher for host builds."""
from pathlib import Path

root = Path(__file__).parent / "build/aura-fd6818b-port/src"

def edit(rel: str, edits: list[tuple[str, str]]) -> None:
    path = root / rel
    text = path.read_text()
    for old, new in edits:
        if new in text:
            continue
        count = text.count(old)
        if count != 1:
            raise SystemExit(f"{rel}: expected one anchor ({count}): {old[:100]!r}")
        text = text.replace(old, new, 1)
    path.write_text(text)


edit("app/launcher.rs", [
    ("    Pager,\n}", "    #[cfg(not(feature = \"blowfang-host\"))]\n    Pager,\n    #[cfg(feature = \"blowfang-host\")]\n    Blowfang,\n}"),
    ("    LauncherEntry::Pager,\n];", "    #[cfg(not(feature = \"blowfang-host\"))]\n    LauncherEntry::Pager,\n    #[cfg(feature = \"blowfang-host\")]\n    LauncherEntry::Blowfang,\n];"),
    ("            LauncherEntry::Pager => \"VOICE MSG\",", "            #[cfg(not(feature = \"blowfang-host\"))]\n            LauncherEntry::Pager => \"VOICE MSG\",\n            #[cfg(feature = \"blowfang-host\")]\n            LauncherEntry::Blowfang => \"BLOWFANG\","),
    ("            LauncherEntry::Pager => true,", "            #[cfg(not(feature = \"blowfang-host\"))]\n            LauncherEntry::Pager => true,\n            #[cfg(feature = \"blowfang-host\")]\n            LauncherEntry::Blowfang => true,"),
    ("            LauncherEntry::Pager => Mode::Pager,", "            #[cfg(not(feature = \"blowfang-host\"))]\n            LauncherEntry::Pager => Mode::Pager,\n            #[cfg(feature = \"blowfang-host\")]\n            LauncherEntry::Blowfang => Mode::Pager,"),
])

launcher_path = root / "app/launcher.rs"
launcher_text = launcher_path.read_text()
items = '''pub const LAUNCHER_ITEMS: &[LauncherEntry] = &[
    LauncherEntry::Settings,
    LauncherEntry::ChannelMgr,
    LauncherEntry::Contacts,
    LauncherEntry::FmRadio,
    LauncherEntry::ScanQt,
    LauncherEntry::Search,
    LauncherEntry::Spectrum,
    LauncherEntry::Satellite,
    LauncherEntry::Sstv,
    #[cfg(not(feature = "blowfang-host"))]
    LauncherEntry::Pager,
    #[cfg(feature = "blowfang-host")]
    LauncherEntry::Blowfang,
];'''
host_items = '''#[cfg(feature = "blowfang-host")]
pub const LAUNCHER_ITEMS: &[LauncherEntry] = &[
    LauncherEntry::Settings,
    LauncherEntry::ChannelMgr,
    LauncherEntry::Blowfang,
];

#[cfg(not(feature = "blowfang-host"))]
pub const LAUNCHER_ITEMS: &[LauncherEntry] = &[
    LauncherEntry::Settings, LauncherEntry::ChannelMgr, LauncherEntry::Contacts,
    LauncherEntry::FmRadio, LauncherEntry::ScanQt, LauncherEntry::Search,
    LauncherEntry::Spectrum, LauncherEntry::Satellite, LauncherEntry::Sstv,
    LauncherEntry::Pager,
];'''
if host_items not in launcher_text:
    if launcher_text.count(items) == 1:
        launcher_path.write_text(launcher_text.replace(items, host_items, 1))
    elif '#[cfg(feature = "blowfang-host")]\npub const LAUNCHER_ITEMS:' not in launcher_text:
        raise SystemExit("launcher.rs: cannot find launcher item array")

edit("app/keys.rs", [
    ("                        LauncherEntry::Pager => pager::enter(app, syst),",
     "                        #[cfg(not(feature = \"blowfang-host\"))]\n"
     "                        LauncherEntry::Pager => pager::enter(app, syst),\n"
     "                        #[cfg(feature = \"blowfang-host\")]\n"
     "                        LauncherEntry::Blowfang => pager::host_enter(app),"),
])
keys_path = root / "app/keys.rs"
keys_text = keys_path.read_text()
for mode in ("Contacts", "Fm", "Scan", "Search", "ScanQt", "Spectrum", "Satellite | Mode::SatelliteTracking", "Sstv"):
    old = f"        Mode::{mode} =>"
    if old in keys_text:
        keys_text = keys_text.replace(old, f"        #[cfg(not(feature = \"blowfang-host\"))]\n{old}", 1)
if "        #[cfg(feature = \"blowfang-host\")]\n        _ => {}" not in keys_text:
    anchor = "        Mode::Pager => pager::dispatch(app, syst, ev),\n    }"
    if keys_text.count(anchor) != 1:
        raise SystemExit("keys.rs: cannot locate top-level mode dispatch")
    keys_text = keys_text.replace(anchor, "        Mode::Pager => pager::dispatch(app, syst, ev),\n"
                                  "        #[cfg(feature = \"blowfang-host\")]\n        _ => {},\n    }", 1)
keys_path.write_text(keys_text)

pager_path = root / "app/pager.rs"
text = pager_path.read_text()
dispatch_anchor = "pub(super) fn dispatch(app: &mut App, syst: &mut SYST, ev: KeyEvent) {\n"
dispatch_prefix = dispatch_anchor + (
    "    #[cfg(feature = \"blowfang-host\")]\n    {\n"
    "        if matches!(ev.key, KeyId::Vm | KeyId::Ab) && matches!(ev.kind, KeyEventKind::Single | KeyEventKind::Long) {\n"
    "            return_to_aura(app, syst);\n            return;\n        }\n"
    "        if ev.key == KeyId::Exit && ev.kind == KeyEventKind::Long { return_to_aura(app, syst); return; }\n"
    "        if menu_key(app, syst, ev) { return; }\n"
    "        return;\n    }\n"
    "    #[cfg(not(feature = \"blowfang-host\"))]\n    {\n"
)
if dispatch_prefix not in text:
    if text.count(dispatch_anchor) != 1:
        raise SystemExit("pager.rs: cannot locate pager dispatcher")
    text = text.replace(dispatch_anchor, dispatch_prefix, 1)
text = text.replace(
    '    if !matches!(ev.key, KeyId::Digit6 | KeyId::Pound) {\n'
    '        report_cfg(app, key_name(ev.key));\n'
    '    }\n}\n\n/// The receive settings changed:',
    '    if !matches!(ev.key, KeyId::Digit6 | KeyId::Pound) {\n'
    '        report_cfg(app, key_name(ev.key));\n'
    '    }\n    }\n}\n\n/// The receive settings changed:',
)
text = text.replace(
    "#[cfg(all(feature = \"explore\", feature = \"spilib\"))]\nconst MENU_CORE: u8 = 2;",
    "#[cfg(all(feature = \"explore\", feature = \"spilib\"))]\nconst MENU_CORE: u8 = 2;\n"
    "#[cfg(all(feature = \"blowfang-host\", not(feature = \"explore\"), feature = \"spilib\"))]\n"
    "const MENU_CORE: u8 = 1;",
)
text = text.replace(
    '#[cfg(all(feature = "explore", feature = "spilib"))]',
    '#[cfg(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]',
)
# The above broad replacement also covers the menu state, row, open, and key functions.
text = text.replace(
    '#[cfg(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]\nconst MENU_CORE: u8 = 2;',
    '#[cfg(all(feature = "spilib", feature = "explore"))]\nconst MENU_CORE: u8 = 2;',
)
text = text.replace(
    "    let core: &[u8] = match i {\n        0 => b\"EXPLORE\",\n        1 => b\"ARENA\",\n        _ => b\"\",\n    };",
    "    #[cfg(feature = \"explore\")]\n"
    "    let core: &[u8] = match i { 0 => b\"EXPLORE\", 1 => b\"ARENA\", _ => b\"\" };\n"
    "    #[cfg(all(feature = \"blowfang-host\", not(feature = \"explore\")))]\n"
    "    let core: &[u8] = if i == 0 { b\"AURA RADIO\" } else { b\"\" };",
)
text = text.replace(
    "    m.sel = if explore::on() { 0 } else { 1 };",
    "    #[cfg(feature = \"explore\")]\n    { m.sel = if explore::on() { 0 } else { 1 }; }\n"
    "    #[cfg(all(feature = \"blowfang-host\", not(feature = \"explore\")))]\n"
    "    { m.sel = 0; }",
)
old_select = '''                match sel {
                    0 => {
                        if !explore::on() {
                            explore::enter(app, syst);
                        }
                    }
                    1 => {
                        if explore::on() {
                            explore::leave(app, syst);
                        }
                    }
                    _ => {
                        rl!("K6 MENU module pre-leave explore={}", explore::on());
                        if explore::on() {
                            explore::leave(app, syst);
                        }
                        rl!("K6 MENU module post-leave");
                        queue_lib_run(m.slots[(sel - MENU_CORE) as usize]);
                    }
                }'''
new_select = '''                #[cfg(feature = "explore")]
                match sel {
                    0 => { if !explore::on() { explore::enter(app, syst); } }
                    1 => { if explore::on() { explore::leave(app, syst); } }
                    _ => {
                        if explore::on() { explore::leave(app, syst); }
                        queue_lib_run(m.slots[(sel - MENU_CORE) as usize]);
                    }
                }
                #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]
                if sel == 0 {
                    return_to_aura(app, syst);
                } else {
                    queue_lib_run(m.slots[(sel - MENU_CORE) as usize]);
                }'''
if new_select not in text:
    if text.count(old_select) != 1:
        raise SystemExit("pager.rs: could not locate menu row dispatch")
    text = text.replace(old_select, new_select, 1)
text = text.replace(
    '            KeyId::Exit if matches!(ev.kind, KeyEventKind::Single) => m.on = false,',
    '            KeyId::Exit if matches!(ev.kind, KeyEventKind::Single) => {\n'
    '                m.on = false;\n'
    '                #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]\n'
    '                return_to_aura(app, syst);\n'
    '            },',
)
text = text.replace(
    "    if explore::on() {\n        explore::touch();\n    } else {\n        explore::voice_key(); // a key in the arena: its quiet minute starts again\n    }",
    "    #[cfg(feature = \"explore\")]\n"
    "    if explore::on() { explore::touch(); } else { explore::voice_key(); }\n"
    "    #[cfg(all(feature = \"blowfang-host\", not(feature = \"explore\")))]\n"
    "    { let _ = app; }",
)
text = text.replace(
    '    #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]\n    explore::voice_key();',
    '    #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]\n    { let _ = app; }',
)
text = text.replace(
    "#[cfg(all(feature = \"explore\", feature = \"spilib\"))]\n    if menu_key(app, syst, ev) {",
    "#[cfg(all(feature = \"spilib\", any(feature = \"explore\", feature = \"blowfang-host\")))]\n"
    "    if menu_key(app, syst, ev) {",
)
text = text.replace(
    "    #[cfg(all(feature = \"explore\", feature = \"spilib\"))]\n    { menu().on = false; }",
    "    #[cfg(all(feature = \"spilib\", any(feature = \"explore\", feature = \"blowfang-host\")))]\n"
    "    { menu().on = false; }",
)
# `arq_owe` is only used for optional over-the-air telemetry. The lean host keeps the caller
# for a shared module runner but must not compile out the helper it references.
text = text.replace(
    "#[cfg(not(feature = \"lean\"))]\nfn arq_owe(",
    "#[cfg(any(not(feature = \"lean\"), feature = \"blowfang-host\"))]\nfn arq_owe(",
)
if "pub(super) fn host_enter(app: &mut App)" not in text:
    anchor = "/// (open, the selected row, rows) for the screen\n"
    addition = '''/// Enter Aura's sideloaded-module picker from the normal launcher.
#[cfg(feature = "blowfang-host")]
pub(super) fn host_enter(app: &mut App) {
    app.mode = Mode::Pager;
    app.input.clear();
    unsafe { core::ptr::write_volatile(core::ptr::addr_of_mut!(PENDING_MENU_OPEN), true) };
    rl!("K6 MENU host");
}

'''
    if text.count(anchor) != 1:
        raise SystemExit("pager.rs: could not locate menu-state anchor")
    text = text.replace(anchor, addition + anchor, 1)
text = text.replace(
    '            KeyId::Exit if matches!(ev.kind, KeyEventKind::Single) => m.on = false,',
    '            KeyId::Exit if matches!(ev.kind, KeyEventKind::Single) => {\n'
    '                m.on = false;\n'
    '                #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]\n'
    '                return_to_aura(app, syst);\n'
    '            },',
)
text = text.replace(
    '        lib_run(app, syst, slot);\n    }\n}',
    '        lib_run(app, syst, slot);\n'
    '        #[cfg(feature = "blowfang-host")]\n        menu_open(app);\n'
    '    }\n}',
)
pager_path.write_text(text)

edit("ui/pager.rs", [
    ('#[cfg(all(feature = "explore", feature = "spilib"))]\npub fn draw_menu',
     '#[cfg(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]\npub fn draw_menu'),
    ('    out!(b, "MODULES {}/{}", sel + 1, rows);',
     '    #[cfg(feature = "explore")]\n    out!(b, "MODULES {}/{}", sel + 1, rows);\n'
     '    #[cfg(all(feature = "blowfang-host", not(feature = "explore")))]\n    out!(b, "BLOWFANG {}/{}", sel + 1, rows);'),
])

edit("ui/mod.rs", [
    ('        #[cfg(all(feature = "explore", feature = "spilib"))]\n        let menu = app::pager::menu_state().0;\n'
     '        #[cfg(not(all(feature = "explore", feature = "spilib")))]\n        let menu = false;',
     '        #[cfg(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]\n'
     '        let menu = app::pager::menu_state().0;\n'
     '        #[cfg(not(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host"))))]\n'
     '        let menu = false;'),
    ('            #[cfg(all(feature = "explore", feature = "spilib"))]\n            if menu {',
     '            #[cfg(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]\n            if menu {'),
    ('    #[cfg(all(not(banded), feature = "explore", feature = "spilib"))]\n    if app::pager::menu_state().0 {',
     '    #[cfg(all(not(banded), feature = "spilib", any(feature = "explore", feature = "blowfang-host")))]\n'
     '    if app::pager::menu_state().0 {'),
    ('        app::Mode::Pager => draw_pager(display.as_draw_target(), &*app),',
     '        app::Mode::Pager => {\n'
     '            #[cfg(feature = "blowfang-host")]\n'
     '            pager::draw_menu(display.as_draw_target());\n'
     '            #[cfg(all(not(feature = "blowfang-host"), feature = "explore", feature = "spilib"))]\n'
     '            if app::pager::menu_state().0 { pager::draw_menu(display.as_draw_target()); }\n'
     '            else { draw_pager(display.as_draw_target(), &*app); }\n'
     '            #[cfg(not(all(feature = "spilib", any(feature = "explore", feature = "blowfang-host"))))]\n'
     '            draw_pager(display.as_draw_target(), &*app);\n'
     '        },'),
])

ui_path = root / "ui/mod.rs"
ui_text = ui_path.read_text()
for mode in ("Contacts", "Fm", "Scan", "Search", "ScanQt", "Spectrum", "Satellite | app::Mode::SatelliteTracking", "Sstv"):
    old = f"        app::Mode::{mode} =>"
    if old in ui_text:
        ui_text = ui_text.replace(old, f"        #[cfg(not(feature = \"blowfang-host\"))]\n{old}", 1)
if "        #[cfg(feature = \"blowfang-host\")]\n        _ => draw_standby(display.as_draw_target(), &*app)," not in ui_text:
    anchor = "        _ => draw_standby(display.as_draw_target(), &*app),\n    }\n    display.flush();"
    if ui_text.count(anchor) != 1:
        raise SystemExit("ui/mod.rs: cannot locate mode draw fallback")
    ui_text = ui_text.replace(anchor, "        #[cfg(feature = \"blowfang-host\")]\n"
                              "        _ => draw_standby(display.as_draw_target(), &*app),\n"
                              "        #[cfg(not(feature = \"blowfang-host\"))]\n"
                              "        _ => draw_standby(display.as_draw_target(), &*app),\n    }\n    display.flush();", 1)
ui_path.write_text(ui_text)

main_path = root / "main.rs"
main_text = main_path.read_text()
voice_start = "        // Voice pager: packets in, then the blocking playback / test TX\n"
voice_end = "        // power sw\n"
if "        #[cfg(not(feature = \"blowfang-host\"))]\n        {\n" + voice_start not in main_text:
    if main_text.count(voice_start) != 1 or main_text.count(voice_end) != 1:
        raise SystemExit("main.rs: cannot locate normal-loop voice pager block")
    start = main_text.index(voice_start)
    end = main_text.index(voice_end, start)
    body = main_text[start:end]
    main_text = main_text[:start] + "        #[cfg(not(feature = \"blowfang-host\"))]\n        {\n" + body + "        }\n\n" + main_text[end:]
main_path.write_text(main_text)

print("Aura launcher now includes the Blowfang host menu")
