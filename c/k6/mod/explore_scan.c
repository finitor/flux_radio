/* EXPLORE: a sideloadable scan-and-rank module for Aura's module host.
   Reuses the original explorer's two-stage scanner and candidate grader, while keeping the
   whole UI and state in module memory. It scans receive-only and integrates the persistent
   repeater table through the host's bounded flash API.
   SPDX-License-Identifier: MIT */
#define K6_MODULE_LEVEL 6
#define K6_MODULE_OPT z
#include "../k6_mod.h"
#include "../xscan.h"
#define XS_MODULE_NO_REFINE
#define known rt_known_state
#include "../rt.c" /* rt_crc validates saved rows; the table journal stays in firmware images. */
#undef known

/* xscan.c and explore.c were separate core objects. Give xscan's private helpers a namespace
   when embedding both translation units into this one position-independent module. */
#define put xs_put
#define num xs_num
#define udiv xs_udiv
#define slot xs_slot
#include "../xscan.c"
#undef put
#undef num
#undef udiv
#undef slot
#include "../explore.c"

K6_MODULE_NAME("EXPLORE");

#define EX_CANDIDATES 6
#define EX_KNOWN 16
#define BAND_COUNT 3
#define WF_ROWS 1
#define WF_BYTES (WF_ROWS * 16)
#define GPIOB 0x48000400u
#define GPIOC 0x48000800u
#define GPIOF 0x48001400u
#define IDR 0x10u
#define ODR 0x14u
#define BSRR 0x18u
#define BRR 0x28u
#define KEYPAD_ROWS ((1u << 0) | (1u << 4) | (1u << 9) | (1u << 10) | (1u << 11))

typedef struct {
  xs_t scan;
  ex_t candidates;
  ex_cand_t entries[EX_CANDIDATES];
  uint32_t known_hz[EX_KNOWN];
  /* Original ALL set: 400 + 60 + 400 bins and one 128-column scan trace. */
  uint8_t scan_mem[988];
  uint8_t waterfall[WF_BYTES];
  uint32_t now, last_flush;
  uint8_t head, band, list, selected, raw_key, stable_key, key_reads;
  char line[28];
} explore_t;


typedef struct {
  uint32_t lo, step, count;
  uint16_t snap;
} segment_t;

typedef struct {
  char name[6];
  uint8_t nseg;
  segment_t seg[3];
} band_t;

static const band_t BANDS[] = {
    {"ALL", 3, {{144000000u, 10000u, 400u, 5000u},
                 {223800000u, 20000u, 60u, 20000u},
                 {440000000u, 12500u, 400u, 12500u}}},
    {"2M", 1, {{144000000u, 10000u, 400u, 5000u}}},
    {"70CM", 2, {{440000000u, 12500u, 400u, 12500u},
                  {445000000u, 12500u, 400u, 12500u}}},
    {"1.25M", 1, {{222000000u, 20000u, 150u, 20000u}}},
};

static const uint8_t KEYS[24] = {
    0, 'A', 0, 'B', '7', '8', '#', '9', '4', '5', '0', '6',
    '1', '2', '*', '3', 'M', 'U', 'X', 'D', 'V', 'W', 0, 'N'};
static const uint8_t ROWPIN[6] = {0xFF, 0, 4, 10, 11, 9};

/* Add a new record without erasing or editing existing entries. Keep one wholly erased sector
   as the table's recovery reserve; when the other sectors fill, refuse safely and leave the
   journal untouched for the full table manager. */
#ifdef K6_EXPLORE_ENABLE_TABLE_SAVE
static int save_candidate(const k6_api_t *api, const ex_cand_t *c) {
  rt_rec_t rec;
  uint32_t addr, max_wseq = 0;
  uint16_t max_id = 0;
  unsigned sector, slot, spare = RT_SECTORS, append = RT_SLOTS;
  for (sector = 0; sector < RT_SECTORS; sector++) {
    int all_blank = 1;
    unsigned first_blank = RT_SLOTS;
    for (slot = 0; slot < RT_SLOTS_PER_SECTOR; slot++) {
      uint32_t index = sector * RT_SLOTS_PER_SECTOR + slot;
      uint32_t delta;
      addr = RT_BASE + index * RT_REC;
      if (api->fl_read(addr, &rec, sizeof rec) < 0) return -1;
      if (blank(&rec)) {
        if (first_blank == RT_SLOTS) first_blank = index;
        continue;
      }
      all_blank = 0;
      if (!rt_known_state(rec.state) ||
          ((rec.state & 0xFFu) == RT_ST_FREE) ||
          ((rec.state & 0xFFu) == RT_ST_VALID && !good(&rec))) return -2;
      if (rec.crc == rt_crc(&rec) && rec.id && rec.id != 0xFFFF && rec.id > max_id)
        max_id = rec.id;
      if (rec.crc == rt_crc(&rec) && (int32_t)(rec.wseq - max_wseq) > 0)
        max_wseq = rec.wseq;
      if (good(&rec) && !(rec.flags & RT_F_VFO)) {
        delta = rec.rx_hz > c->hz ? rec.rx_hz - c->hz : c->hz - rec.rx_hz;
        if (delta <= 5000u) return -4;
      }
    }
    if (all_blank) spare = sector;
    else if (append == RT_SLOTS && first_blank != RT_SLOTS)
      append = first_blank;
  }
  if (spare == RT_SECTORS || append == RT_SLOTS || max_id >= 0xFFFE) return -3;
  addr = RT_BASE + append * RT_REC;
  ex_to_rt(c, &rec);
  rec.state = 0xFFFFu;
  rec.seq = 1;
  rec.id = (uint16_t)(max_id + 1u);
  rec.wseq = max_wseq + 1u;
  rec.spare0 = 0;
  rec.crc = rt_crc(&rec);
  {
    uint8_t state[2] = {0xFEu, 0xFFu};
    if (api->fl_prog(addr, state, 2) < 0 ||
        api->fl_prog(addr + 2, (const uint8_t *)&rec + 2, RT_REC - 2) < 0)
      return -1;
    state[0] = 0xFCu;
    if (api->fl_prog(addr, state, 2) < 0) return -1;
  }
  return (int)append;
}
#endif

static uint32_t mmio_read(uint32_t addr) { return *(volatile uint32_t *)addr; }
static void mmio_write(uint32_t addr, uint32_t value) { *(volatile uint32_t *)addr = value; }

static int keypad_scan(const k6_api_t *api) {
  int phase, key = 0;
  for (phase = 0; phase < 6 && !key; phase++) {
    uint32_t col;
    mmio_write(GPIOB + BSRR, KEYPAD_ROWS);
    if (phase) mmio_write(GPIOB + BRR, 1u << ROWPIN[phase]);
    api->delay_us(5);
    if (!(mmio_read(GPIOC + IDR) & (1u << 13))) col = 0;
    else if (!(mmio_read(GPIOC + IDR) & (1u << 14))) col = 1;
    else if (!(mmio_read(GPIOF + IDR) & (1u << 6))) col = 2;
    else if (!(mmio_read(GPIOB + IDR) & (1u << 14))) col = 3;
    else continue;
    key = KEYS[4 * phase + col];
  }
  mmio_write(GPIOB + BSRR, KEYPAD_ROWS);
  return key;
}

/* Require two identical scans before accepting a press or release. */
static int keypad_event(explore_t *s, const k6_api_t *api) {
  int key = keypad_scan(api);
  if (key != s->raw_key) {
    s->raw_key = (uint8_t)key;
    s->key_reads = 1;
    return 0;
  }
  if (s->key_reads < 2) s->key_reads++;
  if (s->key_reads == 2 && key != s->stable_key) {
    s->stable_key = (uint8_t)key;
    return key;
  }
  return 0;
}

static char *append(char *p, const char *text) {
  while (*text) *p++ = *text++;
  return p;
}

static char *decimal(char *p, uint32_t value, unsigned min_digits) {
  char tmp[10];
  unsigned n = 0;
  do {
    uint32_t q = xs_udiv(value, 10u);
    tmp[n++] = (char)('0' + value - q * 10u);
    value = q;
  } while (value || n < min_digits);
  while (n) *p++ = tmp[--n];
  return p;
}

static char *frequency(char *p, uint32_t hz) {
  uint32_t mhz = xs_udiv(hz, 1000000u);
  uint32_t khz = xs_udiv(hz - mhz * 1000000u, 1000u);
  p = decimal(p, mhz, 1);
  *p++ = '.';
  p = decimal(p, khz, 3);
  return p;
}

static void line_end(char *p) { *p = 0; }

static void screen_scan(explore_t *s, const k6_api_t *api) {
  xs_info_t info;
  char *p;
  unsigned i;
  if (api->level < 6) return;
  xs_info(&s->scan, &info);
  api->lcd_wf(s->waterfall, WF_ROWS, s->head);
  api->lcd_text(0, "EXPLORE / BAND SCAN");
  p = append(s->line, BANDS[s->band].name);
  p = append(p, " ");
  p = frequency(p, api->rx_hz());
  p = append(p, " SW");
  p = decimal(p, info.sweeps, 1);
  line_end(p);
  api->lcd_text(1, s->line);
  for (i = 2; i <= 4; i++) api->lcd_text((int)i, "");
  api->lcd_text(5, "MENU list BAND next");
  api->lcd_flush();
  s->last_flush = api->ms();
}

static void screen_list(explore_t *s, const k6_api_t *api) {
  ex_cand_t *c;
  char *p;
  unsigned i, first = s->selected > 4 ? s->selected - 4 : 0;
  if (api->level < 6) return;
  api->lcd_wf(0, 0, 0);
  api->lcd_text(0, "EXPLORE / REPEATERS");
  for (i = 0; i < 5; i++) {
    c = ex_view(&s->candidates, first + i);
    if (!c) {
      api->lcd_text((int)i + 1, i == 0 ? "No candidates yet" : "");
      continue;
    }
    char *p = s->line;
    *p++ = s->selected == first + i ? '>' : ' ';
    *p++ = c->grade;
    *p++ = ' ';
    p = frequency(p, c->hz);
    *p++ = ' ';
    p = decimal(p, c->overs, 1);
    *p++ = 'x';
    if (c->flags & EX_F_KNOWN) *p++ = '*';
    if (c->call[0]) {
      *p++ = ' ';
      p = append(p, c->call);
    }
    line_end(p);
    api->lcd_text((int)i + 1, s->line);
  }
  p = append(s->line, "UP/DN MENU EXIT; SAVE pending");
  line_end(p);
  api->lcd_text(5, s->line);
  api->lcd_flush();
  s->last_flush = api->ms();
}

static int start_band(explore_t *s, const k6_api_t *api, unsigned mode) {
  unsigned i;
  const band_t *b = &BANDS[mode];
  unsigned n = b->nseg;
  xs_defaults(&s->scan);
  s->scan.nseg = (uint8_t)n;
  /* All configured ranges already use their intended channel raster. Skip the optional
     31-sample frequency refinement to keep the module's 1,152-byte execution stack generous. */
  s->scan.refine = 0;
  s->scan.quiet = 1;
  s->scan.say_rows = 0;
  s->scan.peek_ms = 0;
  for (i = 0; i < n; i++) {
    s->scan.seg[i].lo_hz = b->seg[i].lo;
    s->scan.seg[i].step_hz = b->seg[i].step;
    s->scan.seg[i].nbins = (uint16_t)b->seg[i].count;
    s->scan.seg[i].snap_hz = b->seg[i].snap;
  }
  s->band = (uint8_t)mode;
  return xs_init(&s->scan, api, &s->candidates, s->scan_mem, sizeof s->scan_mem);
}

static void waterfall_row(explore_t *s) {
  uint8_t *dst = s->waterfall + (unsigned)s->head * 16u;
  unsigned x;
  for (x = 0; x < 16; x++) dst[x] = 0;
  for (x = 0; x < s->scan.cols && x < 128; x++) {
    /* A confirmed/stronger scan bin is a bright pixel in the rolling waterfall. */
    if (s->scan.row[x] >= 5) dst[x >> 3] |= (uint8_t)(0x80u >> (x & 7));
  }
  s->head = 0;
}

/* Park on a candidate while retaining the scan state. The keypad remains live and returns to
   the current scan; xs_resume refreshes the segment floor before judging further bins. */
static void try_frequency(explore_t *s, const k6_api_t *api, ex_cand_t *c) {
  char *p;
  api->tune(c->hz, 1);
  api->say("EXPLORE Try; key to resume scan");
  if (api->level >= 6) {
    api->lcd_wf(0, 0, 0);
    api->lcd_text(0, "EXPLORE / TRY");
    p = frequency(s->line, c->hz);
    line_end(p);
    api->lcd_text(1, s->line);
    api->lcd_text(5, "Key resumes scan");
    api->lcd_flush();
  }
  /* Let the key that opened Try be released before accepting its return key. */
  while (keypad_event(s, api) != 0) api->delay_us(10000);
  for (;;) {
    if (keypad_event(s, api) != 0) break;
    api->delay_us(10000);
  }
  xs_resume(&s->scan);
  api->say("EXPLORE scan resumed");
  screen_scan(s, api);
}

int k6_main(const k6_api_t *api) {
  explore_t *s;
  uint32_t bytes;
  uint8_t *mem;
  int result, key;
  if (api->level < 6) return -3;
  mem = api->scratch(&bytes);
  if (!mem || bytes < sizeof(explore_t)) return -8;
  s = (explore_t *)mem;
  for (uint32_t i = 0; i < sizeof *s; i++) ((uint8_t *)s)[i] = 0;
  ex_init(&s->candidates, s->entries, EX_CANDIDATES);
#ifdef K6_EXPLORE_SIM_FIXTURE
  /* Deterministic UI fixture only: the simulator has no RF stimulus source. */
  s->entries[0].hz = 146940000u;
  s->entries[0].overs = 3;
  s->entries[0].lo = -82;
  s->entries[0].hi = -80;
  s->entries[0].grade = 'R';
  s->entries[0].score = 8;
  s->entries[0].last_ms = api->ms();
  s->candidates.n = 1;
#endif
  if (api->level >= 5 && api->fl_read) {
    rt_rec_t rec;
    ex_known_store(&s->candidates, s->known_hz, EX_KNOWN);
    for (uint32_t addr = RT_BASE; addr < RT_BASE + RT_SLOTS * RT_REC; addr += RT_REC) {
      if (api->fl_read(addr, &rec, sizeof rec) < 0) break;
      if ((rec.state & 0xFFu) == RT_ST_VALID && rt_crc(&rec) == rec.crc && rec.rx_hz)
        ex_know(&s->candidates, rec.rx_hz);
    }
    api->say("EXPLORE saved repeater scan ready");
  } else api->say("EXPLORE table read unavailable");
  result = start_band(s, api, 0);
  if (result) return result;
  api->say("EXPLORE band ALL");
  api->say("EXPLORE scan/list started; RX only");
  screen_scan(s, api);
  for (;;) {
    result = xs_step(&s->scan);
    if (result == XS_ROW) {
      waterfall_row(s);
      s->now = api->ms();
      if (s->list) screen_list(s, api);
      else if (s->now - s->last_flush >= 250) screen_scan(s, api);
    }
    key = keypad_event(s, api);
    if (key == 'X') break;
    if (key == 'M') {
      s->list = (uint8_t)!s->list;
      api->say(s->list ? "EXPLORE candidate list" : "EXPLORE waterfall scan");
      if (s->list) screen_list(s, api);
      else screen_scan(s, api);
    } else if (key == 'N') {
      xs_close(&s->scan);
      unsigned next_band = (unsigned)s->band + 1u;
      if (next_band > BAND_COUNT) next_band = 0;
      result = start_band(s, api, next_band);
      if (result) break;
      api->say(next_band == 0 ? "EXPLORE band ALL" :
               next_band == 1 ? "EXPLORE band 2M" :
               next_band == 2 ? "EXPLORE band 70CM" : "EXPLORE band 1.25M");
      s->head = 0;
      for (uint32_t i = 0; i < sizeof s->waterfall; i++) s->waterfall[i] = 0;
      screen_scan(s, api);
    } else if (s->list && key == 'U' && s->selected) {
      s->selected--;
      screen_list(s, api);
    } else if (s->list && key == 'D' && s->selected + 1 < ex_view_n(&s->candidates)) {
      s->selected++;
      screen_list(s, api);
    } else if (s->list && key == 'A') {
      ex_cand_t *c = ex_view(&s->candidates, s->selected);
      if (c) try_frequency(s, api, c);
      else api->say("EXPLORE select a candidate first");
    }
#ifdef K6_EXPLORE_ENABLE_TABLE_SAVE
    else if (s->list && key == '5') {
      ex_cand_t *c = ex_view(&s->candidates, s->selected);
      if (!c) api->say("EXPLORE select a candidate first");
      else if (!api->fl_prog || !api->fl_read) api->say("EXPLORE table unavailable");
      else if (c->flags & EX_F_KNOWN)
        api->say("EXPLORE candidate already saved");
      else {
        result = save_candidate(api, c);
        if (result >= 0) {
          ex_know(&s->candidates, c->hz);
          api->say("EXPLORE candidate saved to table");
          screen_list(s, api);
        } else if (result == -2) api->say("EXPLORE table not valid");
        else if (result == -4) api->say("EXPLORE candidate already saved");
        else if (result == -3) api->say("EXPLORE table full");
        else api->say("EXPLORE table save failed");
      }
    }
#endif
  }
  xs_close(&s->scan);
  xs_summary(&s->scan);
  if (api->level >= 6) {
    api->lcd_wf(0, 0, 0);
    api->lcd_text(0, "EXPLORE stopped");
    api->lcd_text(1, "MENU opens list");
    api->lcd_text(5, "Exit returns to Aura");
    api->lcd_flush();
  }
  return (int)s->scan.sweeps;
}
