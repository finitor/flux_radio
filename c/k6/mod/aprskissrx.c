/* Receive-only KISS port 0 bridge; no command/host-frame handling or TX.
   Uses the physical FD6818B discriminator receiver. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 14
#define K6_MODULE_OPT s
#define K6_NAME "APRS KISS RX"
#define FIF_CHZ 846354u
#define APRS_DISC 1
#define APRS_KISS 1
#ifndef RUN_MS
#define RUN_MS 3600000u
#endif
#include "aprsifbcal.c"
