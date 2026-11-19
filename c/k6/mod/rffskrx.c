/* FD6818B managed native FSK receive diagnostic; no TX. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 10
#define K6_MODULE_OPT z
#include "k6ui.h"
K6_MODULE_NAME("RF FSK RX");
int k6_main(const k6_api_t *a){
  ui_t u;uint16_t w[8];uint32_t start,n=0;unsigned i,j;
  char line[60],*p;int r=0;
  if(a->level<10||a->fd_read(0)!=0x4829)return -3;
  ui_begin(&u,a,"RF FSK RX","Native FIFO; 60s");
  ui_mhz(line,a->rx_hz());ui_text(&u,2,line);
  ui_text(&u,5,"Any key: stop");ui_now(&u);
  if(u.on){ui_release(&u);if(a->key_poll())return -2;}
  if(a->fsk_rx_start()!=0){a->say("rf fsk RX unavailable");ui_end(&u,"FSK unavailable",0);return -4;}
  start=a->ms();
  while(a->ms()-start<60000u){
    if(a->key_poll()){r=-2;break;}
    if(a->fsk_rx_ready()&&a->fsk_rx_read(w)==0){
      p=ui_dec(ui_put(line,"rf fsk n="),++n,1);p=ui_put(p," ");
      for(i=0;i<8;i++)for(j=16;j;j-=4)*p++="0123456789abcdef"[(w[i]>>(j-4))&15];
      *p=0;a->say(line);
      ui_dec(ui_put(line,"Frames: "),n,1);ui_text(&u,3,line);
      ui_text(&u,4,w[4]==0x55aa&&w[5]==0xaa55&&w[6]==0x0123&&w[7]==0x4567?"Test pattern OK":"Other/errored frame");
      ui_flush(&u,100);
      if(n>=1000u)break;
    }
    a->delay_us(1000);
  }
  a->fsk_rx_stop();
  ui_dec(ui_put(line,"rf fsk total="),n,1);a->say(line);
  ui_end(&u,"RX finished",r!=0);return r?r:(int)n;
}
