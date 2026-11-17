"""Extract the 8-byte GNU fast linker build ID from an FD6818B raw image.

This is a firmware identifier, not a signature or a measurement from trusted hardware.
"""
import struct

# ELF note header: namesz=4, descsz=8, NT_GNU_BUILD_ID=3, name GNU\\0.
NOTE = struct.pack('<III', 4, 8, 3) + b'GNU\0'


def image_build_id(data):
    data = bytes(data)
    positions = []
    offset = 0
    while (offset := data.find(NOTE, offset)) != -1:
        if offset % 4 == 0 and offset + len(NOTE) + 8 <= len(data):
            positions.append(offset + len(NOTE))
        offset += 1
    if len(positions) != 1:
        raise ValueError('expected exactly one aligned GNU 8-byte build-ID note in image')
    value = data[positions[0]:positions[0] + 8]
    if not any(value):
        raise ValueError('zero firmware build ID')
    return value.hex()
