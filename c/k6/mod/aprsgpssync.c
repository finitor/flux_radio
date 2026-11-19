/* One-shot receive-only APRS position sync. Exact direct source match.
   Automatically saves the first unambiguous valid fix, then stops.
   Change SYNC_SOURCE in a wrapper for a different station.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 23
#define K6_MODULE_OPT z
#define K6_NAME "GPS SYNC"
#define FIF_CHZ 846354u
#define APRS_DISC 1
#define APRS_SYNC 1
#ifndef SYNC_SOURCE
#define SYNC_SOURCE "AG7SU-7"
#endif
#ifndef RUN_MS
#define RUN_MS 300000u
#endif
#include "aprsifbcal.c"
