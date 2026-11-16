/* PXK6 fixed-frame air-link codec, matching pixelqso.k6_air. SPDX-License-Identifier: MIT */
#ifndef K6_CARD_AIR_H
#define K6_CARD_AIR_H
#include <stdint.h>

#define K6_CA_FRAME_BYTES 16u
#define K6_CA_PAYLOAD_BYTES 8u
#define K6_CA_MAGIC 0xD6u
#define K6_CA_BEGIN 1u
#define K6_CA_DATA 2u
#define K6_CA_END 3u
#define K6_CA_ACK 4u
#define K6_CA_NAK 5u

typedef struct {
  uint8_t kind;
  uint16_t transfer_id;
  uint16_t sequence;
  uint8_t payload[K6_CA_PAYLOAD_BYTES];
} k6_card_air_frame_t;

/* Encodes/decode a complete 16-byte radio frame. CRC is CCITT-FALSE, LE on wire. */
int k6_card_air_encode(const k6_card_air_frame_t *frame, uint8_t out[K6_CA_FRAME_BYTES]);
int k6_card_air_decode(const uint8_t in[K6_CA_FRAME_BYTES], k6_card_air_frame_t *frame);
uint16_t k6_card_air_crc16(const uint8_t *data, unsigned bytes);

/* BEGIN/END payload helpers: record length LE16, record CRC32 LE, version 1, reserved 0. */
void k6_card_air_record_meta(uint8_t out[K6_CA_PAYLOAD_BYTES], uint16_t bytes, uint32_t crc32);

#endif
