/* One guarded native FSK packet on the selected amateur VFO.
   Requires fresh MENU confirmation, dummy load, nonempty configured APRS call.
   No register writes or repeat. FD6818B Data service only. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 15
#define K6_MODULE_OPT z
#include "k6ui.h"
K6_MODULE_NAME("RF FSK TX");
static int allowed(uint32_t hz){
  return (hz>=144100000u&&hz<=147900000u)||(hz>=420100000u&&hz<=449900000u);
}
static int frame(const uint8_t *call,uint16_t *w){
  unsigned i,n=0;uint8_t c;
  for(i=0;i<4;i++)w[i]=0x2020;
  for(i=0;i<6;i++){
    c=call[i];
    if(!c||c==' ')break;
    if(!((c>='A'&&c<='Z')||(c>='0'&&c<='9')))return 0;
    if(i&1)w[i/2]=(w[i/2]&0xff00u)|c;else w[i/2]=(w[i/2]&0xffu)|((uint16_t)c<<8);
    n++;
  }
  if(n<3||(call[6]&&call[6]!=' '))return 0;
  w[3]=0x5246;w[4]=0x55aa;w[5]=0xaa55;w[6]=0x0123;w[7]=0x4567;return 1;
}
int k6_main(const k6_api_t *a){
  ui_t u;uint8_t settings[KM_SETTINGS_BYTES];uint16_t w[8];
  uint32_t hz,start;uint16_t bw;int k,r;char line[24];
  if(a->level<15||a->fd_read(0)!=0x4829)return -3;
  hz=a->rx_hz();
  if(!allowed(hz)||a->settings_read(settings,sizeof settings)!=sizeof settings||
      settings[KM_SETTINGS_TX_FORBID]||!frame(settings+KM_SETTINGS_APRS_CALLSIGN,w)){
    a->say("rf fsk TX: check VFO, TX lock, APRS call");return -4;
  }
  /* RX and TX share the Data feature gate. Probe it before any key-up. */
  bw=a->fd_read(0x43);
  if(a->fsk_rx_start()!=0){a->say("rf fsk Data service unavailable");return -7;}
  a->fsk_rx_stop();
  a->tune(hz,bw==0x3028u);
  ui_begin(&u,a,"RF FSK TX","DUMMY LOAD ONLY");
  if(!u.on)return -5;
  ui_mhz(line,hz);ui_text(&u,2,line);ui_text(&u,3,"One native frame");
  ui_text(&u,4,"Low power; no repeat");ui_text(&u,5,"M: send EXIT: cancel");ui_now(&u);
  start=a->ms();
  while(a->key_poll()){
    if(km_power_switch_off()||a->ms()-start>15000u)return -2;
    a->delay_us(10000);
  }
  do{k=ui_key(&u);if(k=='X'||a->ms()-start>15000u)return -2;a->delay_us(10000);}while(k!='M');
  if(km_power_switch_off())return -2;
  if(a->tx_on(5000)!=0){a->say("rf fsk TX refused");ui_end(&u,"TX refused",0);return -6;}
  r=a->fsk_tx_send(w);
  a->tx_off();
  a->say(r?"rf fsk TX failed":"rf fsk TX complete");
  ui_end(&u,r?"TX failed":"One frame sent",0);
  return r;
}
