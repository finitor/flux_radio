/* Shared hot-list operations: no knowledge of consumer xs_t layout. MIT */
#ifndef K6_XSCAN_HOT_H
#define K6_XSCAN_HOT_H
#include "xscan.h"
xs_hot_t *xs_hot_near(xs_hot_t *hot, unsigned capacity, uint32_t hz, uint32_t tolerance, int up);
xs_hot_t *xs_hot_slot(xs_hot_t *hot, unsigned capacity, int level, unsigned hit_db);
#endif
