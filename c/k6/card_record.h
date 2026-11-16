/* PXK6 lossless PixelQSO card record reader. SPDX-License-Identifier: MIT */
#ifndef K6_CARD_RECORD_H
#define K6_CARD_RECORD_H
#include <stddef.h>
#include <stdint.h>

#define PXK6_HEADER_BYTES 16u
#define PXK6_CRC_BYTES 4u
#define PXK6_MAX_WIDTH 64u
#define PXK6_MAX_HEIGHT 64u
#define PXK6_MAX_RECORD_BYTES 2800u
#define PXK6_FLAG_ANIMATION 0x01u

typedef struct {
  const uint8_t *record;
  const uint8_t *callsign;
  const uint8_t *grid;
  const uint8_t *palette; /* RGB444 triples, one byte per channel */
  const uint8_t *raster;  /* row-major, packed most-significant-bit first */
  const uint8_t *animation; /* optional: first ID, frame ms, 8-byte digest */
  uint16_t record_bytes;
  uint16_t card_id;
  uint16_t payload_bytes;
  uint8_t width, height, palette_count, bits_per_pixel;
  uint8_t callsign_bytes, grid_bytes, flags;
} pxk6_card_t;

/* Validates the complete record and returns zero-copy views into it. */
int pxk6_card_open(const uint8_t *record, size_t bytes, pxk6_card_t *out);

/* Draws a centered, ordered-dithered preview into page-format LCD memory.
   Output is height rows of ceil(width/8) bytes; set bits are dark pixels. */
int pxk6_card_preview(const pxk6_card_t *card, uint8_t *out,
                      unsigned width, unsigned height);

uint32_t pxk6_crc32(const uint8_t *data, size_t bytes);
#endif
