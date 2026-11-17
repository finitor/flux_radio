/* Third-order complex CIC decimator for the GP0 IF front end.
 * Unsigned modular integrators avoid signed-overflow undefined behavior.
 * Output is scaled by 2^(3*log2(R)); R must be a power of two <= 32.
 * SPDX-License-Identifier: MIT */
#ifndef K6_IF_CIC_H
#define K6_IF_CIC_H
#include <stdint.h>
typedef struct {
  uint32_t integ[2][3], delay[2][3];
  uint16_t count, ratio;
  uint8_t shift;
} k6_if_cic_t;
int k6_if_cic_init(k6_if_cic_t *s, uint16_t ratio);
int k6_if_cic_push(k6_if_cic_t *s, int16_t in_i, int16_t in_q,
                   int16_t *out_i, int16_t *out_q);
#endif
