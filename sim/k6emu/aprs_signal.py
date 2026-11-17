"""Deterministic APRS Bell 202 test signals; no decoded-packet injection."""
from __future__ import annotations
import math
import random


def crc16_x25(data: bytes) -> int:
    crc = 0xffff
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ (0x8408 if crc & 1 else 0)
    return crc ^ 0xffff


def address(callsign: str, ssid: int = 0, last: bool = False) -> bytes:
    if not 0 <= ssid <= 15 or not 1 <= len(callsign) <= 6:
        raise ValueError('invalid AX.25 address')
    return bytes([ord(c) << 1 for c in callsign.upper().ljust(6)]) + bytes([0x60 | (ssid << 1) | int(last)])


def ui_frame(source: str, destination: str, info: bytes, source_ssid: int = 0) -> bytes:
    payload = address(destination) + address(source, source_ssid, True) + b'\x03\xf0' + info
    return payload + crc16_x25(payload).to_bytes(2, 'little')


def hdlc_bits(frame: bytes, flags: int = 32) -> list[int]:
    if flags < 1:
        raise ValueError('flags must be positive')
    flag = [0, 1, 1, 1, 1, 1, 1, 0]
    bits = flag * flags
    ones = 0
    for byte in frame:
        for i in range(8):
            bit = (byte >> i) & 1
            bits.append(bit)
            ones = ones + 1 if bit else 0
            if ones == 5:
                bits.append(0)
                ones = 0
    return bits + flag * 3


def afsk(frame: bytes, sample_rate: int = 9600, baud: int = 1200,
         amplitude: float = 0.7, noise: float = 0.0, seed: int = 0,
         gain: float = 1.0, clip: float = 1.0,
         emphasis_db: float = 0.0, frequency_offset: float = 0.0) -> list[float]:
    """NRZI AX.25 AFSK samples, with optional mark/space tilt and impairments.

    emphasis_db is the relative SPACE amplitude in dB vs MARK, not an
    analog pre-emphasis filter model. Samples are normalized [-1,1].
    """
    if sample_rate <= 0 or baud <= 0 or sample_rate % baud:
        raise ValueError('sample rate must be an integer multiple of baud')
    if clip <= 0 or noise < 0:
        raise ValueError('invalid impairment settings')
    rng = random.Random(seed)
    phase = 0.0
    mark = True
    out = []
    space_scale = 10 ** (emphasis_db / 20)
    for bit in hdlc_bits(frame):
        if bit == 0:
            mark = not mark
        frequency = (1200 if mark else 2200) + frequency_offset
        scale = amplitude * gain * (1 if mark else space_scale)
        for _ in range(sample_rate // baud):
            phase += 2 * math.pi * frequency / sample_rate
            sample = scale * math.sin(phase) + rng.gauss(0, noise) if noise else scale * math.sin(phase)
            out.append(max(-clip, min(clip, sample)))
    return out
