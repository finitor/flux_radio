/* Characterize GP0 before changing decoder constants. Receive-only on the
   selected VFO. Use a steady, moderately strong unmodulated reference.
   No crystal trim, calibration record, flash or TX writes.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#define GP0_SWEEP 1
#define GP0_NO_MAIN 1
#define GP0_NO_WAIT 1
#define TAG "ifsurvey"
#include "gp0dma.c"
#ifndef SURVEY_NAME
#define SURVEY_NAME "IF SURVEY"
#endif
K6_MODULE_NAME(SURVEY_NAME);
#ifndef SURVEY_BLOCKS
#define SURVEY_BLOCKS 16
#endif
int k6_main(const k6_api_t *api) {
  saved_t sv;
  uint8_t *ring;
  uint16_t afc, bw, ifsel;
  uint32_t hz, i, j, n, sum, lo, hi, lost, bad;
  int ret, mode;
#ifdef SURVEY_COMPARE_IFSEL
  int sel;
#endif
  char line[100], *p;
  blk_t b;
  (void)carrier; (void)sdec;
  if (api->level < 4) return -3;
  hz=api->rx_hz();
  afc=api->fd_read(0x73);bw=api->fd_read(0x43);ifsel=api->fd_read(0x3D);
  ret=setup(api,&sv,&ring);
  if(ret)return ret;
  if((api->fd_read(SEL_REG)&15u)!=CODE){ret=-9;goto out;}
  p=kv(line,"if hz=",hz);
  p=hex(put(p," 3d="),ifsel,4);
  p=hex(put(p," 3b="),api->fd_read(0x3B),4);
  p=hex(put(p," 3c="),api->fd_read(0x3C),4);
  say0(api,line,hex(put(p," 73="),afc,4));
  /* Compare both filters and AFC states without changing RF level or frequency. */
#ifdef SURVEY_COMPARE_IFSEL
  /* First reproduce zero IF selection, then explicitly select FM's 0x2AAB.
     A readback after RX-on detects an unexpected driver rewrite. */
  for(sel=0;sel<2;sel++){
    uint16_t target=sel?0x2AABu:0;
    if(api->fd_write(0x3D,target)!=0){ret=-10;goto out;}
    p=hex(put(line,"if write3d="),target,4);
    p=hex(put(p," immediate="),api->fd_read(0x3D),4);
    api->delay_us(10000);
    say0(api,line,hex(put(p," 10ms="),api->fd_read(0x3D),4));
#endif
  for (mode=0;mode<4;mode++){
    api->fd_write(0x73,(uint16_t)((afc&~0x10u)|((mode&2)?0x10u:0)));
    api->tune(hz,mode&1);
    api->delay_us(300000);
#ifdef SURVEY_COMPARE_IFSEL
    if(api->fd_read(0x3D)!=target){
      p=hex(put(line,"if 3d wanted="),target,4);
      p=hex(put(p," actual="),api->fd_read(0x3D),4);
      say0(api,line,hex(put(p," 43="),api->fd_read(0x43),4));
      ret=-11;goto out;
    }
    p=hex(put(line,"if 3d="),api->fd_read(0x3D),4);
    p=hex(put(p," 43="),api->fd_read(0x43),4);
    p=hex(put(p," 73="),api->fd_read(0x73),4);
    p=sdec(put(p," rssi="),rssi(api));
    say0(api,line,p);
#endif
    n=sum=lost=bad=0;lo=0xFFFFFFFFu;hi=0;
    b.ifm=17000;
    for(i=0;i<SURVEY_BLOCKS;i++){
      j=run(ring,sv.rsz,64,1,&b,(int)b.ifm);
      if(api->key_poll()){ret=-2;goto out;}
      if(j){lost++;continue;}
      /* Report low-IF readings too; refcal's nominal-window rejection is not appropriate here. */
      if(b.ifm<1000||b.ifm>40000){bad++;continue;}
      if(b.ifm<lo)lo=b.ifm;
      if(b.ifm>hi)hi=b.ifm;
      sum+=b.ifm;n++;
    }
    p=kv(line,"if w=",mode&1);
    p=kv(p," off=",!!(mode&2));
    p=kv(p," if=",n?udiv(sum+n/2,n):0);
    p=kv(p," lo=",n?lo:0);
    p=kv(p," hi=",hi);
    p=kv(p," n=",n);
    p=kv(p," lost=",lost);
    p=kv(p," bad=",bad);
    say0(api,line,p);
  }
#ifdef SURVEY_COMPARE_IFSEL
  }
#endif
  ret=0;
out:
#ifdef SURVEY_COMPARE_IFSEL
  api->fd_write(0x3D,ifsel);
#endif
  api->fd_write(0x73,afc);
  api->tune(hz,bw==0x3028);
  teardown(api,&sv);
  return ret;
}
