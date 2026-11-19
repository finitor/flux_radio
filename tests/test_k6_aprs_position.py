"""Position-sync wire format, exact source filter and ambiguity rejection."""
import ctypes as C
import shutil
import subprocess
from pathlib import Path
import pytest
from modem import aprs,k6mod
ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/"c/k6/mod"
@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    if not shutil.which("cc"):pytest.skip("cc required")
    d=tmp_path_factory.mktemp("pos");c=d/"pos.c";so=d/"pos.so"
    c.write_text('#include "aprs_position.h"\nstatic uint32_t div32(uint32_t a,uint32_t b){return a/b;}\nint decode(const uint8_t *f,unsigned n,const char *src,int32_t *lat,int32_t *lon){return ap_position(f,n,src,lat,lon,div32);}\n')
    subprocess.run(["cc","-O2","-shared","-fPIC","-I"+str(MOD),str(c),"-o",str(so)],check=True)
    l=C.CDLL(str(so));l.decode.argtypes=[C.c_char_p,C.c_uint,C.c_char_p,C.POINTER(C.c_int32),C.POINTER(C.c_int32)]
    return l
def decode(l,info,src="N0CALL-7",dst="APRS",path=(),repeated=0):
    f=aprs.frame(src,dst,info,path=path,repeated=repeated)[:-2]
    a,b=C.c_int32(),C.c_int32()
    ok=l.decode(f,len(f),b"N0CALL-7",C.byref(a),C.byref(b))
    return (a.value,b.value) if ok else None
def test_plain(lib):
    assert decode(lib,"!4536.00N/12222.20W>hi")== (4560000,-12237000)
    assert decode(lib,"@171234z4536.00S/12222.20E>hi")==(-4560000,12237000)
    assert decode(lib,"!4536.00N/12222.20W>hi",path=("WIDE1-1",))==(4560000,-12237000)
def test_rejection(lib):
    for info in ("!4536.0 N/12222.20W>hi","!9136.00N/12222.20W>hi","!4560.00N/12222.20W>hi","!4536.00N/18122.20W>hi","@999999z4536.00N/12222.20W>hi",">hello","}N0CALL-7>APRS:!4536.00N/12222.20W>hi"):
        assert decode(lib,info) is None,info
    assert decode(lib,"!4536.00N/12222.20W>hi",src="N0CALL-8") is None
    assert decode(lib,"!4536.00N/12222.20W>hi",src="N1CALL-7") is None
    assert decode(lib,"!4536.00N/12222.20W>hi",path=("WIDE1-1",),repeated=1) is None
def b91(v):
    return bytes(33+v//91**i%91 for i in (3,2,1,0))
def test_compressed(lib):
    msg=b"!/"+b91(round((90-45.6)*380926))+b91(round((-122.37+180)*190463))+b">!!!"
    assert decode(lib,msg)==(4560000,-12237000)
def test_mice(lib):
    # Destination encodes 4536.00 N, longitude +100 and west flags.
    # 22 degrees, 22.20 minutes, with +100 degrees offset.
    assert decode(lib,bytes([0x60,50,50,48,28,28,28,ord(">"),ord("/")]),dst="453VPP")== (4560000,-12237000)
@pytest.mark.skipif(not shutil.which("clang") or not shutil.which("ld.lld"),reason="ARM tools")
def test_module_build():
    code,entry=k6mod.build(str(MOD/"aprsgpssync.c"))
    assert entry==16 and len(code)<7600 and k6mod.source_level(str(MOD/"aprsgpssync.c"))==23
