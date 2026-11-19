/* Cooperative APRS DSP adapter. No peripheral or LCD ownership.
 * Caller supplies signed IF counts (2*ones-64), at the configured DMA rate.
 * SPDX-License-Identifier: MIT */
#include <stdint.h>
#define APRS_HOST
#define APRS_RX_ONLY
#define APRS_APP
#define APRS_DISC
#define FIF_CHZ 846354u
#include "mod/aprsclk.c"

unsigned arx_state_bytes(void) { return sizeof(st_t); }
int arx_reset(void *state, uint32_t cps8) {
    st_t *s=state;
    if (!s || cps8<3000 || cps8>7000) return -1;
    for (unsigned i=0;i<sizeof(*s);i++) ((volatile uint8_t *)s)[i]=0;
    s->cps8=cps8;
    steps(s);
    s->n=(int32_t)udiv(64000000u+600u*cps8,1200u*cps8);
    if (s->n>NW-1) s->n=NW-1;
    return 0;
}
static void ignore_line(const char *line) { (void)line; }
int arx_feed(void *state, const int8_t *counts, unsigned n) {
    st_t *s=state;
    /* Deliberate bounded work; host must provide consecutive blocks. */
    if (!s || !counts || n>128 || !s->cps8) return -1;
    k6_api_t api={.abi=1,.level=2,.say=ignore_line};
    for (unsigned i=0;i<n;i++) count(&api,s,counts[i]);
    return 0;
}
unsigned arx_packets(const void *state) { return ((const st_t*)state)->ok; }
unsigned arx_preambles(const void *state) { return ((const st_t*)state)->pre; }
unsigned arx_history(const void *state) { return ((const st_t*)state)->hist_n; }
