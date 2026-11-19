"""Native APRS parser, TX encoding and real module RAM accounting."""
import ctypes as C
import shutil
import subprocess
from pathlib import Path
import pytest
from modem import aprs,k6mod

ROOT=Path(__file__).resolve().parents[1]
MOD=ROOT/"c/k6/mod"
class Packet(C.Structure):
    _fields_=[("src",C.c_char*10),("dst",C.c_char*10),("to",C.c_char*10),
              ("text",C.c_char*57),("pos",C.c_char*20),
              ("kind",C.c_uint8),("hops",C.c_uint8),("path",C.c_uint8),
              ("symbol",C.c_uint8),("table",C.c_uint8),("length",C.c_uint16)]
@pytest.fixture(scope="module")
def lib(tmp_path_factory):
    if not shutil.which("cc"):pytest.skip("needs cc")
    d=tmp_path_factory.mktemp("aprs")
    src=d/"test.c"
    src.write_text("""
#include "aprs_packet.h"
#include "aprs_tx.h"
#include "aprs_kiss.h"
static uint8_t *kiss_out;static unsigned kiss_len;
static int kiss_write(const uint8_t *p,uint16_t n){unsigned i;for(i=0;i<n;i++)kiss_out[kiss_len++]=p[i];return 0;}
int kiss_encode(uint8_t *o,const uint8_t *p,unsigned n){kiss_out=o;kiss_len=0;return ap_kiss_send(kiss_write,p,n)?-1:(int)kiss_len;}
int parse(ap_packet_t *p,const uint8_t *f,unsigned n){return ap_parse(p,f,n);}
int encode(uint8_t *out,const uint8_t *f,unsigned n){
 ap_tx_t t;int bits=ap_tx_encode(&t,f,n);unsigned i;
 for(i=0;i<(unsigned)(bits+7)/8;i++)out[i]=t.data[i];return bits;
}
static uint32_t divide(uint32_t n,uint32_t d){return n/d;}
void coord(uint8_t *out,int32_t v,int lon){ap_tx_coord(out,v,lon,divide);}
""")
    so=d/"test.so"
    subprocess.run(["cc","-shared","-fPIC","-O2","-I"+str(MOD),str(src),"-o",str(so)],check=True)
    l=C.CDLL(str(so));l.parse.argtypes=[C.POINTER(Packet),C.c_char_p,C.c_uint]
    l.encode.argtypes=[C.c_void_p,C.c_char_p,C.c_uint]
    l.coord.argtypes=[C.c_void_p,C.c_int32,C.c_int]
    l.kiss_encode.argtypes=[C.c_void_p,C.c_char_p,C.c_uint]
    return l
def parse(lib,info,path=(),repeated=0):
    raw=aprs.frame("N0CALL-7","APRS",info,path=path,repeated=repeated)
    p=Packet()
    assert lib.parse(C.byref(p),raw[:-2],len(raw)-2)
    return p
def test_position_and_path(lib):
    p=parse(lib,"!4857.00N/12229.00W>hello",("WIDE1-1",),1)
    assert (p.src,p.dst,p.pos,p.text,p.kind,p.hops,p.path,p.symbol)==(b"N0CALL-7",b"APRS",b"4857.00N 12229.00W",b"hello",1,1,1,ord(">"))
def test_messages_and_status(lib):
    p=parse(lib,":N0CALL-2 :hello{123")
    assert (p.to,p.text,p.kind)==(b"N0CALL-2",b"hello{123",2)
    assert parse(lib,">status").kind==3
    assert parse(lib,"!4857.00N/12229.00W_hello").kind==4
    assert parse(lib,"T#123,1,2,3,4,5,00000000").kind==6
def test_malformed_bounds(lib):
    raw=bytearray(aprs.frame("N0CALL","APRS",">hi")[:-2])
    for n in range(17):
        assert not lib.parse(C.byref(Packet()),bytes(raw[:n]),n)
    raw[6]|=1
    assert not lib.parse(C.byref(Packet()),bytes(raw),len(raw))
    assert not parse(lib,"!9957.00N/12229.00W>bad").pos
def test_tx_wire_roundtrip(lib):
    f=aprs.frame("N0CALL-7","APRS","!4857.00N/12229.00W>hello",path=("WIDE1-1","WIDE2-1"))
    raw=f[:-2]
    out=(C.c_uint8*128)()
    n=lib.encode(out,raw,len(raw))
    assert 0<n<=1024
    levels=[(out[i//8]>>(7-i%8))&1 for i in range(n)]
    bits=[int(a==b) for a,b in zip([0]+levels,levels)]
    strings="".join(map(str,bits))
    assert strings.startswith("01111110"*32) and strings.endswith("01111110"*3)
    stuffed=strings[256:-24]
    # De-stuff independently of the module, and recover all bytes including FCS.
    data=[];ones=0
    for bit in stuffed:
        if ones==5:
            assert bit=="0";ones=0;continue
        data.append(int(bit));ones=ones+1 if bit=="1" else 0
    decoded=bytes(sum(data[i+j]<<j for j in range(8)) for i in range(0,len(data),8))
    assert decoded==f
    assert not lib.encode(out,b"\xff"*76,76)
def test_coordinates(lib):
    p=C.create_string_buffer(10)
    lib.coord(p,4560000,0)
    assert p.raw[:8]==b"4536.00N"
    lib.coord(p,-12237000,1)
    assert p.raw[:9]==b"12222.20W"
    lib.coord(p,8999999,0)
    assert p.raw[:8]==b"9000.00N"
@pytest.mark.skipif(not shutil.which("clang") or not shutil.which("ld.lld"),reason="needs ARM toolchain")
def test_app_fits_existing_arena(tmp_path):
    code,entry=k6mod.build(str(MOD/"aprsapp.c"))
    c=tmp_path/"size.c";o=tmp_path/"size.o"
    c.write_text('#define APRS_HOST\n#include "'+str(MOD/"aprsapp.c")+'"\nchar state[sizeof(st_t)];\n')
    subprocess.run(["clang","--target=arm-none-eabi","-mcpu=cortex-m0","-mthumb","-c",str(c),"-o",str(o)],check=True)
    sym=next(line for line in subprocess.check_output(["nm","-S",str(o)],text=True).splitlines() if line.endswith(" state"))
    size=int(sym.split()[1],16)
    assert entry==16
    assert size+((len(code)+3)&~3)+1040+24<=11776
    assert k6mod.source_level(str(MOD/"aprsapp.c"))==6
    code,_=k6mod.build(str(MOD/"aprsbeacon.c"))
    assert len(code)<5000


@pytest.mark.skipif(not shutil.which("clang") or not shutil.which("ld.lld"),reason="needs ARM toolchain")
def test_native_app_decodes_model(tmp_path):
    pytest.importorskip("unicorn")
    import k6_live_emu as le
    from test_k6_aprsclk import scene, FDMA
    src=tmp_path/"receiver.c"
    src.write_text('#define RUN_MS 2500u\n#define UI_HOLD_MS 0u\n#include "'+str(MOD/"aprsapp.c")+'"\n')
    # Screen callbacks are tested with the emulator, but no keypad is held.
    code,entry=k6mod.build(str(src))
    production,_=k6mod.build(str(MOD/"aprsapp.c"))
    scratch=11776-1040-24-((len(production)+3)&~3)
    # Model the physical capture IF and measured clock offset.
    e=le.Emu(code,entry,scene(total=6.5,fif=8463.542,f_off=-80)[:int(2*FDMA)],
             0,FDMA,1.5,max_s=4,level=8,scratch=scratch)
    e.fd_regs.update({0x73:0x4681,0x43:0x3028})
    result=e.run()
    assert result is not None,e.said
    assert any("f VE7ABC-9" in line for line in e.said),e.said
    assert result[1]<1152
    assert not e.clock_sets


def test_kiss_escaping(lib):
    raw=bytes([0xc0,0xdb])*165
    out=(C.c_uint8*700)()
    n=lib.kiss_encode(out,raw,len(raw))
    assert bytes(out[:n])==b"\xc0\x00"+b"\xdb\xdc\xdb\xdd"*165+b"\xc0"
    assert lib.kiss_encode(out,b"bad",3)==-1
