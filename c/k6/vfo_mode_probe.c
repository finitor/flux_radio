#include "vfo_mode_probe.h"
/* No legacy API, no RF or LCD access, no blocking loops. */
int vm_probe(void *state, uint32_t event, uint32_t value) {
    vm_probe_state *s=state;
    switch(event) {
    case VM_START: s->count=0; s->resets=0; s->last=0; s->active=1; return 0;
    case VM_STOP: s->active=0; return 0;
    case VM_RX: if (!s->active) return -1; s->count++; s->last=value; return 0;
    case VM_RESET: if (!s->active) return -1; s->resets++; s->last=0; return 0;
    default: return -1;
    }
}
/* Candidate dispatcher: caller must validate provider and own arena lease.
   Stop before replacing a resident provider; never call two concurrently. */
int vm_dispatch(vm_dispatcher *d, vm_callback cb, void *state) {
    if (d->callback) {
        int rc=d->callback(d->state,VM_STOP,0);
        d->callback=0; d->state=0;
        if (rc) return rc;
    }
    if (!cb) return 0;
    if (!state) return -1;
    int rc=cb(state,VM_START,0);
    if (!rc) { d->state=state; d->callback=cb; }
    return rc;
}
int vm_event(vm_dispatcher *d, uint32_t event, uint32_t value) {
    if (!d->callback || (event!=VM_RX && event!=VM_RESET)) return -1;
    int rc=d->callback(d->state,event,value);
    if (rc) { vm_dispatch(d,0,0); }
    return rc;
}
