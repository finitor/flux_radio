#!/usr/bin/env python3
"""Build the experimental RX-metadata resident probe; never installs or flashes."""
import argparse
import struct
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from modem import k6mod


def build_probe(slot=0, key=None, serial=1):
    with tempfile.TemporaryDirectory() as tmp:
        link = Path(tmp) / 'probe.ld'
        link.write_text('''ENTRY(vm_probe)
SECTIONS {
 . = MODULE_BASE;
 .text : { *(.text.vm_probe) *(.text .text.*) *(.rodata .rodata.*) }
 .data : { *(.data .data.* .bss .bss.* COMMON) }
 /DISCARD/ : { *(.ARM.exidx* .ARM.extab* .comment .ARM.attributes) }
}
ASSERT(SIZEOF(.data) == 0, "resident probe cannot have writable statics")
''')
        code, entry = k6mod.build(str(ROOT/'c/k6/vfo_mode_probe.c'),
                                  link=str(link), entry_sym='vm_probe')
    descriptor = b'K6VM' + struct.pack('<BBHHBB8s', 1, 41, 16, 20+entry, 1, 0, b'PROBE')
    envelope = k6mod.image(descriptor+code, 0, serial, key, lib=slot, cards=True)
    body = bytearray(envelope[:-8])
    body[13] = 0x25  # LIB | CARDS (legacy execution barrier) | RESIDENT
    return bytes(body) + k6mod.image_tag(key, body)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--slot', type=int, default=0)
    parser.add_argument('--key', type=Path, help='omit for cable-only CRC envelope')
    args = parser.parse_args()
    key = bytes.fromhex(args.key.read_text().strip()) if args.key else None
    if key is not None and len(key) != 16:
        parser.error('key file must contain 32 hex digits')
    args.out.write_bytes(build_probe(args.slot, key))
