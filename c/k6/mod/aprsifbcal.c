/* Receive-only B-chip APRS experiment. Uses wide filter, AGC, explicit AFC
   disable and a selectable IF mixer center in centihertz. The default is the
   legacy nominal IF, NOT a verified FD6818B measurement. Override FIF_CHZ
   with the result of IF SURVEY on a known carrier in the same band.
   SPDX-License-Identifier: MIT */
#ifndef K6_NAME
#define K6_NAME "APRS IF CAL"
#endif
#ifndef K6_MODULE_LEVEL
#define K6_MODULE_LEVEL 4
#endif
#define APRS_RX_ONLY 1
#define APRS_IF_AFC_OFF 1
#define GAIN13 0
#ifndef RUN_MS
#define RUN_MS 120000u
#endif
#include "aprsclk.c"
