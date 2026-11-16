/* Bounded, non-executable PXK6 card store. SPDX-License-Identifier: MIT */
#include "card_store.h"
#include <string.h>

static uint16_t be16(const uint8_t *p) { return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }

static int erased_sector(const pxk6_store_flash_t *f, uint32_t base) {
  uint8_t buf[64];
  unsigned off, i;
  for (off = 0; off < PXK6_STORE_SECTOR; off += sizeof buf) {
    if (f->read(base + off, buf, sizeof buf)) return -1;
    for (i = 0; i < sizeof buf; ++i) if (buf[i] != 0xFFu) return 0;
  }
  return 1;
}

static int record_at(const pxk6_store_flash_t *f, unsigned slot, uint8_t *scratch,
                     size_t scratch_bytes, size_t *record_bytes) {
  uint8_t header[PXK6_HEADER_BYTES];
  uint32_t base;
  size_t n;
  pxk6_card_t card;
  if (!f || !f->read || slot >= PXK6_STORE_SLOTS || !scratch) return -1;
  base = PXK6_STORE_BASE + slot * PXK6_STORE_SECTOR;
  if (f->read(base, header, sizeof header)) return -2;
  if (memcmp(header, "PXK6", 4) != 0 || header[4] != 1) return -3;
  n = PXK6_HEADER_BYTES + be16(header + 14) + PXK6_CRC_BYTES;
  if (n > PXK6_STORE_SECTOR || n > scratch_bytes || n > PXK6_MAX_RECORD_BYTES) return -4;
  if (f->read(base, scratch, (uint32_t)n) || pxk6_card_open(scratch, n, &card)) return -5;
  if (record_bytes) *record_bytes = n;
  return (int)n;
}

int pxk6_store_count(const pxk6_store_flash_t *f, uint8_t *scratch, size_t scratch_bytes) {
  unsigned slot;
  int count = 0;
  if (!f || !f->read || !scratch || scratch_bytes < PXK6_MAX_RECORD_BYTES) return -1;
  for (slot = 0; slot < PXK6_STORE_SLOTS; ++slot)
    if (record_at(f, slot, scratch, scratch_bytes, NULL) > 0) ++count;
  return count;
}

int pxk6_store_erase_slot(const pxk6_store_flash_t *f, unsigned slot) {
  uint32_t base;
  int erased;
  if (!f || !f->read || !f->erase || slot >= PXK6_STORE_SLOTS) return -1;
  base = PXK6_STORE_BASE + slot * PXK6_STORE_SECTOR;
  erased = erased_sector(f, base);
  if (erased < 0) return -2;
  if (!erased && f->erase(base)) return -3;
  erased = erased_sector(f, base);
  return erased == 1 ? 0 : -4;
}

int pxk6_store_put(const pxk6_store_flash_t *f, const uint8_t *record, size_t bytes,
                   uint8_t *scratch, size_t scratch_bytes) {
  unsigned slot;
  int free_slot = -1;
  pxk6_card_t card;
  if (!f || !f->read || !f->program || !record || !scratch ||
      scratch_bytes < 64 || bytes > PXK6_STORE_SECTOR ||
      pxk6_card_open(record, bytes, &card)) return -1;
  for (slot = 0; slot < PXK6_STORE_SLOTS; ++slot) {
    uint32_t base = PXK6_STORE_BASE + slot * PXK6_STORE_SECTOR;
    uint8_t header[PXK6_HEADER_BYTES];
    size_t off;
    int match = 1;
    if (f->read(base, header, sizeof header) == 0 &&
        memcmp(header, "PXK6", 4) == 0 && header[4] == 1 &&
        PXK6_HEADER_BYTES + be16(header + 14) + PXK6_CRC_BYTES == bytes) {
      for (off = 0; off < bytes; off += scratch_bytes) {
        size_t n = bytes - off < scratch_bytes ? bytes - off : scratch_bytes;
        if (f->read(base + (uint32_t)off, scratch, (uint32_t)n) ||
            memcmp(scratch, record + off, n) != 0) {
          match = 0;
          break;
        }
      }
      if (match) return (int)slot;
    }
    if (free_slot < 0) {
      int erased = erased_sector(f, base);
      if (erased < 0) return -2;
      if (erased) free_slot = (int)slot;
    }
  }
  if (free_slot < 0) return -3;
  {
    uint32_t base = PXK6_STORE_BASE + (uint32_t)free_slot * PXK6_STORE_SECTOR;
    size_t off;
    uint8_t verify[PXK6_STORE_PAGE];
    /* free_slot was checked byte-for-byte as erased; programming directly avoids wear. */
    for (off = 0; off < bytes; off += PXK6_STORE_PAGE) {
      size_t n = bytes - off < PXK6_STORE_PAGE ? bytes - off : PXK6_STORE_PAGE;
      if (f->program(base + (uint32_t)off, record + off, (uint32_t)n)) return -5;
    }
    for (off = 0; off < bytes; off += sizeof verify) {
      size_t n = bytes - off < sizeof verify ? bytes - off : sizeof verify;
      if (f->read(base + (uint32_t)off, verify, (uint32_t)n) ||
          memcmp(verify, record + off, n) != 0) return -6;
    }
  }
  return free_slot;
}

int pxk6_store_get(const pxk6_store_flash_t *f, unsigned slot, uint8_t *dst, size_t dst_bytes) {
  size_t n = 0;
  int r;
  if (!dst) return -1;
  r = record_at(f, slot, dst, dst_bytes, &n);
  return r > 0 ? (int)n : r;
}
