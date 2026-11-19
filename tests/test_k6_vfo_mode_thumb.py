"""Execute the candidate dispatcher and resident probe as Cortex-M0 machine code."""
import shutil
import struct
import subprocess
from pathlib import Path
import pytest

ROOT=Path(__file__).resolve().parents[1]

def test_thumb_resident_dispatch(tmp_path):
    u=pytest.importorskip('unicorn')
    from unicorn import arm_const as A
    for tool in ('clang','ld.lld','llvm-nm','llvm-objcopy'):
        if not shutil.which(tool): pytest.skip(tool)
    elf=tmp_path/'probe.elf'; binary=tmp_path/'probe.bin'
    subprocess.run(['clang','--target=arm-none-eabi','-mcpu=cortex-m0','-mthumb','-Oz',
                    '-ffreestanding','-fno-unwind-tables','-fno-asynchronous-unwind-tables',
                    '-nostdlib','-fuse-ld=lld','-Wl,-Ttext=0x10000,-e,vm_dispatch',
                    str(ROOT/'c/k6/vfo_mode_probe.c'),'-o',str(elf)],check=True)
    subprocess.run(['llvm-objcopy','-O','binary','--only-section=.text',str(elf),str(binary)],check=True)
    symbols={row.split()[-1]:int(row.split()[0],16) for row in
             subprocess.check_output(['llvm-nm','--defined-only',str(elf)],text=True).splitlines()}
    m=u.Uc(u.UC_ARCH_ARM,u.UC_MODE_THUMB|u.UC_MODE_MCLASS)
    m.mem_map(0x10000,0x10000);m.mem_write(0x10000,binary.read_bytes())
    m.mem_map(0x20000000,0x6000)
    d,s,t=0x20000000,0x20000020,0x20000040
    end=0x1f000
    def call(name,*args):
        for reg,v in zip((A.UC_ARM_REG_R0,A.UC_ARM_REG_R1,A.UC_ARM_REG_R2),args):
            m.reg_write(reg,v)
        m.reg_write(A.UC_ARM_REG_SP,0x20005ff0)
        m.reg_write(A.UC_ARM_REG_LR,end|1)
        m.emu_start(symbols[name]|1,end,count=3000)
        assert m.reg_read(A.UC_ARM_REG_PC)==end
        return m.reg_read(A.UC_ARM_REG_R0)
    def state(addr): return struct.unpack('<4I',m.mem_read(addr,16))
    cb=symbols['vm_probe']|1
    assert call('vm_dispatch',d,cb,s)==0
    assert call('vm_event',d,2,77)==0
    assert state(s)==(1,0,1,77)
    assert call('vm_event',d,3,0)==0
    assert state(s)==(1,1,1,0)
    assert call('vm_dispatch',d,cb,t)==0
    assert state(s)==(1,1,0,0)
    assert state(t)==(0,0,1,0)
    assert call('vm_dispatch',d,0,0)==0
    assert state(t)==(0,0,0,0)
    assert call('vm_event',d,2,88)==0xffffffff
