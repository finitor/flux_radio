/* FD6818B IF center/side probe. A quiet-channel baseline followed by a
   steady carrier and known tuning offsets; no REG_3D or trim changes.
   Receive only. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#define GP0_SWEEP 1
#define GP0_NO_MAIN 1
#define GP0_NO_WAIT 1
#define TAG "ifcarrier"
#include "gp0dma.c"
K6_MODULE_NAME("IF CARRIER");
#ifndef CARRIER_BLOCKS
#define CARRIER_BLOCKS 6
#endif
static int measure(const k6_api_t *api, saved_t *sv, uint8_t *ring, int offset, int baseline) {
  blk_t b;
  uint32_t n=0, sum=0, lo=0xFFFFFFFFu, hi=0, lost=0, i;
  char line[64], *p;
  int r=rssi(api);
  b.ifm=17000;
  for(i=0;i<CARRIER_BLOCKS;i++){
    if(run(ring,sv->rsz,64,1,&b,(int)b.ifm))lost++;
    else if(b.ifm>=1000 && b.ifm<=40000){
      if(b.ifm<lo)lo=b.ifm;
      if(b.ifm>hi)hi=b.ifm;
      sum+=b.ifm;n++;
    }
    if(api->key_poll())return -2;
  }
  p=sdec(put(line,baseline?"if noise d=":"if sig d="),offset);
  p=sdec(put(p," r="),r);
  p=kv(p," f=",n?udiv(sum+n/2,n):0);
  p=kv(p," lo=",n?lo:0);
  p=kv(p," hi=",hi);
  p=kv(p," l=",lost);
  say0(api,line,p);
  return n?0:-6;
}
int k6_main(const k6_api_t *api){
  static const int32_t offsets[]={0,-2000,2000,-4000,4000,0};
  saved_t sv;
  uint8_t *ring;
  uint16_t afc,bw;
  uint32_t hz,i;
  int ret,floor;
  char line[64],*p;
  if(api->level<4)return -3;
  hz=api->rx_hz();
  if(hz<18004000u||hz>1299996000u)return -6;
  afc=api->fd_read(0x73);bw=api->fd_read(0x43);
  ret=setup(api,&sv,&ring);if(ret)return ret;
  if((api->fd_read(SEL_REG)&15u)!=CODE){ret=-9;goto out;}
  if(api->fd_write(0x73,(uint16_t)(afc|0x10u))!=0){ret=-10;goto out;}
  api->tune(hz,1);api->delay_us(250000);
  if(!(api->fd_read(0x73)&0x10u)){ret=-10;goto out;}
  floor=rssi(api);
  p=kv(line,"if hz=",hz);
  p=hex(put(p," 3d="),api->fd_read(0x3D),4);
  p=sdec(put(p," floor="),floor);
  say0(api,line,p);
  ret=measure(api,&sv,ring,0,1);
  if(ret==-2)goto out;
  ret=carrier(api,floor);if(ret)goto out;
  for(i=0;i<sizeof offsets/sizeof offsets[0];i++){
    api->tune(hz+offsets[i],1);
    api->delay_us(180000);
    ret=measure(api,&sv,ring,offsets[i],0);
    if(ret==-2)goto out;
    /* A missing IF at one offset is useful data, not a reason to skip the rest. */
  }
  ret=0;
out:
  api->fd_write(0x73,afc);
  api->tune(hz,bw==0x3028);
  teardown(api,&sv);
  return ret;
}
