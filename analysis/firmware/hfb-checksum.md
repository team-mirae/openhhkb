# `.hfb` firmware checksum (CRC-16) — verified

The first 2 bytes of an `.hfb` file are a **CRC-16** over the rest of the file. The official keymap tool
(and the on-device bootloader) reject an image whose CRC does not match, so a custom `.hfb` must carry a
correct CRC to load.

## Algorithm

| Parameter | Value |
|---|---|
| Width | 16 bits |
| Polynomial | `0x8408` (reflected form of `0x1021`, CRC-16/CCITT) |
| Init | `0xFFFF` |
| Reflected in/out | yes |
| Final XOR | none |
| Data covered | the whole file **except the first 2 bytes** |
| Stored as | the first 2 bytes, little-endian |

Reference implementations: `firmware-src/src/hfb_crc.h` (C, used on-device/in tests) and
`firmware-src/gen/pack_hfb.py` (`hfb_crc16` + a `.hfb` packer).

Origin: the algorithm came from a user-provided checksum analysis report (reverse-engineered from the
keymap tool's `CRC16.getCRC16`). It was **independently re-derived and verified here** — no vendor code is
included.

## Verification

**Against the official images** — `make test` step [6] recomputes the CRC in C over `file[2:]` and checks it
equals the stored header:

```
HHKB800_FW_A048.hfb   : C CRC 3b01 == stored 3b01
HHKB820_FW_JP_A249.hfb: C CRC 4124 == stored 4124
```

**Against the official keymap tool** (driven in the throwaway VM, 2026-11-16). Two files were built from the
A2.49 image with one payload byte changed, differing only in the 2-byte CRC header:

| File | CRC header | Tool result |
|---|---|---|
| `…_badcrc.hfb` | original `0x2441` (now wrong) | **rejected**: "This firmware data cannot be applied to this model." (`…-badcrc-rejected.png`) |
| `…_goodcrc.hfb` | `0x0095`, computed by our algorithm | **accepted**: shows "Updated firmware version : A2.49", enables "Write to HHKB" (`…-goodcrc-accepted.png`) |

The payloads are identical; only the CRC differs. The tool accepting a CRC that **only our algorithm produced**
confirms both the algorithm and that the CRC is the integrity gate (no signature/encryption). Evidence
screenshots are in `../hhkb-hybrid-jis/captures/`.

## Consequence for the recovery firmware

An image our firmware build produces can be wrapped with `pack_hfb.py` into a `.hfb` the tool and bootloader
accept — the last missing piece for distributing an installable recovery image. Still needed to build a full
loadable image of *our own* firmware: the exact footer the tool/bootloader checks (model id `AHJX01` + version)
and its offset/padding, plus the 2 bytes at file offset 2–3 that precede the vector table.
