#!/usr/bin/env python3
"""Package a firmware body into a loadable .hfb by prepending the CRC-16 header.

The .hfb format is: [CRC-16 LE, 2 bytes] + body, where CRC-16 (reflected, poly 0x8408,
init 0xFFFF) is computed over the body. The official keymap tool and the on-device bootloader
verify it. See analysis/firmware/hfb-checksum.md.

    python3 gen/pack_hfb.py <body.bin> <out.hfb>

The body must already be the full image-after-the-2-CRC-bytes, including the model/version footer
(e.g. "AHJX01\\n" + version) that the tool checks. Building that body from our own firmware image is
a separate step (needs the exact footer offset/padding the bootloader expects).
"""
import sys


def hfb_crc16(data: bytes) -> int:
    crc = 0xFFFF
    for byte in data:
        crc ^= byte
        for _ in range(8):
            crc = (crc >> 1) ^ 0x8408 if crc & 1 else crc >> 1
    return crc & 0xFFFF


def pack(body: bytes) -> bytes:
    crc = hfb_crc16(body)
    return bytes([crc & 0xFF, (crc >> 8) & 0xFF]) + body


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    body = open(sys.argv[1], "rb").read()
    out = pack(body)
    open(sys.argv[2], "wb").write(out)
    print(f"wrote {sys.argv[2]}: {len(out)} bytes, CRC {out[0] | out[1] << 8:#06x}")
