/* PXK6 lossless PixelQSO card record reader. SPDX-License-Identifier: MIT */
#include "card_record.h"
#ifndef K6_MODULE_NO_LIBC
#include <string.h>
#endif

static uint16_t be16(const uint8_t *p) { return (uint16_t)((uint16_t)p[0] << 8 | p[1]); }
static uint32_t be32(const uint8_t *p) {
  return (uint32_t)p[0] << 24 | (uint32_t)p[1] << 16 | (uint32_t)p[2] << 8 | p[3];
}
static unsigned bits_for_palette(unsigned n) {
  switch (n) {
  case 2: return 1;
  case 8: return 3;
  case 16: return 4;
  case 32: return 5;
  default: return 0;
  }
}

uint32_t pxk6_crc32(const uint8_t *data, size_t bytes) {
  uint32_t crc = 0xFFFFFFFFu;
  size_t i;
  unsigned b;
  for (i = 0; i < bytes; ++i) {
    crc ^= data[i];
    for (b = 0; b < 8; ++b)
      crc = (crc >> 1) ^ ((crc & 1u) ? 0xEDB88320u : 0u);
  }
  return crc ^ 0xFFFFFFFFu;
}

int pxk6_card_open(const uint8_t *r, size_t bytes, pxk6_card_t *out) {
  unsigned palette_count, bits, width, height, call_len, grid_len, flags;
  unsigned raster_bytes, anim_bytes, payload_bytes, expected, i, bitpos;
  const uint8_t *palette, *raster, *animation;
  if (!r || !out || bytes < PXK6_HEADER_BYTES + PXK6_CRC_BYTES ||
      bytes > PXK6_MAX_RECORD_BYTES || memcmp(r, "PXK6", 4) != 0 || r[4] != 1)
    return -1;
  flags = r[5];
  if (flags & (uint8_t)~PXK6_FLAG_ANIMATION) return -2;
  width = r[8]; height = r[9]; palette_count = r[10]; bits = r[11];
  call_len = r[12]; grid_len = r[13]; payload_bytes = be16(r + 14);
  if (!width || width > PXK6_MAX_WIDTH || !height || height > PXK6_MAX_HEIGHT ||
      bits_for_palette(palette_count) != bits || call_len > 12 || grid_len > 8)
    return -3;
  raster_bytes = (width * height * bits + 7u) / 8u;
  anim_bytes = (flags & PXK6_FLAG_ANIMATION) ? 12u : 0u;
  expected = call_len + grid_len + palette_count * 3u + raster_bytes + anim_bytes;
  if (payload_bytes != expected || bytes != PXK6_HEADER_BYTES + expected + PXK6_CRC_BYTES)
    return -4;
  if (pxk6_crc32(r, bytes - PXK6_CRC_BYTES) != be32(r + bytes - PXK6_CRC_BYTES))
    return -5;
  for (i = 0; i < call_len + grid_len; ++i)
    if (r[PXK6_HEADER_BYTES + i] > 0x7Fu) return -6;
  palette = r + PXK6_HEADER_BYTES + call_len + grid_len;
  for (i = 0; i < palette_count * 3u; ++i)
    if (palette[i] > 15) return -7;
  raster = palette + palette_count * 3u;
  /* Palette depths are dense powers of two except 3-bit (also exactly 8 colors),
     but still reject malformed indices explicitly so this remains robust to format growth. */
  for (i = 0, bitpos = 0; i < width * height; ++i) {
    unsigned j, index = 0;
    for (j = 0; j < bits; ++j, ++bitpos)
      index = (index << 1) | ((raster[bitpos >> 3] >> (7u - (bitpos & 7u))) & 1u);
    if (index >= palette_count) return -8;
  }
  if ((width * height * bits) & 7u) {
    unsigned unused = 8u - ((width * height * bits) & 7u);
    if (raster[raster_bytes - 1] & ((1u << unused) - 1u)) return -9;
  }
  animation = anim_bytes ? raster + raster_bytes : NULL;
  if (animation) {
    unsigned first = be16(animation), duration = be16(animation + 2);
    if (first == be16(r + 6) || duration < 100 || duration > 10000) return -10;
  }
  memset(out, 0, sizeof(*out));
  out->record = r;
  out->callsign = r + PXK6_HEADER_BYTES;
  out->grid = out->callsign + call_len;
  out->palette = palette;
  out->raster = raster;
  out->animation = animation;
  out->record_bytes = (uint16_t)bytes;
  out->card_id = be16(r + 6);
  out->payload_bytes = (uint16_t)payload_bytes;
  out->width = (uint8_t)width; out->height = (uint8_t)height;
  out->palette_count = (uint8_t)palette_count; out->bits_per_pixel = (uint8_t)bits;
  out->callsign_bytes = (uint8_t)call_len; out->grid_bytes = (uint8_t)grid_len;
  out->flags = (uint8_t)flags;
  return 0;
}

static unsigned round_even(unsigned numerator, unsigned denominator) {
  unsigned q = numerator / denominator, r = numerator % denominator;
  if (r * 2u > denominator || (r * 2u == denominator && (q & 1u))) ++q;
  return q;
}

int pxk6_card_preview(const pxk6_card_t *c, uint8_t *out, unsigned width, unsigned height) {
  static const uint8_t bayer[4][4] = {
      {0, 8, 2, 10}, {12, 4, 14, 6}, {3, 11, 1, 9}, {15, 7, 13, 5}};
  unsigned scale_num, scale_den, draw_w, draw_h, left, top, stride, y, x;
  if (!c || !c->record || !out || !width || !height || width > 256 || height > 256) return -1;
  stride = (width + 7u) / 8u;
  memset(out, 0, stride * height);
  if (width * c->height <= height * c->width) {
    scale_num = width; scale_den = c->width;
    draw_w = width;
    draw_h = round_even((unsigned)c->height * scale_num, scale_den);
  } else {
    scale_num = height; scale_den = c->height;
    draw_h = height;
    draw_w = round_even((unsigned)c->width * scale_num, scale_den);
  }
  if (!draw_w) draw_w = 1;
  if (!draw_h) draw_h = 1;
  left = (width - draw_w) / 2u; top = (height - draw_h) / 2u;
  for (y = 0; y < draw_h; ++y) {
    unsigned sy = ((unsigned)y * scale_den) / scale_num;
    if (sy >= c->height) sy = c->height - 1u;
    for (x = 0; x < draw_w; ++x) {
      unsigned sx = ((unsigned)x * scale_den) / scale_num;
      unsigned index, bitpos = (sy * c->width + sx) * c->bits_per_pixel;
      unsigned j, rgb, luminance, tx = left + x, ty = top + y;
      if (sx >= c->width) sx = c->width - 1u;
      bitpos = (sy * c->width + sx) * c->bits_per_pixel;
      index = 0;
      for (j = 0; j < c->bits_per_pixel; ++j, ++bitpos)
        index = (index << 1) | ((c->raster[bitpos >> 3] >> (7u - (bitpos & 7u))) & 1u);
      rgb = index * 3u;
      luminance = round_even((299u * c->palette[rgb] + 587u * c->palette[rgb + 1] +
                              114u * c->palette[rgb + 2]) * 17u, 1000u);
      if (luminance < (unsigned)bayer[ty & 3u][tx & 3u] * 16u + 8u)
        out[ty * stride + tx / 8u] |= (uint8_t)(1u << (7u - (tx & 7u)));
    }
  }
  return 0;
}
