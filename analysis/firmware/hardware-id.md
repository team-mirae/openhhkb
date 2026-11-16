# Firmware / MCU identification (from the official images)

Derived only by reading the vendor firmware binaries (kept out of the repo under `firmware/`, git-ignored).
No device was opened. These guide the clean-room (Tier B) recovery firmware; confirm against the physical
board before trusting anything for a flash.

## HHKB Professional Hybrid (PD-KB820 / PD-KB800) — `.hfb`

| Property | Value | Source |
|---|---|---|
| Core | ARM Cortex-**M0** | 48-entry vector table = 16 core + **32 IRQs** (exactly the STM32F0 line) |
| Family | **STM32F0** | Cortex-M0 + 32 IRQs is the deciding evidence (F1/F3 are M3, F4 is M4). RCC referenced at `0x40021000` is consistent (F0/F1/F3 share it) |
| Reset vector | `0x080100D5` | image = `.hfb` minus first 2 bytes; vector table at file offset 4 |
| App base | `0x08010000` | upper 64 KB of a 128 KB flash; lower 64 KB = bootloader |
| Initial SP | `0x200024F0` (820), `0x200024E8` (800) | needs ≥ ~10 KB RAM → 16 KB part |
| Likely part | **STM32F070CB or STM32F072CB** | 128 KB flash, 16 KB RAM, USB FS. F072 = crystalless USB |
| Header (first 2 B of .hfb) | `24 41` (820), checksum-like | sent in the `E1` FirmupStart packet, not part of the image |
| Image trailer | `"AHJX01\n" <ver4>` | model id + version; tool logs `appliableKeyboard: AHJX01` |

Flash map (inferred): `0x08000000`–`0x0800FFFF` bootloader (64 KB), `0x08010000`–`0x0801FFFF` application (64 KB).
The bootloader implements the `E0/E1/E2/E3` receiver (it must, since the app jumps to it on `0xE0` and the update
needs no USB re-enumeration — see captures/).

## HHKB Studio (PD-ID100 / PD-ID120) — `MAIN` container `.bin`

| Property | Value | Source |
|---|---|---|
| Container | `"MAIN"` magic + 16-byte header, then the image at offset `0x10` | see header below |
| Core | Cortex-**M4 class** (not M0) | 104-entry vector table = 16 core + **88 IRQs** |
| Family | likely **STM32F3** | GPIO referenced at `0x48000000` (AHB2, F3/F0/L0) **and** M4 + 88 IRQs + RCC `0x40021000` + USB-FS `0x40005C00` → F3 (M4F) fits; F0/L0 are M0/M0+, excluded by the IRQ count |
| Inner reset | `0x080086C1` | app at ~`0x08008000` (≈32 KB bootloader below) |
| Inner SP | `0x20000800` | low; re-check against the real part's RAM map |
| Update framing | `F7`/`F6` with complement checksums, on `0xFF00/0x01` in **boot mode** | static analysis of the Studio tool |
| Separate firmwares | main MCU, Bluetooth, touchpad | `commandGet{Boot,BT,TP}Version`, `commandFirmupForBTAndTouchPad` |

### `MAIN` 16-byte header (both images)

| Offset | JP (`PD-ID120_B209`) | US (`PD-ID100_B009`) | Guess |
|---|---|---|---|
| 0x00 | `"MAIN"` | `"MAIN"` | magic |
| 0x04 | `0x90000000` | `0x90000000` | fixed (flags / format) |
| 0x08 | `0x2402e7b5` | `0x2402555d` | per-image, high `0x2402` fixed — checksum or signature |
| 0x0c | `0x00016b52` | `0x00016a4e` | per-image, high `0x0001` fixed — length/CRC-like |

So `0x08`/`0x0c` are the per-build varying fields (checksum + length/CRC), the kind the bootloader likely verifies.

Studio next steps: confirm STM32F3 against the board, work out the `0x08`/`0x0c` header fields, and the boot-mode
handshake (`0B 02` → re-enumerate as the `0xFF00/0x01` 64-byte bootloader + the `F7`/`F6` framing), which our
emulator does not do yet. Studio is a separate, larger firmware effort than the Hybrid (M4 vs M0, and the emulator
needs interface hot-swap to capture its update).

## Open items before any Tier B image can be built or flashed
1. Confirm the exact MCU part from the physical PCB (silkscreen) — gates linker script, flash size, USB clock.
2. Derive the `.hfb` header checksum (first 2 bytes) — the on-device **bootloader** verifies it; the keymap tool
   does not (it accepted any value in our capture). Without this, a built image will not install.
3. Studio: parse `MAIN` container + boot-mode protocol.
4. No firmware read-back and no recovery path yet: a wrong image flashed to real hardware can brick it.
