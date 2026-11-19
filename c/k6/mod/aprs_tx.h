/* AX.25 UI frame and Bell 202 NRZI builder, shared with host tests.
   SPDX-License-Identifier: MIT */
#ifndef FLUX_APRS_TX_H
#define FLUX_APRS_TX_H
#include <stdint.h>
#define TX_FN static __attribute__((unused))
#define AP_TX_BYTES 128
typedef struct {uint8_t data[AP_TX_BYTES];uint16_t bits;uint8_t tone,ones,failed;} ap_tx_t;
TX_FN uint16_t ap_crc16(const uint8_t *p,unsigned n){
  uint16_t c=0xffff;unsigned i;
  while(n--){c^=*p++;for(i=0;i<8;i++)c=(uint16_t)((c>>1)^((c&1)?0x8408:0));}
  return (uint16_t)~c;
}
TX_FN void ap_tx_bit(ap_tx_t *t,unsigned bit){
  unsigned n=t->bits;
  if(n>=AP_TX_BYTES*8){t->failed=1;return;}
  if(!bit)t->tone^=1;
  if(!(n&7))t->data[n>>3]=0;
  if(t->tone)t->data[n>>3]|=(uint8_t)(0x80>>(n&7));
  t->bits++;
}
TX_FN void ap_tx_byte(ap_tx_t *t,unsigned v,int stuff){
  unsigned i,b;
  for(i=0;i<8;i++){
    b=(v>>i)&1;ap_tx_bit(t,b);
    if(stuff){if(b){if(++t->ones==5){ap_tx_bit(t,0);t->ones=0;}}else t->ones=0;}
  }
}
TX_FN int ap_tx_encode(ap_tx_t *t,const uint8_t *f,unsigned n){
  unsigned i;uint16_t c;
  if(n<17||n>75)return 0;
  t->bits=0;t->tone=t->ones=t->failed=0;
  for(i=0;i<32;i++)ap_tx_byte(t,0x7e,0);
  c=ap_crc16(f,n);
  for(i=0;i<n;i++)ap_tx_byte(t,f[i],1);
  ap_tx_byte(t,c&255,1);ap_tx_byte(t,c>>8,1);
  for(i=0;i<3;i++)ap_tx_byte(t,0x7e,0);
  return t->failed?0:t->bits;
}
TX_FN int ap_tx_addr(uint8_t *f,const uint8_t *call,unsigned ssid,int last){
  unsigned i,end=0,n=0,c;
  if(ssid>15)return 0;
  for(i=0;i<6;i++){
    if(!end&&(call[i]==0||call[i]==' '))end=1;
    c=end?' ':call[i];
    if(c!=' '){if(!((c>='A'&&c<='Z')||(c>='0'&&c<='9')))return 0;n++;}
    f[i]=(uint8_t)(c<<1);
  }
  f[6]=(uint8_t)(0x60|(ssid<<1)|(last?1:0));
  return n!=0;
}
/* Coordinates in degrees*100000, APRS hundredths of minutes. Avoid division
   runtime helpers on Cortex-M0 by using the shared ui_udiv at the call site. */
TX_FN void ap_tx_coord(uint8_t *p,int32_t v,int lon,uint32_t (*div)(uint32_t,uint32_t)){
  unsigned a=v<0?(uint32_t)-v:(uint32_t)v,d=div(a,100000);
  unsigned m=div((a-d*100000)*6000+50000,100000);
  unsigned k=lon?3:2,i;
  if(m>=6000){d++;m=0;}
  for(i=k;i>0;i--){unsigned q=div(d,10);p[i-1]=(uint8_t)('0'+d-q*10);d=q;}
  p[k]='0'+div(m,1000);p[k+1]='0'+div(m,100)-10*div(m,1000);
  p[k+2]='.';p[k+3]='0'+div(m,10)-10*div(m,100);p[k+4]='0'+m-10*div(m,10);
  p[k+5]=(uint8_t)(lon?(v<0?'W':'E'):(v<0?'S':'N'));
}
#endif
