"""Build and native host-contract checks; not RF validation."""
import pathlib
import shutil
import subprocess
import pytest
from modem import k6mod

ROOT = pathlib.Path(__file__).resolve().parents[1]
MOD = ROOT / "c/k6/mod"

@pytest.mark.parametrize("name,title,level", [
    ("rflimits", "RF LIMITS", 4), ("rffskrx", "RF FSK RX", 10),
    ("rffsktx", "RF FSK TX", 15), ("rfbaseb", "RF IF B", 4),
])
def test_bundle(name,title,level):
    if not shutil.which("clang") or not shutil.which("ld.lld"):
        pytest.skip("ARM toolchain required")
    source = str(MOD / (name + ".c"))
    code, entry = k6mod.build(source)
    assert entry == k6mod.bin_entry(code)
    assert k6mod.module_name(code) == title
    assert k6mod.source_level(source) == level
    assert len(code) < 4096

def run_native(tmp_path, body):
    if not shutil.which("cc"):
        pytest.skip("native compiler required")
    src=tmp_path/"test.c"
    src.write_text(body)
    exe=tmp_path/"test"
    subprocess.run(["cc","-I"+str(MOD),str(src),"-o",str(exe)],check=True)
    subprocess.run([str(exe)],check=True)

def test_rx_survey(tmp_path):
    run_native(tmp_path, r'''
#include <assert.h>
#include <string.h>
#include "rflimits.c"
static uint32_t last;
static unsigned tunes, reports;
static uint16_t id=0x4819;
static uint16_t readreg(uint8_t r){return r==0?id:r==0x67?100:r==0x0c?0x200:0;}
static void tune(uint32_t h,int w){last=h;tunes++;}
static void wait(uint32_t us){}
static uint32_t rx(void){return 145000000;}
static int key(void){return 0;}
static void say(const char *s){if(!strncmp(s,"rf hz=",6))reports++;}
int main(void){
 k6_api_t a={.abi=1,.level=4,.fd_read=readreg,.tune=tune,.delay_us=wait,
 .rx_hz=rx,.key_poll=key,.say=say};
 for(int i=0;i<2;i++){
  id=i?0x4829:0x4819;tunes=reports=0;
  assert(k6_main(&a)==0);
  assert(tunes==43&&reports==21&&last==145000000);
 }
 id=0;tunes=0;assert(k6_main(&a)<0&&tunes==0);
 return 0;
}
''')

def test_fsk_frame_and_gates(tmp_path):
    run_native(tmp_path,r'''
#include <assert.h>
#include <string.h>
#include "rffsktx.c"
static uint32_t hz=145500000;
static int tx_calls,rx_calls;
static uint16_t readreg(uint8_t r){return r==0?0x4829:0;}
static uint32_t rx(void){return hz;}
static int settings_read(uint8_t *p,uint16_t n){
 memset(p,0,n);memcpy(p+KM_SETTINGS_APRS_CALLSIGN,"AG7SU",5);return n;
}
static int no_service(void){rx_calls++;return -1;}
static int tx(uint32_t n){tx_calls++;return 0;}
static void say(const char *s){}
int main(void){
 uint16_t w[8];
 assert(frame((const uint8_t*)"AG7SU\0",w));
 assert(w[0]==0x4147&&w[1]==0x3753&&w[2]==0x5520&&w[3]==0x5246);
 assert(w[4]==0x55aa&&w[7]==0x4567);
 assert(!frame((const uint8_t*)"A?7SU\0",w));
 assert(!allowed(915000000)&&!allowed(223500000));
 k6_api_t a={.abi=1,.level=15,.fd_read=readreg,.rx_hz=rx,.say=say,
 .settings_read=settings_read,.fsk_rx_start=no_service,.tx_on=tx};
 assert(k6_main(&a)==-7&&rx_calls==1&&tx_calls==0);
 hz=915000000;assert(k6_main(&a)==-4&&rx_calls==1&&tx_calls==0);
 return 0;
}
''')
