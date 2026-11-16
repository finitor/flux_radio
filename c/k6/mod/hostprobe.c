/* Minimal shared-host contract probe: scratch, LCD callbacks and normal return.
   No RF setup or transmit. SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 6
#include "../k6_mod.h"
K6_MODULE_NAME("HOST PROBE");

int k6_main(const k6_api_t *api) {
  uint32_t size;
  uint8_t *scratch;
  int result;
  if (api->level < 6) return -1;
  api->say("host probe enter");
  scratch = api->scratch(&size);
  if (!scratch || size < 16) return -2;
  scratch[0] = 0x36;
  scratch[size - 1] = 0x79;
  api->lcd_text(0, "HOST PROBE");
  api->lcd_text(1, "Shared LCD callback");
  result = api->lcd_flush();
  if (result < 0) return -3;
  if (scratch[0] != 0x36 || scratch[size - 1] != 0x79) return -4;
  api->say("host probe done");
  return 42;
}
