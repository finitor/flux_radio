#include "if_cic.h"
int k6_if_cic_init(k6_if_cic_t *s, uint16_t ratio) {
  unsigned ch, j, bits=0;
  if (!ratio || ratio > 32 || (ratio & (ratio-1))) return 0;
  for (ch=0;ch<2;ch++) for(j=0;j<3;j++)
    s->integ[ch][j]=s->delay[ch][j]=0;
  while ((1u << bits) != ratio) bits++;
  s->ratio=ratio; s->count=0; s->shift=(uint8_t)(3*bits);
  return 1;
}
int k6_if_cic_push(k6_if_cic_t *s, int16_t in_i, int16_t in_q,
                   int16_t *out_i, int16_t *out_q) {
  uint32_t v[2]={(uint32_t)(int32_t)in_i,(uint32_t)(int32_t)in_q};
  unsigned ch,j;
  for(ch=0;ch<2;ch++) {
    for(j=0;j<3;j++) {
      s->integ[ch][j]+=v[ch];
      v[ch]=s->integ[ch][j];
    }
  }
  if(++s->count<s->ratio) return 0;
  s->count=0;
  for(ch=0;ch<2;ch++) {
    v[ch]=s->integ[ch][2];
    for(j=0;j<3;j++) {
      uint32_t old=s->delay[ch][j];
      s->delay[ch][j]=v[ch];
      v[ch]-=old;
    }
  }
  /* Use sign magnitude for portable negative division by power of two. */
  for(ch=0;ch<2;ch++) {
    int32_t signed_value=(int32_t)v[ch];
    int32_t scaled=signed_value>=0 ? signed_value >> s->shift :
      -(int32_t)((0u-(uint32_t)signed_value)>>s->shift);
    if(scaled>32767) scaled=32767;
    if(scaled< -32768) scaled=-32768;
    if(ch==0) *out_i=(int16_t)scaled;
    else *out_q=(int16_t)scaled;
  }
  return 1;
}
