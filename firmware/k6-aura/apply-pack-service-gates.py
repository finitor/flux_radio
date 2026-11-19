#!/usr/bin/env python3
"""Gate optional raw FD6818B FSK RX and TX host callbacks without changing K6Api layout."""
import os
from pathlib import Path

pager = Path(__file__).parent / 'build/aura-fd6818b-port/src/app/pager.rs'
text = pager.read_text()
start = 'unsafe extern "C" fn mod_fsk_rx_start() -> i32 {'
ready = 'unsafe extern "C" fn mod_fsk_rx_ready() -> i32 {'
read = 'unsafe extern "C" fn mod_fsk_rx_read(words: *mut u16) -> i32 {'
stop = 'unsafe extern "C" fn mod_fsk_rx_stop() {'
next_fn = 'unsafe extern "C" fn mod_fsk_tx_send(words: *const u16) -> i32 {'
if not all(text.count(anchor) >= 1 for anchor in (start, ready, read, stop, next_fn)):
    raise SystemExit('pager.rs FSK RX anchors changed; refusing to patch')
# Keep the real implementations in the source for alternate builds, but use cfg
# to exclude their bodies from the linked image. Separate stub names avoid ABI drift.
for anchor in (start, ready, read, stop):
    if '#[cfg(not(k6_no_fsk_rx))]\n' + anchor not in text:
        text = text.replace(anchor, '#[cfg(not(k6_no_fsk_rx))]\n' + anchor, 1)
marker = '// K6 pack optional FSK RX callbacks (API layout unchanged).'
if marker not in text:
    idx = text.index(next_fn)
    stubs = '''// K6 pack optional FSK RX callbacks (API layout unchanged).
#[cfg(k6_no_fsk_rx)]
unsafe extern "C" fn mod_fsk_rx_start() -> i32 { -1 }
#[cfg(k6_no_fsk_rx)]
unsafe extern "C" fn mod_fsk_rx_ready() -> i32 { 0 }
#[cfg(k6_no_fsk_rx)]
unsafe extern "C" fn mod_fsk_rx_read(_words: *mut u16) -> i32 { -1 }
#[cfg(k6_no_fsk_rx)]
unsafe extern "C" fn mod_fsk_rx_stop() {}

'''
    text = text[:idx] + stubs + text[idx:]
# Raw fixed-frame TX is only needed by Data (Card Link). Keep the slot and
# return an unavailable error on Base; Bell 202 AFSK TX is a separate service.
tx_guard = '#[cfg(not(k6_no_fsk_rx))]\n' + next_fn
if tx_guard not in text:
    text = text.replace(next_fn, tx_guard, 1)
tx_stub = '#[cfg(k6_no_fsk_rx)]\nunsafe extern "C" fn mod_fsk_tx_send(_words: *const u16) -> i32 { -1 }\n'
if tx_stub not in text:
    text = text.replace(tx_guard, tx_stub + '\n' + tx_guard, 1)
# Card Link's PXK6 append operation belongs to the optional Data service. Keep
# the append-only API field wired in every image, but let Base use an unavailable
# stub so the module-specific flash writer can be dead-stripped from the link.
card_store = '#[cfg(feature = "spilib")]\nunsafe extern "C" fn mod_card_store('
card_store_guard = '#[cfg(all(feature = "spilib", not(k6_no_fsk_rx)))]\nunsafe extern "C" fn mod_card_store('
if card_store_guard not in text:
    if text.count(card_store) != 1:
        raise SystemExit('pager.rs Card Link store callback anchor changed; refusing to patch')
    text = text.replace(card_store, card_store_guard, 1)
card_store_stub = '''#[cfg(all(feature = "spilib", k6_no_fsk_rx))]
unsafe extern "C" fn mod_card_store(_record: *const u8, _n: u32) -> i32 { -1 }

'''
if card_store_stub not in text:
    marker = 'unsafe extern "C" fn mod_delay_us('
    if text.count(marker) != 1:
        raise SystemExit('pager.rs module delay anchor changed; refusing to add Card Link stub')
    text = text.replace(marker, card_store_stub + marker, 1)
pager.write_text(text)

# The cable-side PXK6 list/read/write/erase protocol and its C validator are
# Data-only. Keep the cable framing and module API layout in Base; the matching
# card_store callback remains an unavailable stub there. This lets linker GC
# remove pxk6_store_* and pxk6_card_open from Base while retaining the complete
# cable protocol in Data builds.
cps = Path(__file__).parent / 'build/aura-fd6818b-port/src/cps/mod.rs'
cps_text = cps.read_text()
card_start = '// PXK6 card data uses explicit commands and a reserved non-executable flash region.'
card_helpers_end = '/// One frame to the PC through the report\'s queue'
card_end = 'frame::CMD_READ_FLASH_RAW if (f.addr as u32) < FLASH_CHIP_SIZE / FLASH_RAW_CHUNK => {'
if card_start in cps_text:
    start = cps_text.index(card_start)
    helpers_end = cps_text.index(card_helpers_end, start)
    end = cps_text.index(card_end, start)
    helpers = cps_text[start:helpers_end]
    segment = cps_text[helpers_end:end]
    old_cfg = '#[cfg(feature = "spilib")]'
    data_cfg = '#[cfg(all(feature = "spilib", not(k6_no_fsk_rx)))]'
    helpers = helpers.replace(data_cfg, old_cfg).replace(old_cfg, data_cfg)
    # Normalize the cable-session helpers first, then gate only the card state
    # and match arms; the common CPS transport stays compiled in Base.
    segment = segment.replace(data_cfg, old_cfg)
    setup = old_cfg + '\n    unsafe {\n        CARD_NOR ='
    if setup in segment:
        segment = segment.replace(setup, data_cfg + '\n    unsafe {\n        CARD_NOR =', 1)
    for state in (
        old_cfg + '\n    let (mut card_len, mut card_next, mut card_crc, mut card_active, mut card_commit_done) =',
        old_cfg + '\n    let mut card_commit_reply =',
    ):
        segment = segment.replace(state, state.replace(old_cfg, data_cfg), 1)
    for command in ('LIST', 'READ', 'ERASE', 'BEGIN', 'DATA', 'COMMIT'):
        arm = old_cfg + '\n            CMD_CARD_' + command
        if arm in segment:
            segment = segment.replace(arm, data_cfg + '\n            CMD_CARD_' + command)
    if data_cfg not in helpers or 'CMD_CARD_LIST' not in segment:
        raise SystemExit('CPS PXK6 card protocol cfg anchors changed; refusing to patch')
    cps_text = cps_text[:start] + helpers + segment + cps_text[end:]
else:
    raise SystemExit('CPS PXK6 card protocol anchor changed; refusing to patch')
cps.write_text(cps_text)
print('Applied raw FSK RX/TX service gate; cfg selected by K6_FSK_RX_SERVICE')
