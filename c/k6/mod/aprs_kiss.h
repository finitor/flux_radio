/* KISS port-zero data framing; caller supplies FCS-stripped AX.25.
   Bounded chunks avoid a large stack/scratch allocation. SPDX-License-Identifier: MIT */
#ifndef FLUX_APRS_KISS_H
#define FLUX_APRS_KISS_H
#include <stdint.h>
static __attribute__((unused)) int ap_kiss_send(int (*write)(const uint8_t*,uint16_t),const uint8_t *f,unsigned n){
  uint8_t out[64];unsigned used=0,i;
  if(!write||!f||n<15||n>330)return -1;
  out[used++]=0xc0;out[used++]=0;
  for(i=0;i<n;i++){
    unsigned b=f[i];
    if(used>=62){if(write(out,(uint16_t)used)<0)return -1;used=0;}
    if(b==0xc0||b==0xdb){out[used++]=0xdb;out[used++]=b==0xc0?0xdc:0xdd;}
    else out[used++]=(uint8_t)b;
  }
  out[used++]=0xc0;
  return write(out,(uint16_t)used)<0?-1:0;
}
#endif
