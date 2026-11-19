/* Explicit IF-selector A/B test for FD6818B. No TX or persistent writes.
   Compares the inherited zero-IF condition against Aura's FM selection.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#define SURVEY_COMPARE_IFSEL 1
#define SURVEY_NAME "IF SURVEY FM"
#include "ifsurveyb.c"
