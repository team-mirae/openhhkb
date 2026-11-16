/* HHKB .hfb firmware checksum: CRC-16 (reflected, poly 0x8408, init 0xFFFF, no final XOR),
 * computed over the file excluding its first 2 bytes. Those 2 bytes store this CRC, little-endian.
 *
 * Verified: reproduces the stored header of every official image we have, and the official keymap
 * tool accepts a custom .hfb carrying this CRC and rejects one whose CRC is wrong (see
 * analysis/firmware/hfb-checksum.md). Algorithm from the checksum analysis report (user-provided),
 * independently re-derived here; no vendor code is included. */
#ifndef HHKB_HFB_CRC_H
#define HHKB_HFB_CRC_H

#include <stdint.h>
#include <stddef.h>

static inline uint16_t hfb_crc16(const uint8_t *data, size_t len) {
    uint16_t crc = 0xFFFF;
    for (size_t i = 0; i < len; i++) {
        crc ^= data[i];
        for (int b = 0; b < 8; b++)
            crc = (crc & 1) ? (uint16_t)((crc >> 1) ^ 0x8408) : (uint16_t)(crc >> 1);
    }
    return crc;
}

#endif
