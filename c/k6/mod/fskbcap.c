/* fskbcap: observe the FD6818B's fixed-length FSK FIFO without imposing a byte-order guess.
   This is the first hardware-facing port probe: it logs eight raw FIFO words per received
   frame. It does not decode Blowfang's legacy packet format or transmit. Hold any key to stop.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 10
#define K6_MODULE_OPT z
#include "../k6_mod.h"
#define FSKBCAP_NAME "FSKB CAP"
K6_MODULE_NAME(FSKBCAP_NAME);

static char hex_digit(unsigned v) { return "0123456789ABCDEF"[v & 15u]; }

static void show_frame(const k6_api_t *api, const uint16_t words[8]) {
  char line[60];
  unsigned i;
  char *p = line;
  *p++ = 'F'; *p++ = 'S'; *p++ = 'K'; *p++ = 'B'; *p++ = ' ';
  for (i = 0; i < 8; ++i) {
    *p++ = hex_digit(words[i] >> 12);
    *p++ = hex_digit(words[i] >> 8);
    *p++ = hex_digit(words[i] >> 4);
    *p++ = hex_digit(words[i]);
  }
  *p = 0;
  api->say(line);
}

int k6_main(const k6_api_t *api) {
  int frames = 0;
  uint16_t words[8];
  if (api->level < 10 || api->fsk_rx_start() != 0) {
    api->say("FSKB needs FD6818B API 10");
    return -1;
  }
  api->say("FSKB raw RX; key to stop");
  api->lcd_text(0, "FD6818B raw FSK");
  api->lcd_text(1, "Waiting for frames");
  api->lcd_flush();
  while (!api->key_down()) {
    if (api->fsk_rx_ready() && api->fsk_rx_read(words) == 0) {
      show_frame(api, words);
      ++frames;
      if ((frames & 3) == 0) {
        api->lcd_text(1, "Frame received");
        api->lcd_flush();
      }
    }
    api->delay_us(2000);
  }
  api->fsk_rx_stop();
  api->say("FSKB stopped");
  return 0;
}
