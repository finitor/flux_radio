/* Flux FD6818B candidate: upstream refcal, serial diagnostics, dry run only.
   No calibration-sector writes; temporary trim restored on every normal return.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#define GP0_NO_WAIT 1
#define REFCAL_NREF 4
#include "refcal.c"
K6_MODULE_NAME("REFCAL DRY");
