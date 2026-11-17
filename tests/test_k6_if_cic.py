import ctypes
import math
import subprocess
import tempfile
from pathlib import Path
import numpy as np
import pytest

ROOT=Path(__file__).resolve().parents[1]
class State(ctypes.Structure):
    _fields_=[('integ',(ctypes.c_uint32*3)*2),('delay',(ctypes.c_uint32*3)*2),
              ('count',ctypes.c_uint16),('ratio',ctypes.c_uint16),('shift',ctypes.c_uint8)]

@pytest.fixture(scope='module')
def lib():
    with tempfile.TemporaryDirectory() as d:
        so=Path(d)/'cic.so'
        subprocess.run(['cc','-O2','-shared','-fPIC','-o',str(so),str(ROOT/'c/k6/if_cic.c')],check=True)
        l=ctypes.CDLL(str(so))
        l.k6_if_cic_init.argtypes=[ctypes.POINTER(State),ctypes.c_uint16]
        l.k6_if_cic_push.argtypes=[ctypes.POINTER(State),ctypes.c_int16,ctypes.c_int16,
                                  ctypes.POINTER(ctypes.c_int16),ctypes.POINTER(ctypes.c_int16)]
        yield l

def process(lib, data, ratio=8):
    state=State()
    assert lib.k6_if_cic_init(ctypes.byref(state),ratio)
    result=[]
    for v in data:
        i=ctypes.c_int16();q=ctypes.c_int16()
        if lib.k6_if_cic_push(ctypes.byref(state),int(v),0,ctypes.byref(i),ctypes.byref(q)):
            result.append(i.value)
    return np.asarray(result)

def test_dc_and_negative_values(lib):
    for dc in (1000,-1000):
        y=process(lib,[dc]*800)
        assert len(y)==100
        assert np.all(abs(y[10:]-dc)<=1)

def test_alias_rejection_vs_boxcar(lib):
    fs=5710000/64
    t=np.arange(8192)/fs
    near=process(lib,np.rint(1000*np.cos(2*np.pi*1200*t)))
    alias=process(lib,np.rint(1000*np.cos(2*np.pi*(fs/8+1200)*t)))
    near_rms=np.std(near[40:]); alias_rms=np.std(alias[40:])
    assert near_rms>400
    assert alias_rms<near_rms/15

def test_invalid_ratios(lib):
    for ratio in (0,3,33,64):
        assert not lib.k6_if_cic_init(ctypes.byref(State()),ratio)
