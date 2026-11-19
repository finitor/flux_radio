/* Guarded catalog entry for the existing FD6818B IF survey.
   Receive only; no new register recipes. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 4
#define K6_MODULE_OPT z
#define SURVEY_COMPARE_IFSEL 1
#define SURVEY_NAME "RF IF B"
#define k6_main rf_survey_main
#include "ifsurveyb.c"
#undef k6_main
int k6_main(const k6_api_t *api){
  if(api->level<4||api->fd_read(0)!=0x4829){api->say("RF baseband requires FD6818B");return -3;}
  return rf_survey_main(api);
}
