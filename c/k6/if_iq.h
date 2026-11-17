/* Portable fixed-point IF downconverter: population counts -> complex IQ.
 * Prototype DSP core only; caller owns DMA and serial transport.
 * SPDX-License-Identifier: MIT */
#ifndef K6_IF_IQ_H
#define K6_IF_IQ_H
#include <stdint.h>
typedef struct {
  uint32_t phase, step;
  int32_t i_acc, q_acc;
  uint16_t n, decimation;
} k6_if_iq_t;
void k6_if_iq_init(k6_if_iq_t *s, uint32_t phase_step, uint16_t decimation);
/* Returns 1 and writes an I/Q pair whenever decimation input counts arrive.
 * x is signed, centered GP0 population count (count - 32 for LCNT=64).
 * Output is a scaled mean of mixed counts, signed int16. */
int k6_if_iq_push(k6_if_iq_t *s, int16_t x, int16_t *i, int16_t *q);
#endif
