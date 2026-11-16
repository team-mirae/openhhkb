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
| Container | `"MAIN"` magic + header, then the image at offset `0x10` | `4d 41 49 4e 00 00 00 90 ...` |
| Core | Cortex-**M3/M4 class** (not M0) | large vector table (~80+ IRQs) |
| Inner reset | `0x080086C1` | app above ~`0x08008000` (≈32 KB bootloader) |
| Inner SP | `0x20000800` | (small; re-check — padding may inflate the vector count) |
| Update framing | `F7`/`F6` with complement checksums, on `0xFF00/0x01` in **boot mode** | static analysis of the Studio tool |
| Separate firmwares | main MCU, Bluetooth, touchpad | `commandGet{Boot,BT,TP}Version`, `commandFirmupForBTAndTouchPad` |

Studio needs its own pass: parse the `MAIN` header fields, confirm the MCU, and the boot-mode handshake
(`0B 02` → re-enumerate as the `0xFF00/0x01` 64-byte bootloader, which our emulator does not do yet).

## Open items before any Tier B image can be built or flashed
1. Confirm the exact MCU part from the physical PCB (silkscreen) — gates linker script, flash size, USB clock.
2. Derive the `.hfb` header checksum (first 2 bytes) — the on-device **bootloader** verifies it; the keymap tool
   does not (it accepted any value in our capture). Without this, a built image will not install.
3. Studio: parse `MAIN` container + boot-mode protocol.
4. No firmware read-back and no recovery path yet: a wrong image flashed to real hardware can brick it.
