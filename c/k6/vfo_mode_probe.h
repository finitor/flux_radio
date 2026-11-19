/* Experimental cooperative callback contract; not a published module ABI. */
#ifndef K6_VFO_MODE_PROBE_H
#define K6_VFO_MODE_PROBE_H
#include <stdint.h>
enum { VM_START=1, VM_RX=2, VM_RESET=3, VM_STOP=4 };
typedef int (*vm_callback)(void *state, uint32_t event, uint32_t value);
typedef struct { uint32_t count, resets, active, last; } vm_probe_state;
int vm_probe(void *state, uint32_t event, uint32_t value);
typedef struct { vm_callback callback; void *state; } vm_dispatcher;
int vm_dispatch(vm_dispatcher *d, vm_callback cb, void *state);
int vm_event(vm_dispatcher *d, uint32_t event, uint32_t value);
#endif
