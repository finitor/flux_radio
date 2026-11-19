/* FD6818B 8.46 kHz IF receiver, using the FM discriminator for the
   bit decision as well as the DPLL. On the physical 2026-11-17 capture
   this recovered five adjacent HDLC flags, unlike the IF matched filter.
   Receive only; not yet validated for complete frames on B hardware.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_NAME "APRS 8K DISC"
#define FIF_CHZ 846354u
#define APRS_DISC 1
#include "aprsifbcal.c"
