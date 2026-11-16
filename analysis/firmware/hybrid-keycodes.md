# HHKB Hybrid: special keymap values (incl. media keys)

The keymap stores one byte per key. Most values are standard USB HID **keyboard**-page usages, emitted as-is in the
keyboard report. But the firmware's keycode classifier (two copies in the main-MCU image, at file offsets
`0x00a9d2` and `0x00d19a` = press/release paths, confirmed by running the firmware under `tools/fw-emu/`)
special-cases eight values and routes them to a **consumer/system report**. The official keymap tool does not expose
these, but the firmware honours them, so they can be written with the `0x86` SetKeymap command.

**Verified on real hardware (2026-11-17)** by writing each value to Fn+P on the active profile and reading the
emitted consumer usage from the OS event stream. The earlier version of this table was wrong (it guessed the
descriptor bit order); the table below is the corrected, hardware-confirmed mapping.

## Media/system keys → consumer report

The classifier sets one bit of a single consumer report byte. That report's HID descriptor bit order (from the
firmware descriptor at `0x00e754`) is `Bright+, Bright-, Power, Stop, Mute, Vol+, Vol-, Eject` (LSB first):

| keymap value | bit | Emits (consumer usage) |
|---|---|---|
| `0xED` | 0 | Brightness Up (`0x6F`) |
| `0xEC` | 1 | Brightness Down (`0x70`) |
| `0x66` | 2 | Power (`0x30`) |
| `0x78` | 3 | **Stop** (`0xB7`) |
| `0xEA` | 4 | Mute (`0xE2`) |
| `0xE9` | 5 | Volume Up (`0xE9`) |
| `0xE8` | 6 | Volume Down (`0xEA`) |
| `0xEB` | 7 | Eject (`0xB8`) |

These are internal firmware codes, not HID usages; the firmware translates each to the consumer usage shown.
(The factory JIS Fn layer uses `0xE8`/`0xE9`/`0xEA`/`0xEB` on Fn+A/S/D/F for Vol-/Vol+/Mute/Eject, matching the
table.)

### Play/Pause / Next / Prev are NOT reachable via the keymap

The HID descriptor declares a *second* consumer report containing Play/Pause (`0xCD`), Prev (`0xB6`), Next (`0xB5`),
Home, Mail, Calc and MediaSel — but **no keymap classifier feeds it**. A full scan of the firmware found exactly
one classifier (the eight codes above); nothing sets the Play/Pause report byte from a keymap value. So a keymap
remap **cannot** produce Play/Pause, Next or Prev on this firmware. The closest transport key available is **Stop**
(`0x78`).

Classifier disassembly (`0x00a9d2`, press path; the release path at `0x00d19a` clears the same bits):

```
cmp r0,#0xed → r1=0x01 (bit0)    cmp r0,#0xec → r1=0x02    cmp r0,#0x66 → r1=0x04
cmp r0,#0x78 → r1=0x08           cmp r0,#0xea → r1=0x10    cmp r0,#0xe9 → r1=0x20
cmp r0,#0xe8 → r1=0x40           cmp r0,#0xeb → r1=0x80
then: consumer_report_byte |= r1 (press) / &= ~r1 (release); set send flag
```

## Applying a remap: use the active keyboard-mode profile

The keymap is stored **per keyboard-mode profile**. `0x86`/`0x87` take a mode byte; the active profile is the value
returned by `0x06` GetKeyboardMode (`0x01` on the tested unit, not `0x00`). Writing to profile `0x00` reads back
correctly but never changes live keys. The official tool's full apply sequence is: write four layers — keymap
Standard+Fn at `mode`, shortcut Standard+Fn at `mode|0x10` — then `0x08` (sleep), `0x04` (ConfirmKeymap),
`0x07` (ResetDIPSW, payload = mode). See `tools/`'s keymap writer.

## Other special-cased values

The same classifier also special-cases:

- `0x00`–`0x09`, `0x10`–`0x12` — internal functions (Fn, layer, Bluetooth/DIP actions); not HID keyboard output.
  (We saw `0x01` = assignable Fn, `0x02` = fixed Fn in the captured keymap.)
- `0xE0`–`0xE7` — standard HID modifiers (Ctrl/Shift/Alt/Gui, left/right).
- `0x86`, `0x87` — JIS international keys (e.g. Ro `\_`).
- `0xAA`, `0xC7`, `0xD0` — further internal codes (not fully decoded).

Everything else in the standard keyboard range is passed straight into the keyboard report.

## Verifying on hardware (optional, reversible)

Write `0xED` to one key position with `0x86` SetKeymap (e.g. via `happy-hacking-gnu` or the writes-enabled
passthrough), press it, and confirm the OS sees Play/Pause. Reversible by restoring the factory keymap. This is a
config write to the real keyboard, so it needs explicit OK.
