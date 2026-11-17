#!/usr/bin/env python3
"""Add a read-only, versioned Blowfang cable capability query to generated Aura CPS."""
import os
from pathlib import Path

work = Path(__file__).parent / 'build/aura-fd6818b-port'
build = work / 'build.rs'
build_text = build.read_text()
anchor_build = '    if feat("VOICE_EXPLORE") {\n        File::create(out.join("k6id.x"))'
updated_build = '    if feat("VOICE_EXPLORE") || feat("SPILIB") {\n        File::create(out.join("k6id.x"))'
if updated_build not in build_text:
    if build_text.count(anchor_build) != 1:
        raise SystemExit('could not locate linker build-ID configuration')
    build_text = build_text.replace(anchor_build, updated_build, 1)
    build.write_text(build_text)
path = work / 'src/cps/mod.rs'
text = path.read_text()
marker = '            CMD_CABLE_CAPS if f.addr == 0 && '
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
insert = f'''            // Read-only capability query: K6CP, format 2, flags, API ceiling, reserved.
            // Version 2 includes the embedded linker build ID (not a runtime measurement).
            CMD_CABLE_CAPS if f.addr == 0 && (f.len == 0 || f.len == 16) => {{
                let mut d: [u8; 16] = [b'K', b'6', b'C', b'P', 2, {mask}, 22, 0,
                                   0, 0, 0, 0, 0, 0, 0, 0];
                extern "C" {{
                    static k6_build_id: [u8; 8];
                }}
                d[8..].copy_from_slice(unsafe {{ &*core::ptr::addr_of!(k6_build_id) }});
                if f.len == 0 {{
                    cable_send(CMD_CABLE_CAPS, 0, &d);
                }} else {{
                    extern "C" {{
                        fn km_capability_proof(record: *const u8, nonce: *const u8, tag: *mut u8) -> i32;
                    }}
                    let mut reply = [0u8; 25];
                    reply[..16].copy_from_slice(&d);
                    let result = unsafe {{ km_capability_proof(d.as_ptr(), f.data.as_ptr(), reply[17..].as_mut_ptr()) }};
                    reply[16] = result as u8;
                    cable_send(CMD_CABLE_CAPS, 0, &reply);
                }}
            }}
'''
if marker in text:
    start = text.index(marker)
    previous = text.rfind('            // Read-only capability query:', 0, start)
    if previous >= 0:
        start = previous
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
