"""Protocol-neutral, timestamped complex IF sample stream for receiver experiments.

This is a host/simulator prototype, not a claim of on-radio throughput.
Frames are fixed-size binary records with CRC32 and an explicit clock domain.
"""
from __future__ import annotations

import struct
import zlib

MAGIC = b'K6IQ'
VERSION = 1
HEADER = struct.Struct('<4sBBHIII')  # magic, version, flags, count, seq, end_tick, rate_hz
MAX_SAMPLES = 256


def encode_frame(iq: bytes, *, sequence: int, end_tick: int, rate_hz: int,
                 flags: int = 0) -> bytes:
    if len(iq) % 2 or not 0 < len(iq) // 2 <= MAX_SAMPLES:
        raise ValueError('expected 1..256 interleaved int8 IQ pairs')
    if not 0 < rate_hz <= 10_000_000 or not 0 <= flags <= 255:
        raise ValueError('invalid clock or flags')
    header = HEADER.pack(MAGIC, VERSION, flags, len(iq) // 2,
                         sequence & 0xffffffff, end_tick & 0xffffffff, rate_hz)
    body = header + iq
    return body + struct.pack('<I', zlib.crc32(body))


def decode_frame(data: bytes) -> dict:
    if len(data) < HEADER.size + 4:
        raise ValueError('truncated IQ frame')
    magic, version, flags, count, seq, tick, rate = HEADER.unpack_from(data)
    if magic != MAGIC or version != VERSION or not 0 < count <= MAX_SAMPLES:
        raise ValueError('unsupported IQ frame')
    if rate == 0 or len(data) != HEADER.size + 2 * count + 4:
        raise ValueError('invalid IQ payload length or rate')
    if zlib.crc32(data[:-4]) != struct.unpack_from('<I', data, len(data)-4)[0]:
        raise ValueError('IQ CRC mismatch')
    return {'sequence': seq, 'end_tick': tick, 'rate_hz': rate,
            'flags': flags, 'samples': data[HEADER.size:-4]}


def stream_gaps(frames):
    """Return lost frame counts; never silently treat missing data as valid IQ."""
    previous = None
    for frame in frames:
        seq = frame['sequence']
        missing = 0 if previous is None else ((seq - previous - 1) & 0xffffffff)
        if missing > 0x7fffffff:
            raise ValueError('out-of-order IQ sequence')
        yield missing
        previous = seq


def packetize_iq(iq: bytes, rate_hz: int, *, start_tick: int = 0,
                 clock_hz: int = 96_000_000, samples_per_frame: int = 64):
    """Packetize simulated int8 IQ using the MCU's 96 MHz tick timebase.

    This generator is a *transport fixture*. Real on-radio DSP and acquisition
    have not yet been connected to this protocol.
    """
    if len(iq) % 2 or not 0 < samples_per_frame <= MAX_SAMPLES:
        raise ValueError('invalid IQ buffer or frame size')
    if rate_hz <= 0 or clock_hz <= 0:
        raise ValueError('invalid clock')
    for sequence, at in enumerate(range(0, len(iq), 2 * samples_per_frame)):
        chunk = iq[at:at + 2 * samples_per_frame]
        end_sample = at // 2 + len(chunk) // 2 - 1
        tick = start_tick + (end_sample * clock_hz) // rate_hz
        yield encode_frame(chunk, sequence=sequence, end_tick=tick, rate_hz=rate_hz)
