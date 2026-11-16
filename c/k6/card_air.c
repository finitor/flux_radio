/* PXK6 fixed-frame air-link codec, matching pixelqso.k6_air. SPDX-License-Identifier: MIT */
#include "card_air.h"
#ifndef K6_MODULE_NO_LIBC
#include <string.h>
#endif

uint16_t k6_card_air_crc16(const uint8_t *data, unsigned bytes) {
  uint16_t crc = 0xFFFFu;
  unsigned i, bit;
  if (!data) return 0;
  for (i = 0; i < bytes; ++i) {
    crc ^= (uint16_t)data[i] << 8;
    for (bit = 0; bit < 8; ++bit)
      crc = (uint16_t)((crc & 0x8000u) ? (crc << 1) ^ 0x1021u : crc << 1);
  }
  return crc;
}

static int valid_kind(uint8_t kind) {
  return kind >= K6_CA_BEGIN && kind <= K6_CA_NAK;
}

int k6_card_air_encode(const k6_card_air_frame_t *f, uint8_t out[K6_CA_FRAME_BYTES]) {
  uint16_t crc;
  if (!f || !out || !valid_kind(f->kind)) return -1;
  out[0] = K6_CA_MAGIC;
  out[1] = f->kind;
  out[2] = (uint8_t)f->transfer_id;
  out[3] = (uint8_t)(f->transfer_id >> 8);
  out[4] = (uint8_t)f->sequence;
  out[5] = (uint8_t)(f->sequence >> 8);
  memcpy(out + 6, f->payload, K6_CA_PAYLOAD_BYTES);
  crc = k6_card_air_crc16(out, 14);
  out[14] = (uint8_t)crc;
  out[15] = (uint8_t)(crc >> 8);
  return 0;
}

int k6_card_air_decode(const uint8_t in[K6_CA_FRAME_BYTES], k6_card_air_frame_t *f) {
  uint16_t crc;
  if (!in || !f || in[0] != K6_CA_MAGIC || !valid_kind(in[1])) return -1;
  crc = k6_card_air_crc16(in, 14);
  if (in[14] != (uint8_t)crc || in[15] != (uint8_t)(crc >> 8)) return -2;
  memset(f, 0, sizeof(*f));
  f->kind = in[1];
  f->transfer_id = (uint16_t)(in[2] | (uint16_t)in[3] << 8);
  f->sequence = (uint16_t)(in[4] | (uint16_t)in[5] << 8);
  memcpy(f->payload, in + 6, K6_CA_PAYLOAD_BYTES);
  return 0;
}

void k6_card_air_record_meta(uint8_t out[K6_CA_PAYLOAD_BYTES], uint16_t bytes, uint32_t crc32) {
  if (!out) return;
  out[0] = (uint8_t)bytes;
  out[1] = (uint8_t)(bytes >> 8);
  out[2] = (uint8_t)crc32;
  out[3] = (uint8_t)(crc32 >> 8);
  out[4] = (uint8_t)(crc32 >> 16);
  out[5] = (uint8_t)(crc32 >> 24);
  out[6] = 1;
  out[7] = 0;
}
