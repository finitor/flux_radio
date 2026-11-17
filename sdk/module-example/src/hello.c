/* SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 1
#include "k6_mod.h"

K6_MODULE_NAME("HELLO");

int k6_main(const k6_api_t *api) {
    api->say("Hello from Flux!");
    return 0;
}
