/* Stable K6 API slots for builds without the scanner service.
 * Deliberately fail scanner startup; do not link the scanner engine.
 * Modules must also check firmware capabilities before using these slots.
 */
#include <stdint.h>
void kmx_xs_defaults(void *state) { (void)state; }
int kmx_xs_init(void *state, const void *api, void *candidates, uint8_t *mem, uint32_t bytes) {
    (void)state; (void)api; (void)candidates; (void)mem; (void)bytes;
    return -1;
}
int kmx_xs_step(void *state) { (void)state; return -1; }
void kmx_xs_close(void *state) { (void)state; }
void kmx_xs_resume(void *state) { (void)state; }
