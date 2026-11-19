#include "scheduled_dispatch.h"
int sd_enable(sd_job *j,uint32_t now,uint32_t interval,uint32_t grace) {
    if (!interval || interval>=0x80000000u || grace>=interval) return -1;
    j->interval=interval; j->grace=grace; j->deadline=now+interval; j->enabled=1;
    return 0;
}
void sd_cancel(sd_job *j) { j->enabled=0; }
int sd_poll(sd_job *j,uint32_t now,int rf_idle,int arena_available) {
    if (!j->enabled) return SD_WAIT;
    uint32_t late=now-j->deadline;
    if (late>=0x80000000u) return SD_WAIT;
    if (late<=j->grace && !(rf_idle && arena_available)) return SD_WAIT;
    int result=late<=j->grace ? SD_DISPATCH : SD_SKIP;
    /* Rebase to next future deadline without executing missed jobs.
       Remainder form avoids overflow in multiplying a missed-period count. */
    j->deadline=now+(j->interval-late%j->interval);
    return result;
}
