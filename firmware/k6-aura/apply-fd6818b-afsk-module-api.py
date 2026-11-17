#!/usr/bin/env python3
"""Append the bounded Bell 202 AFSK TX service to the Aura module ABI."""
from pathlib import Path

pager_path = Path(__file__).resolve().parent / "build/aura-fd6818b-port/src/app/pager.rs"
pager = pager_path.read_text()

# The ABI is append-only; older catalog modules keep using their known prefix.
field = '        pub afsk_tx_send: unsafe extern "C" fn(*const u8, u16) -> i32,\n'
if field not in pager:
    anchor = '        pub card_store: unsafe extern "C" fn(*const u8, u32) -> i32,\n'
    if pager.count(anchor) != 1:
        raise SystemExit("expected one card_store API field")
    pager = pager.replace(anchor, anchor +
        '        // level 13: guarded Bell 202 1200-baud AFSK TX, at rx_hz only.\n' + field, 1)

for old in (
    '    level: if cfg!(all(feature = "fd6818b", feature = "spilib")) { 12 } else if cfg!(feature = "fd6818b") { 11 } else { 9 },\n',
    '    level: if cfg!(feature = "fd6818b") { 11 } else { 9 },\n',
    '    level: if cfg!(feature = "fd6818b") { 12 } else { 9 },\n',
):
    if old in pager:
        pager = pager.replace(old, '    level: if cfg!(feature = "fd6818b") { 13 } else { 9 },\n', 1)
        break

init = '    afsk_tx_send: mod_afsk_tx_send,\n'
if init not in pager:
    anchor = '    card_store: mod_card_store,\n'
    if pager.count(anchor) != 1:
        raise SystemExit("expected one card_store API initializer")
    pager = pager.replace(anchor, anchor + init, 1)

if 'unsafe extern "C" fn mod_afsk_tx_send' not in pager:
    anchor = 'unsafe extern "C" fn mod_delay_us(mut us: u32) {'
    fn = r'''/// Level 13: send one short Bell 202 AFSK bit run, NRZI encoded MSB first.
/// The module must explicitly key through the guarded level-3 API first. The host
/// fixes frequency, baud, tones and power policy at this boundary.
unsafe extern "C" fn mod_afsk_tx_send(bits: *const u8, bit_count: u16) -> i32 {
    if bits.is_null() || bit_count == 0 || bit_count > 1024 {
        return -1;
    }
    mod_tx_guard();
    let c = unsafe { &*addr_of!(MOD_CTX) };
    if c.app.is_null() || !c.tx {
        return -1;
    }
    #[cfg(feature = "fd6818b")]
    {
        let (app, syst) = unsafe { mod_ctx() };
        let bytes = (bit_count as usize + 7) / 8;
        let data = unsafe { core::slice::from_raw_parts(bits, bytes) };
        let mark = (1200u32 * 1_032_444 / 100_000) as u16;
        let space = (2200u32 * 1_032_444 / 100_000) as u16;
        app.radio.transmit_afsk(
            syst, data, bit_count as usize, c.rx_hz, fd6818::Power::Low,
            mark, space, 40, 20,
        );
        mod_tx_guard();
        return 0;
    }
    #[cfg(not(feature = "fd6818b"))]
    -1
}

'''
    if pager.count(anchor) != 1:
        raise SystemExit("expected one module delay function insertion point")
    pager = pager.replace(anchor, fn + anchor, 1)

# The lean host image ships the guarded TX API and independent TX watchdog.
pager = pager.replace(
    '#[cfg(feature = \"lean\")]\nunsafe extern \"C\" fn mod_tx_on(_max_ms: u32) -> i32 {',
    '#[cfg(all(feature = \"lean\", not(feature = \"blowfang-host\")))]\nunsafe extern \"C\" fn mod_tx_on(_max_ms: u32) -> i32 {', 1)
pager = pager.replace(
    '#[cfg(not(feature = \"lean\"))]\nunsafe extern \"C\" fn mod_tx_on(max_ms: u32) -> i32 {',
    '#[cfg(any(not(feature = \"lean\"), feature = \"blowfang-host\"))]\nunsafe extern \"C\" fn mod_tx_on(max_ms: u32) -> i32 {', 1)
old_tune = '''unsafe extern "C" fn mod_tune(hz: u32, wide: i32) {
    let (app, syst) = unsafe { mod_ctx() };
    app.radio.retune_rx(syst, hz, wide != 0);
}'''
new_tune = '''unsafe extern "C" fn mod_tune(hz: u32, wide: i32) {
    let (app, syst) = unsafe { mod_ctx() };
    app.radio.retune_rx(syst, hz, wide != 0);
    unsafe { (*addr_of_mut!(MOD_CTX)).rx_hz = hz; }
}'''
if new_tune not in pager:
    if pager.count(old_tune) != 1:
        raise SystemExit("expected one module tune callback")
    pager = pager.replace(old_tune, new_tune, 1)
pager_path.write_text(pager)
