/* Flux APRS receive app. The B-chip discriminator baseline is unchanged.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 6
#define K6_MODULE_OPT s
#define K6_NAME "APRS"
#define FIF_CHZ 846354u
#define APRS_DISC 1
#define APRS_APP 1
#ifndef RUN_MS
#define RUN_MS 3600000u
#endif
#include "aprsifbcal.c"
