/* IF CAPTURE: raw one-bit GP0/PB1 recording, exported after DMA stops.
 * The serial lines are deliberately emitted after capture to avoid UART stalls.
 * Requires FD6818B GP0 routing firmware (PR #68/#69). SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 2
#include "../k6_mod.h"
K6_MODULE_NAME("IF CAPTURE");
#define GPIOB 0x48000400u
#define RCC_AHBENR 0x40021014u
#define RCC_APB2ENR 0x40021018u
#define TIM17 0x40014800u
#define DMA 0x40020000u
#define RSZ 1024u
#define NRAW 8192u
#define TIM17EN (1u << 18)
static uint32_t rd(uint32_t a) { return *(volatile uint32_t *)a; }
static void wr(uint32_t a, uint32_t v) { *(volatile uint32_t *)a = v; }
static const char hex[] = "0123456789abcdef";
static void stop(void) { wr(TIM17,0); wr(TIM17+0x0c,0); wr(DMA+8,0); wr(DMA+4,15); }
int k6_main(const k6_api_t *api) {
  uint32_t room, ahb, apb, oldccr, n=0, consumed=0, laps=0, last=0, t0, t1;
  uint16_t r33,r34;
  uint8_t *mem=(uint8_t *)api->scratch(&room), *ring, *packed;
  char line[70];
  uint32_t i,j;
  if (!mem || room < RSZ+NRAW/8+4) { api->say("ifcap: insufficient scratch"); return -8; }
  ring=(uint8_t *)(((uint32_t)mem+3u)&~3u); packed=ring+RSZ;
  if (rd(GPIOB)&(3u<<2)) { api->say("ifcap: PB1 not input"); return -4; }
  ahb=rd(RCC_AHBENR); apb=rd(RCC_APB2ENR);
  wr(RCC_AHBENR,ahb|1u);
  oldccr=rd(DMA+8);
  if ((apb&TIM17EN)||(oldccr&1)) { wr(RCC_AHBENR,ahb); api->say("ifcap: DMA/TIM17 busy"); return -7; }
  r33=api->fd_read(0x33); r34=api->fd_read(0x34);
  if ((r33&0x100) && api->fd_write(0x33,r33&~0x100)) { wr(RCC_AHBENR,ahb); return -5; }
  api->fd_write(0x34,(r34&0xfff0)|13u);
  if ((api->fd_read(0x34)&15u)!=13u) {
    api->fd_write(0x34,r34); api->fd_write(0x33,r33); wr(RCC_AHBENR,ahb);
    api->say("ifcap: GP0 route unsupported"); return -9;
  }
  wr(RCC_APB2ENR,apb|TIM17EN);
  wr(DMA+8,0); wr(DMA+4,15); wr(DMA+0x10,GPIOB+0x10);
  wr(DMA+0x14,(uint32_t)ring); wr(DMA+0x0c,RSZ);
  wr(TIM17,0); wr(TIM17+0x28,0); wr(TIM17+0x2c,0xffff);
  wr(TIM17+0x14,1); wr(TIM17+0x10,0); wr(TIM17+0x0c,1u<<8);
  t0=api->ticks();
  wr(TIM17,1); wr(DMA+8,(3u<<12)|(1u<<7)|(1u<<5)|1u);
  while (n<NRAW && (uint32_t)(api->ticks()-t0)<300000u) {
    uint32_t pos=RSZ-(rd(DMA+0x0c)&0xffffu), produced;
    if (pos<last) laps++;
    last=pos; produced=laps*RSZ+pos;
    if (produced-consumed>=RSZ) { n=0; break; } /* overrun invalidates recording */
    if (produced==consumed) continue;
    packed[n>>3]=(uint8_t)((n&7u)?packed[n>>3]:0);
    packed[n>>3]|=(uint8_t)(((ring[consumed&(RSZ-1)]>>1)&1u)<<(n&7u));
    n++; consumed++;
  }
  t1=api->ticks(); stop();
  wr(DMA+0x0c,0); wr(DMA+0x10,0); wr(DMA+0x14,0);
  wr(RCC_APB2ENR,apb); wr(RCC_AHBENR,ahb);
  api->fd_write(0x34,r34); api->fd_write(0x33,r33);
  if (!n) { api->say("ifcap: overrun or timeout"); return -6; }
  /* Capture format: ifcap v1 N=<bits> ticks=<100us> hex rows (LSB first). */
  {
    char *p=line; const char *q="ifcap v1 bits="; uint32_t x=n, div=10000;
    while (*q) *p++=*q++;
    for (;div;div/=10) { *p++=hex[(x/div)%10]; }
    q=" ticks="; while (*q) *p++=*q++;
    x=t1-t0; for(div=100000;div;div/=10) *p++=hex[(x/div)%10];
    *p=0; api->say(line);
  }
  for (i=0;i<(n+7)/8;i+=24) {
    char *p=line; *p++='i';*p++='f';*p++=' '; 
    for(j=i;j<i+24 && j<(n+7)/8;j++) { *p++=hex[packed[j]>>4]; *p++=hex[packed[j]&15]; }
    *p=0; api->say(line);
  }
  api->say("ifcap end");
  return (int)n;
}
