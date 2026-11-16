# tools/fw-emu/

Emulate the HHKB Hybrid main MCU (STM32F0 / Cortex-M0) and run its firmware under [Unicorn], to trace code and
analyse routines without hardware.

```
python3 tools/fw-emu/emu.py firmware/HHKB820_FW_JP_A249.hfb [--trace N] [--pc 0xADDR] [--maxinsn N]
```

(Needs `unicorn` + `capstone`, e.g. in a venv: `uv venv v && uv pip install --python v/bin/python unicorn capstone`.)

## What it does / doesn't

- Maps STM32F0 memory (FLASH `0x08000000`, app at `0x08010000`; RAM `0x20000000`; peripheral + PPB regions),
  loads the `.hfb`'s ARM image, and runs from the reset vector.
- Peripheral MMIO is **stubbed** (reads return `0xFFFFFFFF` so active-high "ready" flags pass; writes logged;
  unknown pages auto-mapped). It boots through clock/flash init into the main loop.
- It does **not** model the USB-FS device or the Topre analog sensing, so it cannot become a working keyboard —
  it's for tracing and static-plus-dynamic analysis (e.g. the keymap → HID-report path).

## Notes

- The `.hfb` is a **multi-part container** (main STM32F0 app + the nRF52832 Bluetooth firmware + likely touchpad),
  ~282 KB total. The Cortex-M0 app is the first chunk; its reset vector is `0x080100d5`.
- Running the firmware confirms the main MCU is STM32F0: its real RCC (`0x40021000`) and FLASH (`0x40022000`)
  init execute correctly as F0 code.
- The vendor firmware lives in the git-ignored `../../firmware/`.

[Unicorn]: https://www.unicorn-engine.org/
