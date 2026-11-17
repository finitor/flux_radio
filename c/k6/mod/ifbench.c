/* IF BENCH: repeatable CPU timing probe, no RF, flash, UART reconfiguration or DMA ownership.
 * Run on hardware and the Cortex-M0 emulator; output 100-us ticks for each workload.
 * The volatile sink prevents optimizing away the work. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 2
#include "../k6_mod.h"
K6_MODULE_NAME("IF BENCH");
#define N 8192u
#define R 1024u
static const uint32_t powers[] = {1000000000u,100000000u,10000000u,1000000u,100000u,10000u,1000u,100u,10u,1u};
static char *dec10(char *p, uint32_t v) {
  unsigned k;
  for (k=0;k<10;k++) {
    unsigned d=0;
    while (v>=powers[k]) { v-=powers[k]; d++; }
    *p++=(char)('0'+d);
  }
  return p;
}
static void report(const k6_api_t *api, const char *tag, uint32_t ticks, uint32_t value) {
  char line[58], *p=line;
  while (*tag) *p++=*tag++;
  *p++=' '; p=dec10(p,ticks); *p++=' '; p=dec10(p,value); *p=0;
  api->say(line);
}
int k6_main(const k6_api_t *api) {
  uint32_t room, i, j, t0, t1, acc=0;
  uint8_t *buf=(uint8_t *)api->scratch(&room);
  if (!buf || room<R+N/8+4) { api->say("ifbench insufficient scratch"); return -8; }
  for(i=0;i<R;i++) buf[i]=(uint8_t)((i*73u+19u)&255u);
  report(api,"ifbench v1 scratch",room,0);
  t0=api->ticks();
  for(i=0;i<N;i++) acc+=((i^0x5a5au)&7u);
  t1=api->ticks(); report(api,"ifbench arithmetic",(uint16_t)(t1-t0),acc);
  t0=api->ticks();
  for(i=0;i<N;i++) acc+=((buf[i&(R-1u)]>>1)&1u);
  t1=api->ticks(); report(api,"ifbench read",(uint16_t)(t1-t0),acc);
  t0=api->ticks();
  for(i=0;i<N/8;i++) buf[R+i]=0;
  for(i=0;i<N;i++) {
    j=i&(R-1u);
    buf[R+(i>>3)]|=(uint8_t)(((buf[j]>>1)&1u)<<(i&7u));
  }
  t1=api->ticks(); report(api,"ifbench pack",(uint16_t)(t1-t0),acc);
  for(i=0;i<N/8;i++) acc+=buf[R+i];

  report(api,"ifbench checksum",0,acc);
  return (int)(acc&0x7fff);
}
