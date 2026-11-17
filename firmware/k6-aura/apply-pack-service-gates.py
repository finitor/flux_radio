#!/usr/bin/env python3
"""Gate optional FD6818B FSK RX host callbacks without changing K6Api layout."""
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
pager.write_text(text)
print('Applied FSK RX service gate; cfg selected by K6_FSK_RX_SERVICE')
