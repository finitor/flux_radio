"""Portable C IF mixing prototype compared with a known synthetic tone."""
import ctypes
import math
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

class State(ctypes.Structure):
    _fields_ = [('phase',ctypes.c_uint32),('step',ctypes.c_uint32),
                ('i_acc',ctypes.c_int32),('q_acc',ctypes.c_int32),
                ('n',ctypes.c_uint16),('decimation',ctypes.c_uint16)]


def test_fixed_point_mixer_tone_and_output_count():
    with tempfile.TemporaryDirectory() as d:
        so=Path(d)/'if_iq.so'
        subprocess.run(['cc','-O2','-shared','-fPIC','-o',str(so),
                        str(ROOT/'c/k6/if_iq.c')],check=True)
        lib=ctypes.CDLL(str(so))
        lib.k6_if_iq_init.argtypes=[ctypes.POINTER(State),ctypes.c_uint32,ctypes.c_uint16]
        lib.k6_if_iq_push.argtypes=[ctypes.POINTER(State),ctypes.c_int16,
                                    ctypes.POINTER(ctypes.c_int16),ctypes.POINTER(ctypes.c_int16)]
        fs=5710000/64
        fc=26000000/1536
        dec=8
        s=State()
        lib.k6_if_iq_init(ctypes.byref(s),round(fc/fs*2**32),dec)
        out=[]
        for n in range(8000):
            x=round(12*math.cos(2*math.pi*(fc+1200)*n/fs))
            i=ctypes.c_int16();q=ctypes.c_int16()
            if lib.k6_if_iq_push(ctypes.byref(s),x,ctypes.byref(i),ctypes.byref(q)):
                out.append(complex(i.value,q.value))
        assert len(out)==1000
        assert max(abs(x) for x in out)>15
        # Decimation=8 is a preliminary boxcar, NOT a validated anti-alias filter.
        assert s.n==0
