/* k6_lib: the K6's SPI module library (see k6_lib.h). SPDX-License-Identifier: MIT */
#include "k6_lib.h"

static unsigned u16le(const uint8_t *p) { return (unsigned)p[0] | (unsigned)p[1] << 8; }

/* the header's own checks (k6_mod.c check() without the transfer): the image's length, or 0 */
static unsigned hdr_len(const uint8_t *a) {
  unsigned code = u16le(a + 4), entry = u16le(a + 6), total = KM_HDR + code + KM_TAG;
  if (a[0] != 'K' || a[1] != '6' || a[2] != 'M' || a[3] != KM_ABI || a[12] > KM_LEVEL || !code ||
      entry >= code || (entry & 1) || total > KL_SLOT_BYTES)
    return 0;
  return total;
}

int kl_install(const uint8_t *img, const kl_flash_t *fl) {
  unsigned total = hdr_len(img), slot = img[15], off, n;
  uint32_t base;
  uint8_t back[64];
  if (!total || !(img[13] & KM_F_LIB) || (img[13] & (KM_F_REMOVE | KM_F_THEME))) return KL_BAD_HDR;
  if (slot >= KL_SLOTS) return KL_SLOT;
  base = KL_SLOT_ADDR(slot);
  if (fl->read(base, back, 4)) return KL_IO;
  if (back[0]=='K' && back[1]=='6' && back[2]=='T') return KL_NOT_MODULE;
  /* only the sectors the image needs; a shorter image leaves 0xFF behind it in the last one */
  for (off = 0; off < total; off += KL_SECTOR)
    if (fl->erase(base + off)) return KL_IO;
  for (off = 0; off < total; off += n) {
    n = total - off < KL_PAGE ? total - off : KL_PAGE;
    if (fl->prog(base + off, img + off, n)) return KL_IO;
  }
  for (off = 0; off < total; off += n) {
    unsigned i;
    n = total - off < sizeof back ? total - off : (unsigned)sizeof back;
    if (fl->read(base + off, back, n)) return KL_IO;
    for (i = 0; i < n; i++)
      if (back[i] != img[off + i]) return KL_VERIFY;
  }
  return (int)total;
}

int kl_remove(int slot, const kl_flash_t *fl) {
  kl_info_t info;
  uint8_t check[64];
  uint32_t base;
  unsigned off, i;
  if (slot < 0 || slot >= KL_SLOTS) return KL_SLOT;
  if (kl_info(slot, fl, &info) != 0 || !(info.flags & KM_F_LIB) ||
      (info.flags & (KM_F_PAGE | KM_F_CARDS))) return KL_NOT_MODULE;
  base = KL_SLOT_ADDR(slot);
  /* Clear the full slot, including stale data beyond the previous image's final sector. */
  for (off = 0; off < KL_SLOT_BYTES; off += KL_SECTOR)
    if (fl->erase(base + off)) return KL_IO;
  for (off = 0; off < KL_SLOT_BYTES; off += sizeof check) {
    if (fl->read(base + off, check, sizeof check)) return KL_IO;
    for (i = 0; i < sizeof check; i++)
      if (check[i] != 0xFF) return KL_VERIFY;
  }
  return 0;
}

int kl_info(int slot, const kl_flash_t *fl, kl_info_t *out) {
  uint8_t h[KM_HDR + 4 + KL_NAME];
  unsigned i, blank = 1, named;
  if (slot < 0 || slot >= KL_SLOTS) return KL_SLOT;
  if (fl->read(KL_SLOT_ADDR(slot), h, sizeof h)) return KL_IO;
  for (i = 0; i < KM_HDR; i++) blank &= h[i] == 0xFF;
  if (blank) return KL_EMPTY;
  if (!hdr_len(h)) return KL_BAD_HDR;
  out->code_len = (uint16_t)u16le(h + 4), out->entry = (uint16_t)u16le(h + 6);
  out->serial = (uint32_t)h[8] | (uint32_t)h[9] << 8 | (uint32_t)h[10] << 16 | (uint32_t)h[11] << 24;
  out->level = h[12], out->flags = h[13];
  /* the name block: a module's (not a page's or a deck's), whole inside its code */
  named = !(h[13] & (KM_F_PAGE | KM_F_CARDS)) && out->code_len >= 4 + KL_NAME && h[16] == 'K' &&
          h[17] == '6' && h[18] == 'N' && h[19] == 'M';
  for (i = 0; i < KL_NAME; i++) out->name[i] = named ? (char)h[KM_HDR + 4 + i] : 0;
  return 0;
}

/* read slot n into dst and check its header and tag: the code length, or KL_* */
static int load(int slot, const kl_flash_t *fl, uint8_t *dst, unsigned cap, unsigned page) {
  unsigned total, code, flags;
  if (slot < 0 || slot >= KL_SLOTS) return KL_SLOT;
  if (cap < KM_HDR) return KL_BAD_HDR;
  /* Keep this path shallow: the Aura host calls kl_load from its keypad handler with little
     stack left. Calling kl_info here nested another C frame and a Rust SPI callback before the
     image was even read. Read the header into the destination, validate it, then load the image. */
  if (fl->read(KL_SLOT_ADDR(slot), dst, KM_HDR)) return KL_IO;
  total = hdr_len(dst);
  if (!total) return KL_BAD_HDR;
  code = u16le(dst + 4);
  flags = dst[13];
  if (!!(flags & KM_F_PAGE) != !!page || (flags & (KM_F_CARDS | KM_F_THEME))) return KL_BAD_HDR;
  if (total > cap) return KL_BAD_HDR;
  if (fl->read(KL_SLOT_ADDR(slot), dst, total)) return KL_IO;
  if (!hdr_len(dst) || dst[13] != flags) return KL_BAD_HDR;       /* changed between the two reads */
  if (km_tag_check(dst, code)) return KL_BAD_TAG;
  return (int)code;
}

int kl_load(int slot, const kl_flash_t *fl, uint8_t *dst, unsigned cap) {
  int r = load(slot, fl, dst, cap, 0);
  if (r > 0) km_arm(dst, 0);
  return r;
}

int kl_page(int slot, const kl_flash_t *fl, uint8_t *dst, unsigned cap) {
  return load(slot, fl, dst, cap, 1);
}
