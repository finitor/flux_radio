/* Capture a short APRS burst on the measured B-chip IF, after a quiet baseline.
   Same 144.390 MHz, wide filter, AGC, AFC off as APRS IF 8K.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 2
#define K6_MODULE_OPT z
#define CAP_B_APRS 1
#define CAP_AFC_OFF 1
#define CAP_B_DELAY_US 180000u
#define NCAP 6000u
#define K 1
#define WAIT_S 60
#include "gp0cap.c"
K6_MODULE_NAME("APRS 8K CAP");
