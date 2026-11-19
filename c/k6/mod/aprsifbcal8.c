/* B-chip candidate: 8.46354 kHz nominal, supported by the two 146.560 MHz
   IF CARRIER runs (center 8379-8388 Hz, approximately -80 Hz offset).
   Actual AX.25 reception on B hardware is not yet validated.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define APRS_RF_DIAG 1
#define FIF_CHZ 846354u
#define K6_NAME "APRS IF 8K"
#include "aprsifbcal.c"
