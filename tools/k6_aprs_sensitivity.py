#!/usr/bin/env python3
"""Compare existing discriminator and matched filter at the B-chip IF.
Model results only; does not calibrate radio sensitivity in dBm.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import numpy as np
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from modem import aprs
from sim.k6if import frontend as fe, study as st

def receiver(directory, disc):
    so=directory/('disc.so' if disc else 'mf.so')
    subprocess.run(['cc','-O2','-shared','-fPIC','-DFIF_CHZ=846354',
                    *(['-DAPRS_DISC'] if disc else []),
                    str(ROOT/'c/k6/aprsclk_host.c'),'-o',str(so)],check=True)
    l=C.CDLL(str(so))
    l.aprs_counts.argtypes=[C.c_void_p,C.c_int,C.c_uint32]
    l.aprs_result.argtypes=[C.POINTER(C.c_int32)]
    return l

def run(l,counts,cps8):
    l.aprs_reset(cps8)
    l.aprs_counts(counts.ctypes.data,len(counts),0)
    r=(C.c_int32*9)()
    l.aprs_result(r)
    return int(r[3])

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--packets',type=int,default=6)
    p.add_argument('--cn0',type=float,nargs='+',default=[48,52,56])
    p.add_argument('--seed',type=int,default=11)
    a=p.parse_args()
    if a.packets<1: p.error('packets must be positive')
    fdma=5493000
    cps8=round(96e6*256/fdma)
    rng=np.random.default_rng(a.seed)
    parts=[]
    for k in range(a.packets):
        f=aprs.frame('N0CALL-'+str(k%16),'APRS','>test '+str(k)+'x'*int(rng.integers(5,25)))
        audio,_=aprs.packet_audio([f],fs=st.FSA,pre_flags=24)
        parts.extend([np.zeros(int(st.FSA*.2)), audio])
    parts.append(np.zeros(int(st.FSA*.2)))
    sig=st.fm(np.concatenate(parts)*3000,0)
    with tempfile.TemporaryDirectory() as d:
        d=Path(d)
        disc,mf=receiver(d,True),receiver(d,False)
        for cn0 in a.cn0:
            samples=fe.receive(sig,st.FZ,cn0,bw=8000,seed=a.seed,L=64,fdma=fdma,fif=8463.54)
            counts=np.ascontiguousarray(samples.astype(np.int8))
            print(json.dumps(dict(cn0=cn0,sent=a.packets,discriminator=run(disc,counts,cps8),matched=run(mf,counts,cps8))),flush=True)
if __name__=='__main__': main()
