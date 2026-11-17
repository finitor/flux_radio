#!/usr/bin/env python3
"""Make a debounced physical power-off act as a key to cooperative modules."""
from pathlib import Path

source = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src/app/pager.rs"
text = source.read_text()

old_start = text.find("/// The main loop cannot see the physical power switch while a module is running on its")
anchor = "/// 1 while any key is held, in about 5 us: all five keypad rows driven low at once"
if old_start >= 0:
    old_end = text.find(anchor, old_start)
    if old_end < 0:
        raise SystemExit("missing end of previous power-off helper")
    text = text[:old_start] + text[old_end:]

helper = '''/// Modules run synchronously, so the main-loop power handler cannot run until they yield.
/// Treat a switch-off as a stop key; the main loop debounces it and performs normal shutdown.
unsafe fn mod_power_off_requested() -> bool {
    let gpioa = unsafe { &*kd32f328_pac::Gpioa::ptr() };
    crate::board::power_switch_off(gpioa)
}

'''
helper_start = text.find("/// Modules run synchronously, so the main-loop power handler")
if helper_start >= 0:
    helper_end = text.find(anchor, helper_start)
    if helper_end < 0:
        raise SystemExit("missing end of previous power-off helper")
    text = text[:helper_start] + helper + text[helper_end:]
elif anchor in text:
    text = text.replace(anchor, helper + anchor, 1)
else:
    raise SystemExit(f"missing insertion anchor in {source}")

for old, new in (
    ('''unsafe extern "C" fn mod_key_poll() -> i32 {
    unsafe { mod_key_down() }
}''', '''unsafe extern "C" fn mod_key_poll() -> i32 {
    if unsafe { mod_power_off_requested() } { return 1; }
    unsafe { mod_key_down() }
}'''),
    ('''unsafe extern "C" fn mod_key_poll() -> i32 {
    unsafe { mod_power_off_guard() };
    unsafe { mod_key_down() }
}''', '''unsafe extern "C" fn mod_key_poll() -> i32 {
    if unsafe { mod_power_off_requested() } { return 1; }
    unsafe { mod_key_down() }
}'''),
    ('''unsafe extern "C" fn mod_key_poll() -> i32 {
    mod_tx_guard();
    let gb = unsafe { &*kd32f328_pac::Gpiob::ptr() };''', '''unsafe extern "C" fn mod_key_poll() -> i32 {
    if unsafe { mod_power_off_requested() } { return 1; }
    mod_tx_guard();
    let gb = unsafe { &*kd32f328_pac::Gpiob::ptr() };'''),
    ('''unsafe extern "C" fn mod_key_poll() -> i32 {
    unsafe { mod_power_off_guard() };
    mod_tx_guard();
    let gb = unsafe { &*kd32f328_pac::Gpiob::ptr() };''', '''unsafe extern "C" fn mod_key_poll() -> i32 {
    if unsafe { mod_power_off_requested() } { return 1; }
    mod_tx_guard();
    let gb = unsafe { &*kd32f328_pac::Gpiob::ptr() };'''),
):
    text = text.replace(old, new, 1)

text = text.replace('''unsafe extern "C" fn mod_delay_us(mut us: u32) {
    let (_, syst) = unsafe { mod_ctx() };
    while us > 0 {
        let n = us.min(100_000);''', '''unsafe extern "C" fn mod_delay_us(mut us: u32) {
    let (_, syst) = unsafe { mod_ctx() };
    while us > 0 {
        if unsafe { mod_power_off_requested() } { return; }
        let n = us.min(100_000);''', 1)

# Most modules use the original key_down callback rather than the newer key_poll.
old_key_down = '''unsafe extern "C" fn mod_key_down() -> i32 {
    mod_tx_guard();'''
new_key_down = '''unsafe extern "C" fn mod_key_down() -> i32 {
    if unsafe { mod_power_off_requested() } { return 1; }
    mod_tx_guard();'''
if new_key_down not in text:
    if text.count(old_key_down) != 1:
        raise SystemExit("missing module key_down callback")
    text = text.replace(old_key_down, new_key_down, 1)

# Shutdown is reported as a held key to modules, but the host must not
# wait for that "key" to be released before its main loop can power off.
old_release = "    while unsafe { mod_key_poll() } != 0 && uptime::now().wrapping_sub(t1) < 30_000 {}"
new_release = """    while !unsafe { mod_power_off_requested() }
        && unsafe { mod_key_poll() } != 0
        && uptime::now().wrapping_sub(t1) < 30_000
    {}"""
if new_release not in text:
    if text.count(old_release) != 1:
        raise SystemExit("missing module key-release wait")
    text = text.replace(old_release, new_release, 1)

if "mod_power_off_requested() } { return 1;" not in text:
    raise SystemExit("did not update mod_key_poll")
source.write_text(text)
