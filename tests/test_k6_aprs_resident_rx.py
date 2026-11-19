"""Replay the physical B-chip preamble through the cooperative receive adapter."""
import ctypes as C
from pathlib import Path
import subprocess
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_b_chip_counts_chunked(tmp_path):
    so=tmp_path/'rx.so'
    subprocess.run(['cc','-O2','-shared','-fPIC',str(ROOT/'c/k6/aprs_resident_rx.c'),'-o',str(so)],check=True)
    lib=C.CDLL(str(so))
    lib.arx_state_bytes.restype=C.c_uint
    lib.arx_reset.argtypes=[C.c_void_p,C.c_uint32]
    lib.arx_feed.argtypes=[C.c_void_p,C.c_void_p,C.c_uint]
    for name in ('arx_packets','arx_preambles','arx_history'):
        getattr(lib,name).argtypes=[C.c_void_p]
        getattr(lib,name).restype=C.c_uint
    state=C.create_string_buffer(lib.arx_state_bytes())
    cps8=round(96e6*256/5493000)
    assert lib.arx_reset(state,cps8)==0
    raw=(ROOT/'tests/data/k6/fd6818b-aprs-preamble.s8').read_bytes()
    for i in range(0,len(raw),97):
        chunk=raw[i:i+97]
        assert lib.arx_feed(state,chunk,len(chunk))==0
    assert lib.arx_preambles(state)>0
    assert lib.arx_packets(state)==0
    assert lib.arx_history(state)==0
    assert lib.arx_feed(state,raw,129)==-1
    assert lib.arx_reset(state,cps8)==0
    assert lib.arx_preambles(state)==0
