#!/usr/bin/env python3
"""Separate cable ingress from RF; omit RF module dispatch in Base."""
from pathlib import Path
p=Path(__file__).parent/'build/aura-fd6818b-port/src/app/pager.rs'
s=p.read_text()
anchor='        pub fn km_packet(payload: *const u8, len: i32, arena: *mut u8, bytes: u32) -> i32;'
decl=anchor.replace('km_packet(', 'km_cable_packet(')
if decl not in s:
    assert s.count(anchor)==1
    s=s.replace(anchor,anchor+'\n'+decl)
a=s.index('pub(super) fn cable_chunk(')
b=s.index('let r = unsafe {',a)
e=s.index(';',b)
line=s[b:e]
if 'ffi::km_packet(' in line:
    s=s[:b]+line.replace('ffi::km_packet(', 'ffi::km_cable_packet(')+s[e:]
elif 'ffi::km_cable_packet(' not in line and 'ffi::km_packet_on_stack(' not in line:
    raise SystemExit('unknown cable ingress')
anchor='    if let (false, false, Some(syst)) = (app.pager.play_pending, stream_on(), syst) {'
guard='    #[cfg(not(k6_no_ota))]\n'+anchor
if guard not in s:
    assert s.count(anchor)==1
    s=s.replace(anchor,guard)
p.write_text(s)
