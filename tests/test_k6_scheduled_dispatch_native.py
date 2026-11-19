"""Differential tests: real C scheduler versus the Python reference."""
import ctypes as C
import random
import subprocess
from pathlib import Path
import pytest
from sim.k6emu.scheduled_jobs import ScheduledJob

class Job(C.Structure):
    _fields_=[('interval',C.c_uint32),('grace',C.c_uint32),
              ('deadline',C.c_uint32),('enabled',C.c_uint8)]

@pytest.fixture
def native(tmp_path):
    root=Path(__file__).resolve().parents[1]
    so=tmp_path/'sched.so'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-shared','-fPIC',
                    str(root/'c/k6/scheduled_dispatch.c'),'-o',str(so)],check=True)
    lib=C.CDLL(str(so))
    lib.sd_enable.argtypes=[C.POINTER(Job),C.c_uint32,C.c_uint32,C.c_uint32]
    lib.sd_cancel.argtypes=[C.POINTER(Job)]
    lib.sd_poll.argtypes=[C.POINTER(Job),C.c_uint32,C.c_int,C.c_int]
    return lib

def test_native_policy(native):
    rng=random.Random(41)
    for initial in (0,0xffffffc0,0x7fffffff):
        for interval,grace in ((100,20),(1,0),(5000,1000),(0x7fffffff,10)):
            ref=ScheduledJob(interval,grace)
            job=Job()
            now=initial
            assert native.sd_poll(C.byref(job),now,1,1)==0
            assert native.sd_enable(C.byref(job),now,interval,grace)==0
            ref.enable(now)
            for _ in range(500):
                now=(now+rng.randrange(0,min(0x7fffffff,interval*3)+1))&0xffffffff
                idle,arena=rng.choice([0,1]),rng.choice([0,1])
                expected=ref.poll(now,rf_idle=idle,arena_available=arena)
                assert native.sd_poll(C.byref(job),now,idle,arena)=={None:0,'dispatch':1,'skip':2}[expected]
                assert job.deadline==ref.deadline
            native.sd_cancel(C.byref(job))
            assert native.sd_poll(C.byref(job),job.deadline,1,1)==0

@pytest.mark.parametrize('interval,grace',[(0,0),(100,100),(2**31,0)])
def test_reject_invalid(native,interval,grace):
    job=Job()
    assert native.sd_enable(C.byref(job),0,interval,grace)==-1
    assert not job.enabled
