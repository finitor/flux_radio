/* Explicit user-confirmed APRS position beacon. No automatic transmissions.
   Uses existing radio settings and the bounded host AFSK API. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 15
#define K6_MODULE_OPT z
#include "k6ui.h"
#include "aprs_tx.h"
K6_MODULE_NAME("APRS BEACON");
typedef struct {uint8_t settings[KM_SETTINGS_BYTES],frame[75];ap_tx_t tx;ui_t ui;} beacon_t;
static uint32_t le32(const uint8_t *p){return (uint32_t)p[0]|(uint32_t)p[1]<<8|(uint32_t)p[2]<<16|(uint32_t)p[3]<<24;}
int k6_main(const k6_api_t *api){
  static const char symbols[]="[;>kb-_#&O'";
  uint32_t room,hz,old_hz,start;
  uint16_t old_bw;
  int32_t lat,lon;
  unsigned n=14,i,path,symbol,ssid;int key,ret;
  beacon_t *s;
  char line[32],*p;
  if(api->level<15)return -3;
  s=(beacon_t *)api->scratch(&room);
  if(room<sizeof *s)return -8;
  if(api->settings_read(s->settings,sizeof s->settings)!=(int)sizeof s->settings)return -4;
  hz=le32(s->settings+KM_SETTINGS_APRS_FREQ);
  lat=(int32_t)le32(s->settings+KM_SETTINGS_APRS_LAT);
  lon=(int32_t)le32(s->settings+KM_SETTINGS_APRS_LON);
  ssid=s->settings[KM_SETTINGS_APRS_SSID];
  path=s->settings[KM_SETTINGS_APRS_PATH];
  symbol=s->settings[KM_SETTINGS_APRS_SYMBOL];
  if(lat < -9000000||lat>9000000||lon < -18000000||lon>18000000||
     !((hz>=144000000u&&hz<=148000000u)||(hz>=420000000u&&hz<=450000000u))||
     path>3||symbol>=sizeof symbols-1||!ap_tx_addr(s->frame+7,s->settings+KM_SETTINGS_APRS_CALLSIGN,ssid,path==3)){
    api->say("APRS beacon: check callsign, position, path, frequency");return -5;
  }
  ap_tx_addr(s->frame,(const uint8_t *)"APRS  ",0,0);
  if(path==0){ap_tx_addr(s->frame+n,(const uint8_t *)"WIDE1 ",1,0);n+=7;ap_tx_addr(s->frame+n,(const uint8_t *)"WIDE2 ",1,1);n+=7;}
  else if(path==1){ap_tx_addr(s->frame+n,(const uint8_t *)"WIDE2 ",2,1);n+=7;}
  else if(path==2){ap_tx_addr(s->frame+n,(const uint8_t *)"ARISS ",0,1);n+=7;}
  s->frame[n++]=3;s->frame[n++]=0xf0;s->frame[n++]='!';
  ap_tx_coord(s->frame+n,lat,0,ui_udiv);n+=8;
  s->frame[n++]='/';ap_tx_coord(s->frame+n,lon,1,ui_udiv);n+=9;
  s->frame[n++]=(uint8_t)symbols[symbol];
  for(i=0;i<16;i++){unsigned b=s->settings[KM_SETTINGS_APRS_COMMENT+i];if(!b||b==255)break;if(b>=32&&b<=126)s->frame[n++]=(uint8_t)b;}
  if(!ap_tx_encode(&s->tx,s->frame,n))return -6;
  ui_begin(&s->ui,api,"APRS BEACON","Confirm transmission");
  if(!s->ui.on){api->say("APRS beacon requires display");return -7;}
  p=line;for(i=0;i<6&&s->settings[KM_SETTINGS_APRS_CALLSIGN+i]&&s->settings[KM_SETTINGS_APRS_CALLSIGN+i]!=' ';i++)*p++=(char)s->settings[KM_SETTINGS_APRS_CALLSIGN+i];
  *p=0;if(ssid){*p++='-';ui_dec(p,ssid,1);}
  ui_text(&s->ui,2,line);
  ui_mhz(line,hz);ui_text(&s->ui,3,line);
  ui_text(&s->ui,4,"One position packet");
  ui_text(&s->ui,5,"M:send  EXIT:cancel");ui_now(&s->ui);
  start=api->ms();
  /* Require release of menu-launch key before a fresh confirmation. */
  while(api->key_poll()){if(km_power_switch_off()||api->ms()-start>15000)return -2;api->delay_us(10000);}
  do{key=ui_key(&s->ui);if(key=='X'||api->ms()-start>15000)return -2;api->delay_us(10000);}while(key!='M');
  old_hz=api->rx_hz();old_bw=api->fd_read(0x43);
  api->tune(hz,1);
  /* Two separated samples above the observed B-chip idle floor (-87 dBm).
     This coarse carrier check is NOT a complete CSMA implementation. */
  api->delay_us(200000);
  ret=(KM_RSSI_DBM(api->fd_read(0x67))>-82);
  api->delay_us(100000);
  if(ret||KM_RSSI_DBM(api->fd_read(0x67))>-82){api->say("APRS beacon: channel busy");ret=-9;goto restore;}
  if(api->tx_on(3000)!=0){api->say("APRS beacon: TX refused");ret=-10;goto restore;}
  ret=api->afsk_tx_send(s->tx.data,s->tx.bits);
  api->tx_off();
  api->say(ret?"APRS beacon: send failed":"APRS beacon: TX complete");
restore:
  api->tune(old_hz,old_bw==0x3028);
  ui_hold(api,ret?"NOT SENT  ANY KEY":"SENT  ANY KEY");
  return ret;
}
