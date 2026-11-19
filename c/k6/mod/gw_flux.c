/* GROUNDWAVE for the compact Flux host. The original FD6818 direct-register
   radio protocol is not compatible with the managed FD6818B FSK service.
   This build retains the whole local game and audio without any RF TX path.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 6
#define K6_MODULE_OPT z
#define GW_RADIO 0
#include "gw.c"
