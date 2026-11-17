/* APRS RX: plain-FSK samples from the discriminator, decoded as Bell 202 in aprsclk.c.
   This is the APRS path that handles sender pre-emphasis. 144.390 MHz. SPDX-License-Identifier: MIT */
#define K6_MODULE_OPT z
#define K6_MODULE_LEVEL 2
#define K6_NAME "APRS RX"
#define APRS_FSK
#define FSK_PLAIN
#include "aprsclk.c"
