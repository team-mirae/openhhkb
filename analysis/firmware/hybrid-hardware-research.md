# HHKB Hybrid internal hardware — research (NOT CONFIRMED)

> **Status: UNCONFIRMED.** None of this has been checked against the physical board. It combines our own
> firmware-binary analysis (strong, but still inferred) with web research (FCC filings, community RE). Treat every
> part number as a hypothesis until someone opens a Hybrid and reads the silkscreen, or an official FCC internal-photo
> exhibit confirms it. Date: 2026-11-17.

## Main MCU — likely STM32F0 (Cortex-M0), ~STM32F072CB / F070CB

Inferred from the firmware binary (`HHKB820_FW_JP_A249.hfb`); see `hardware-id.md` for the raw evidence.

- Cortex-M0, **48-entry vector table = 16 core + 32 IRQs** (the 32-IRQ count is the STM32F0 signature; F1 is M3, F3/F4 more).
- STM32 memory map: flash at `0x08000000`, **application at `0x08010000`**, RCC referenced at `0x40021000`
  (an nRF would map flash at `0x00000000`).
- 128 KB flash (64 KB bootloader + 64 KB app), ≥16 KB RAM, USB FS → **STM32F072CB** (crystalless USB via HSI48) or
  **STM32F070CB** (needs an external crystal). Not distinguishable from the binary alone.
- Role: Topre capacitive sensing (ADC), USB, keymap, firmware update.
- Caveat: a third-party research note guessed "STM32F1-class"; the 32-IRQ table from the actual binary argues against
  that (M0, not M3). Still unconfirmed either way.

## Bluetooth — possibly Taiyo Yuden EYSHCN module (Nordic nRF52832)

Inferred from an FCC-ID lead, **weaker** than the MCU evidence.

- A retailer listing gives the Hybrid Type-S radio FCC ID as **RYYEYSHCN** = Taiyo Yuden **EYSHCN** "Bluetooth Smart /
  ANT" module. I could not verify this against an official PFU FCC grant.
- The EYSHCN series (e.g. EYSHCNZXZ) is built on the **Nordic nRF52832** — Cortex-M4F, BLE 4.2 + ANT, 512 KB flash,
  64 KB RAM.
- Implication (if true): BLE runs on a **separate radio co-processor**, not the main STM32. Consistent with the vendor
  tool exposing separate BT-firmware commands (seen in the Studio tool's `commandGetBTVersion`).
- Unconfirmed: that the Hybrid actually uses this module, and the exact EYSHCN variant / nRF part.

## Firmware / flash architecture (inferred)

- **Dual-bank with bootloader recovery**: app at `0x08010000` + a backup bank. The Classic RE
  (`m1sk9/HHKB-reverse-engineering`) documents `UPDATEBOOT_*` commands (`0xE4`–`0xE7`) that rewrite the backup bank;
  whether the Hybrid shares this is unconfirmed.
- `.hfb` container: 2-byte **CRC-16** header (reflected, poly `0x8408`, over `file[2:]`) — this part **is** verified
  (`hfb-checksum.md`). Plain unencrypted ARM image; `AHJX01` model-ID + version footer.

## How to confirm

1. Open a Hybrid; read the two main chip silkscreens (main MCU + radio module).
2. Find the Hybrid's own FCC internal-photo exhibit. The **Studio's** are public (`fccid.io/FPJPD-ID100`); the Hybrid's
   were not located.
3. On the board: confirm F072 vs F070 by presence/absence of an external USB crystal; confirm the radio part directly.

## Sources

- Our firmware analysis: `analysis/firmware/hardware-id.md`, `hfb-checksum.md`.
- Taiyo Yuden EYSHCN datasheet (EYSHCNZXZ → nRF52832).
- FCC ID RYYEYSHCN (Taiyo Yuden EYSHCN module).
- `github.com/m1sk9/HHKB-reverse-engineering` (Classic PD-KB401 protocol/bank notes).
- HHKB Studio FCC internal photos: `fccid.io/FPJPD-ID100`.
