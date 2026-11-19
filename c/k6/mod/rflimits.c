/* RF laboratory: passive synthesizer/receiver survey, both known chip IDs.
   Raw register 0x0c bit 9 is a candidate lock indication, NOT proof of lock.
   No register writes, TX, PA control, or persistent changes. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#include "k6ui.h"
K6_MODULE_NAME("RF LIMITS");

static const uint32_t frequencies[] = {
  16000000u, 18000000u, 29000000u, 50000000u, 88000000u,
  145000000u, 223500000u, 433500000u, 550000000u, 560000000u,
  600000000u, 630000000u, 700000000u, 740000000u, 800000000u,
  902000000u, 915000000u, 928000000u, 1000000000u, 1120000000u
};
static char *hex4(char *p,uint16_t v){
  int i;for(i=12;i>=0;i-=4)*p++="0123456789abcdef"[(v>>i)&15];
  *p=0;return p;
}
static int read_at(const k6_api_t *a,uint32_t hz,uint16_t *status){
  int i,s=0;
  a->tune(hz,0);
  a->delay_us(40000);
  *status=a->fd_read(0x0c);
  for(i=0;i<4;i++){s+=KM_RSSI_DBM(a->fd_read(0x67));a->delay_us(1000);}
  return s/4;
}
int k6_main(const k6_api_t *a){
  ui_t u; char line[60],*p;uint32_t old,hz,i;
  uint16_t id,oldbw,st,refst;int sig,ref,r=0;
  if(a->level<4)return -3;
  id=a->fd_read(0);
  if(id!=0x4819&&id!=0x4829){a->say("rf limits: unknown chip");return -4;}
  old=a->rx_hz();oldbw=a->fd_read(0x43);
  ui_begin(&u,a,"RF LIMITS","RX only / narrow");
  ui_text(&u,5,"Any key: stop");ui_now(&u);
  if(u.on){ui_release(&u);if(a->key_poll())return -2;}
  hex4(ui_put(line,"rf chip="),id);a->say(line);
  for(i=0;i<sizeof frequencies/sizeof frequencies[0]+1;i++){
    if(a->key_poll()){r=-2;break;}
    hz=i?frequencies[i-1]:old;
    sig=read_at(a,hz,&st);ref=read_at(a,hz+30000u,&refst);
    p=ui_dec(ui_put(line,"rf hz="),hz,1);
    p=hex4(ui_put(p," st="),st);
    p=hex4(ui_put(p," refst="),refst);
    p=ui_sdec(ui_put(p," r="),sig);
    ui_sdec(ui_put(p," ref="),ref);
    a->say(line);
    p=ui_mhz(line,hz);p=ui_sdec(ui_put(p," "),sig);
    ui_sdec(ui_put(p,"/"),ref);
    ui_log(&u,line);ui_flush(&u,100);
  }
  a->tune(old,oldbw==0x3028u);
  a->say(r?"rf limits stopped":"rf limits complete");
  ui_end(&u,r?"Stopped":"Done; serial report",r!=0);
  return r;
}
