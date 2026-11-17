#include "if_iq.h"
/* Q7 cosine LUT, 16-phase coarse mixer: no division, floats, or library calls. */
static const int8_t cos16[16] = {
  127,117,90,49,0,-49,-90,-117,-127,-117,-90,-49,0,49,90,117
};
void k6_if_iq_init(k6_if_iq_t *s, uint32_t step, uint16_t decimation) {
  s->phase=0; s->step=step; s->i_acc=0; s->q_acc=0;
  s->n=0; s->decimation=decimation ? decimation : 1;
}
int k6_if_iq_push(k6_if_iq_t *s, int16_t x, int16_t *i, int16_t *q) {
  unsigned phase=s->phase >> 28;
  s->i_acc+=(int32_t)x*cos16[phase];
  s->q_acc-=(int32_t)x*cos16[(phase+12u)&15u];
  s->phase+=s->step;
  if (++s->n < s->decimation) return 0;
  /* Divide-free power-of-two decimation is deliberate for Cortex-M0. */
  *i=(int16_t)(s->i_acc >> 7);
  *q=(int16_t)(s->q_acc >> 7);
  s->i_acc=s->q_acc=0; s->n=0;
  return 1;
}
