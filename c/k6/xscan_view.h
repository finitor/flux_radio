/* Internal shared-scanner boundary, for migration without changing legacy xs_t layouts.
 * Each consumer supplies its own storage; the engine must never assume XS_HOT.
 * This header is not a sideloadable-module ABI. SPDX-License-Identifier: MIT */
#ifndef K6_XSCAN_VIEW_H
#define K6_XSCAN_VIEW_H
#include "xscan.h"
typedef struct {
  xs_t *legacy;           /* the consumer's existing prefix; not a universal full xs_t */
  xs_hot_t *hot;          /* consumer-owned entries */
  uint8_t hot_capacity;  /* 4 for compact Explore, 10 for core Explore */
  uint8_t row_columns;   /* 1 for compact Explore, up to 128 for core */
  uint8_t enable_peek;
  uint8_t enable_refine;
  uint8_t enable_sweep_diag;
} xs_engine_view_t;
/* A future engine must use the supplied pointers/capacities, not sizeof(xs_t)
 * or offsets of fields after xs_t.hot. Existing xs_* APIs remain unchanged. */
#endif
