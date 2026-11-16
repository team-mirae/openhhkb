# HHKB Hybrid: special keymap values (incl. media keys)

The keymap stores one byte per key. Most values are standard USB HID **keyboard**-page usages, emitted as-is in the
keyboard report. But the firmware's keycode classifier (found in the main-MCU image at ~`0x0801a9ce`, confirmed by
running the firmware under `tools/fw-emu/`) special-cases a set of values and routes them to other reports —
including the **consumer/media report** (interface 1, report ID 1). The official keymap tool does not expose these,
but the firmware honours them, so they can be written with the `0x86` SetKeymap command.

## Media keys → consumer report (report ID 1)

The classifier maps each media keycode to one bit of the consumer report byte; the descriptor's bit order is
`Play/Pause, Stop, Prev, Next, Mute, Vol-, Vol+, Eject` (LSB first):

| keymap value | bit | Emits |
|---|---|---|
| **`0xED`** | 0 | **Play / Pause** (consumer `0xCD`) |
| `0xEC` | 1 | Stop (`0xB7`) |
| `0x66` | 2 | Previous Track (`0xB6`) |
| `0x78` | 3 | Next Track (`0xB5`) |
| `0xEA` | 4 | Mute (`0xE2`) |
| `0xE9` | 5 | Volume Down (`0xEA`) |
| `0xE8` | 6 | Volume Up (`0xE9`) |
| `0xEB` | 7 | Eject (`0xB8`) |

**To bind a key to Play/Pause, set its keymap byte to `0xED`.** (The byte value `0xED` is an internal firmware code,
not a HID usage; the firmware translates it to consumer usage `0xCD`.)

Disassembly of the classifier (release path; the press path sets the same bits):

```
cmp r0,#0xed → r1=0x01 (bit0)    cmp r0,#0xec → r1=0x02    cmp r0,#0x66 → r1=0x04
cmp r0,#0x78 → r1=0x08           cmp r0,#0xea → r1=0x10    cmp r0,#0xe9 → r1=0x20
cmp r0,#0xe8 → r1=0x40           cmp r0,#0xeb → r1=0x80
then: consumer_report[9] &= ~r1 (clear on release) / |= r1 (set on press); report[12] = 1 (send flag)
```

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
