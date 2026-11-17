#!/usr/bin/env python3
"""Add a read-only, versioned Blowfang cable capability query to generated Aura CPS."""
import os
from pathlib import Path

path = Path(__file__).parent / 'build/aura-fd6818b-port/src/cps/mod.rs'
text = path.read_text()
marker = '            CMD_CABLE_CAPS if f.addr == 0 && f.len == 0 => {'
anchor = '            CMD_CABLE_INFO => {\n'
if text.count(anchor) != 1:
    raise SystemExit('could not uniquely locate Blowfang cable info dispatcher')
scan = os.environ.get('K6_SCAN_SERVICE', '1')
fsk = os.environ.get('K6_FSK_RX_SERVICE', '1')
if scan not in ('0', '1') or fsk not in ('0', '1'):
    raise SystemExit('capability gates must be 0 or 1')
# Do not claim capabilities just because a source file was present. These are
# declared build gates; a future attested image measurement is still required.
mask = 1 | (2 if scan == '1' else 0) | (4 if fsk == '1' else 0)
insert = f'''            // Read-only capability query: K6CP, format 1, flags, API ceiling, reserved.
            // The 8 trailing bytes are reserved for a future measured build identity.
            CMD_CABLE_CAPS if f.addr == 0 && f.len == 0 => {{
                let d: [u8; 16] = [b'K', b'6', b'C', b'P', 1, {mask}, 22, 0,
                                   0, 0, 0, 0, 0, 0, 0, 0];
                cable_send(CMD_CABLE_CAPS, 0, &d);
            }}
'''
if marker in text:
    start = text.index(marker)
    end = text.index(anchor, start)
    text = text[:start] + insert + text[end:]
else:
    text = text.replace(anchor, insert + anchor, 1)
constant = 'const CMD_CABLE_INFO: u8 = 0x56;'
if text.count(constant) != 1:
    raise SystemExit('could not locate Blowfang cable command definitions')
if 'const CMD_CABLE_CAPS: u8 = 0x49;' not in text:
    text = text.replace(constant, "const CMD_CABLE_CAPS: u8 = 0x49; // 'I' read-only capabilities\n" + constant, 1)
path.write_text(text)
