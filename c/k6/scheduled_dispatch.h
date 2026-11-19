/* Host-owned periodic dispatch policy, milliseconds modulo 2^32. MIT. */
#ifndef K6_SCHEDULED_DISPATCH_H
#define K6_SCHEDULED_DISPATCH_H
#include <stdint.h>
typedef struct { uint32_t interval, grace, deadline; uint8_t enabled; } sd_job;
enum { SD_WAIT=0, SD_DISPATCH=1, SD_SKIP=2 };
int sd_enable(sd_job *j, uint32_t now, uint32_t interval, uint32_t grace);
void sd_cancel(sd_job *j);
int sd_poll(sd_job *j, uint32_t now, int rf_idle, int arena_available);
#endif
