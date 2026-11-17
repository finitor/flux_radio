/* Host-side smoke test: no radio required. */
#include <assert.h>
#include <string.h>
#include "k6_mod.h"

int k6_main(const k6_api_t *);
static int calls;
static void say(const char *text) {
    assert(strcmp(text, "Hello from Flux!") == 0);
    ++calls;
}
int main(void) {
    const k6_api_t api = {.abi = 1, .level = 1, .say = say};
    assert(k6_main(&api) == 0);
    assert(calls == 1);
    return 0;
}
