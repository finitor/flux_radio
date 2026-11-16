/* VFO RADIO: a compact receive VFO and ten persistent memories for the RAM module host.
   Memory records share EXPLORE's crash-safe repeater table but are tagged RT_F_VFO, so
   repeater matching/listing ignores them. Voice PTT is not part of the current module API. */
#define K6_MODULE_LEVEL 6
#define K6_MODULE_OPT z
#include "../k6_mod.h"
#include "../rt.h"
#include "../rt.c"
#include "k6ui.h"

K6_MODULE_NAME("VFO RADIO");

#define VFO_MEMORIES 10
#define VFO_STEP_HZ 12500u
#define VFO_MIN_HZ 130000000u
#define VFO_MAX_HZ 520000000u

static int fl_read(void *c, uint32_t a, void *b, uint32_t n) {
  return ((const k6_api_t *)c)->fl_read(a, b, n);
}
static int fl_write(void *c, uint32_t a, const void *b, uint32_t n) {
  return ((const k6_api_t *)c)->fl_prog(a, b, n);
}
static int fl_erase(void *c, uint32_t a) {
  return ((const k6_api_t *)c)->fl_erase(a);
}

/* Locate a tagged memory slot; rt_find validates the record CRC before returning it. */
static int memory_find(rt_t *t, const k6_api_t *api, unsigned slot, rt_rec_t *out) {
  uint8_t raw[RT_REC];
  uint16_t flags, id;
  unsigned i;
  for (i = 0; i < RT_SLOTS; i++) {
    if (api->fl_read(RT_BASE + RT_REC * i, raw, sizeof raw) < 0) return RT_ERR_FLASH;
    flags = (uint16_t)raw[16] | (uint16_t)raw[17] << 8;
    id = (uint16_t)raw[54] | (uint16_t)raw[55] << 8;
    if (raw[0] == RT_ST_VALID && (flags & RT_F_VFO) &&
        raw[52] == slot + 1 && id && rt_find(t, id, 0, 0, out) >= 0)
      return i;
  }
  return RT_ERR_NONE;
}

static int memory_save(rt_t *t, const k6_api_t *api, unsigned slot, uint32_t hz) {
  rt_rec_t r;
  int i, at;
  at = memory_find(t, api, slot, &r);
  if (at == RT_ERR_FLASH) return at;
  if (at < 0) {
    uint8_t *p = (uint8_t *)&r;
    for (i = 0; i < (int)sizeof r; i++) p[i] = 0;
    r.group = (uint8_t)(slot + 1);
  }
  r.rx_hz = hz;
  r.tx_off = 0;
  r.flags |= RT_F_VFO;
  r.name[0] = 'V'; r.name[1] = 'F'; r.name[2] = 'O'; r.name[3] = 0;
  return rt_put(t, &r);
}

static char *frequency(char *p, uint32_t hz) {
  return ui_mhz(p, hz);
}

static void show(ui_t *ui, const k6_api_t *api, uint32_t a, uint32_t b,
                 unsigned active, unsigned mem, uint32_t entered, unsigned digits,
                 const char *status) {
  rt_t table;
  rt_flash_t flash = {fl_read, fl_write, fl_erase, (void *)api};
  rt_rec_t r;
  char line[32], *p;
  int mounted = rt_mount(&table, &flash, RT_BASE, 0);
  /* A title bar, a clear active marker, and aligned A/B frequencies make the tuned VFO
     immediately obvious. Keep the live key legend on the last line. */
  ui_text(ui, 0, active ? "BLOWFANG  VFO B" : "BLOWFANG  VFO A");
  p = ui_put(line, active ? "  A " : "> A ");
  p = frequency(p, a); p = ui_put(p, " MHz"); *p = 0;
  ui_text(ui, 1, line);
  p = ui_put(line, active ? "> B " : "  B ");
  p = frequency(p, b); p = ui_put(p, " MHz"); *p = 0;
  ui_text(ui, 2, line);
  p = ui_put(line, "W MEM ");
  p = ui_dec(p, mem + 1, 2); *p++ = ' ';
  if (mounted >= 0 && memory_find(&table, api, mem, &r) >= 0) {
    p = frequency(p, r.rx_hz); p = ui_put(p, " MHz");
  } else p = ui_put(p, "EMPTY");
  *p = 0; ui_text(ui, 3, line);
  if (digits) {
    p = ui_put(line, "ENTER "); p = ui_dec(p, entered, digits); *p = 0;
    ui_text(ui, 4, line);
  } else ui_text(ui, 4, status);
  ui_text(ui, 5, "N A/B W MEM U/D STEP");
  ui_now(ui);
}

int k6_main(const k6_api_t *api) {
  ui_t ui;
  rt_t table;
  rt_flash_t flash = {fl_read, fl_write, fl_erase, (void *)api};
  uint32_t hz[2], entered = 0;
  unsigned digits = 0, active = 0, mem = 0;
  int mounted, k, ret = 0;
  char status[UI_COLS + 1];

  status[0] = 'R'; status[1] = 'E'; status[2] = 'A'; status[3] = 'D';
  status[4] = 'Y'; status[5] = 0;

  if (api->level < 6) return -3;
  hz[0] = api->rx_hz();
  if (hz[0] < VFO_MIN_HZ || hz[0] > VFO_MAX_HZ) hz[0] = 145500000u;
  hz[1] = hz[0];
  mounted = rt_mount(&table, &flash, RT_BASE, 0);
  ui_begin(&ui, api, "BLOWFANG VFO", "RECEIVE ONLY");
  ui_release(&ui);
  api->tune(hz[0], 0);
  show(&ui, api, hz[0], hz[1], active, mem, entered, digits, "*:LOAD #:SAVE X:EXIT");

  for (;;) {
    k = ui_key(&ui);
    if (!k) { api->delay_us(10000); continue; }
    if (k == 'X') { ret = 0; break; }
    /* These keys are the firmware's direct escape to Aura when that image contains Aura. */
    if (k == 'M' || k == 'V' || k == 'A' || k == 'B') {
      (void)api->key_down();
      ret = 0;
      break;
    }
    status[0] = 0;
    if (k >= '0' && k <= '9') {
      if (digits < 6) {
        entered = entered * 10u + (uint32_t)(k - '0');
        digits++;
        if (digits == 6) {
          uint32_t f = entered * 1000u;
          if (f >= VFO_MIN_HZ && f <= VFO_MAX_HZ) {
            hz[active] = f; api->tune(f, 0);
            ui_put(status, "TUNED");
          } else ui_put(status, "BAD FREQ");
          entered = 0; digits = 0;
        } else {
        }
      }
    } else if (k == 'U' || k == 'D') {
      uint32_t f = hz[active];
      if (k == 'U' && f <= VFO_MAX_HZ - VFO_STEP_HZ) f += VFO_STEP_HZ;
      if (k == 'D' && f >= VFO_MIN_HZ + VFO_STEP_HZ) f -= VFO_STEP_HZ;
      hz[active] = f; api->tune(f, 0); ui_put(status, "TUNED");
      entered = 0; digits = 0;
    } else if (k == 'N') {
      active ^= 1; api->tune(hz[active], 0); ui_put(status, "VFO CHANGED");
      entered = 0; digits = 0;
    } else if (k == 'W') {
      mem = mem + 1 == VFO_MEMORIES ? 0 : mem + 1; ui_put(status, "MEMORY SELECTED");
    } else if (k == '*') {
      rt_rec_t r;
      int at = mounted >= 0 ? memory_find(&table, api, mem, &r) : RT_ERR_NOT_BLANK;
      if (at >= 0) { hz[active] = r.rx_hz; api->tune(r.rx_hz, 0); ui_put(status, "MEMORY LOADED"); }
      else ui_put(status, "NO MEMORY");
      entered = 0; digits = 0;
    } else if (k == '#') {
      if (mounted < 0) ui_put(status, "MEMORY TABLE UNAVAILABLE");
      else {
        int at = memory_save(&table, api, mem, hz[active]);
        ui_put(status, at >= 0 ? "MEMORY SAVED" : "SAVE FAILED");
      }
    } else {
      continue;
    }
    show(&ui, api, hz[0], hz[1], active, mem, entered, digits, status);
  }
  return ret;
}
