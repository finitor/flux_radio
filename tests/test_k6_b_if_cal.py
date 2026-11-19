"""FD6818B calibration candidates: model checks, not hardware proof."""
from test_k6_i2s import ROOT, START, dma_bench, need_clang, run
from pathlib import Path
import pytest


@need_clang
def test_survey_measures_both_if_centers_and_restores_registers(tmp_path):
    src = tmp_path / "survey.c"
    src.write_text('#define SURVEY_BLOCKS 3\n#include "'+str(Path(ROOT)/"c/k6/mod/ifsurveyb.c")+'"\n')
    # The survey measures the real IF, even when it differs from the legacy nominal.
    state = {"wide": False}
    def tune(hz, wide, us):
        state["wide"] = bool(wide)
    def freq(t, regs):
        return 16927 if state["wide"] else 8464
    mmio, rcc, tim, dma, sim = dma_bench(f_if=freq, dev=0.0)
    regs = {**START, 0x73: 0x4682, 0x43: 0x3028, 0x3B: 0x5880, 0x3C: 0x4F88,0x3D:0x2AAB}
    ret, said, after, writes = run(regs, src=str(src), spare=2048, level=4, tune=tune, mmio=mmio)
    assert ret == 0, said
    rows = [dict(w.split("=") for w in line.split()[1:]) for line in said if line.startswith("if w=")]
    assert len(rows)==4, said
    for row in rows:
        assert abs(int(row["if"])-(16927 if row["w"]=="1" else 8464))<50, row
        assert row["lost"]=="0"
    assert after[0x73]==regs[0x73] and after[0x3B]==regs[0x3B]
    assert state["wide"]


@need_clang
@pytest.mark.parametrize("variant,fif,offset", [("aprsifbcal",16927.083,0),("aprsifbcal8",8463.542,-80),("aprsifbdisc",8463.542,-80)])
def test_calibrated_rx_dsp_on_emulated_m0(variant,fif,offset):
    import pytest
    pytest.importorskip("unicorn")
    import k6_live_emu as le
    from modem import k6mod
    from test_k6_aprsclk import scene, FDMA
    src=str(Path(ROOT)/"c/k6/mod"/(variant+".c"))
    code,entry=k6mod.build(src)
    # Same DSP build with a shorter receive window.
    scratch=11776-1040-24-((len(code)+3)&~3)
    assert scratch >= 3000
    code,entry=k6mod.build(src,cflags=[*k6mod.CFLAGS,"-DRUN_MS=6500u"])
    e=le.Emu(code,entry,scene(total=6.5,fif=fif,f_off=offset),0,FDMA,1.5,max_s=8,level=8,scratch=scratch)
    e.fd_regs.update({0x73:0x4682,0x43:0x3028})
    result=e.run()
    assert result is not None,e.said
    assert any("f VE7ABC-9" in line for line in e.said), e.said
    assert any("ok=3 " in line and "lost=0" in line for line in e.said), e.said
    assert e.writes[0x73][-1]==0x4682 and not e.clock_sets
    assert result[1]<1152


@need_clang
def test_explicit_fm_selector_survey_restores_previous_selector(tmp_path):
    src = tmp_path / "survey.c"
    src.write_text('#define SURVEY_BLOCKS 2\n#include "'+str(Path(ROOT)/"c/k6/mod/ifsurveyfm.c")+'"\n')
    state = {"wide": False}
    def tune(hz, wide, us):
        state["wide"] = bool(wide)
    def freq(t, regs):
        return (16927 if state["wide"] else 8464) if regs.get(0x3D) == 0x2AAB else (10500 if state["wide"] else 6000)
    mmio, rcc, tim, dma, sim = dma_bench(f_if=freq, dev=0.0)
    regs = {**START, 0x73: 0x4681, 0x43: 0x3028, 0x3B: 0x5880, 0x3C: 0x4F88, 0x3D: 0}
    ret, said, after, writes = run(regs, src=str(src), spare=2048, level=4, tune=tune, mmio=mmio)
    assert ret == 0, said
    reads=[line for line in said if line.startswith("if 3d=")]
    rows=[dict(w.split("=") for w in line.split()[1:]) for line in said if line.startswith("if w=")]
    assert len(reads)==len(rows)==8, said
    for i,row in enumerate(rows):
        assert ("3d=0000" if i<4 else "3d=2aab") in reads[i]
        expected=(10500 if row["w"]=="1" else 6000) if i<4 else (16927 if row["w"]=="1" else 8464)
        assert abs(int(row["if"])-expected)<50, row
        assert row["lost"]=="0"
    assert after[0x3D]==0 and after[0x73]==regs[0x73] and after[0x3B]==regs[0x3B]


@need_clang
def test_carrier_probe_tracks_tuning_offset_not_selector(tmp_path):
    from test_k6_i2s import rssi_reg
    src=tmp_path/"carrier.c"
    src.write_text('#define CARRIER_BLOCKS 2\n#include "'+str(Path(ROOT)/"c/k6/mod/ifcarrierb.c")+'"\n')
    state={"hz":144_100_000,"wide":False,"signal":False}
    def tune(hz,wide,us):
        state.update(hz=hz,wide=bool(wide))
    def rssi(us):
        state["signal"]=us>1_000_000
        return rssi_reg(-60 if state["signal"] else -100)
    def freq(t,regs):
        return 10000+state["hz"]-144_100_000 if state["signal"] else 9000
    mmio,*_=dma_bench(f_if=freq,dev=0.0)
    regs={**START,0x67:rssi,0x73:0x4681,0x43:0x4048,0x3D:0}
    ret,said,after,writes=run(regs,src=str(src),spare=2048,level=4,rx_hz=144_100_000,tune=tune,mmio=mmio)
    assert ret==0,said
    assert any(line.startswith("if noise d=0 r=-100") for line in said),said
    rows=[dict(w.split("=") for w in line.split()[2:]) for line in said if line.startswith("if sig ")]
    assert [int(row["d"]) for row in rows]==[0,-2000,2000,-4000,4000,0],said
    assert all(abs(int(row["f"])-10000-int(row["d"]))<50 and row["l"]=="0" for row in rows),said
    assert after[0x73]==0x4681 and after[0x3D]==0
    assert not any(reg==0x3D for reg,val in writes)
    assert state["hz"]==144_100_000 and not state["wide"]


def test_b_chip_physical_preamble_discriminator(tmp_path):
    """Replay only the first ~42 ms of the real Nov 17 D74 capture."""
    import ctypes
    import shutil
    import subprocess
    import numpy as np
    if not shutil.which("cc"):
        pytest.skip("needs a C compiler")
    root=Path(ROOT)
    sample=np.fromfile(root/"tests/data/k6/fd6818b-aprs-preamble.s8",dtype=np.int8)
    assert len(sample)==3600
    so=tmp_path/"disc.so"
    subprocess.run(["cc","-O2","-shared","-fPIC","-DAPRS_DISC","-DFIF_CHZ=846354",
                    "-I"+str(root/"c/k6"),str(root/"c/k6/aprsclk_host.c"),"-o",str(so)],check=True)
    lib=ctypes.CDLL(str(so))
    lib.aprs_counts.argtypes=[ctypes.c_void_p,ctypes.c_int,ctypes.c_uint32]
    lib.aprs_reset(round(96e6*256/5493000))
    lib.aprs_counts(sample.ctypes.data,len(sample),0)
    n=ctypes.c_int.in_dll(lib,"aprs_nbits_trace").value
    bits="".join(map(str,(ctypes.c_uint8*65536).in_dll(lib,"aprs_bit_trace")[:n]))
    assert "01111110"*5 in bits,bits
