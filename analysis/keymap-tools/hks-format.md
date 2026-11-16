# HHKB Keymap Tool `.hks` setting-file format

The official HHKB Keymap Tool's "back up the keymap as a file" / load feature writes a `.hks`
file. It is **plain UTF-8 JSON** (pretty-printed, 2-space indent). A real sample exported from a
HHKB Professional HYBRID Type-S (JP) is in [`samples/HHKB_Setting_20261117.hks`](samples/).

## Schema

```jsonc
{
  "ToolVersion":        "2.0.1.0",        // version of the tool that wrote the file
  "DipSwitch":          [bool, ...],      // 6 entries, true = switch ON (up). SW1..SW6 in order.
  "TypeNumber":         "PD-KB820BS",     // keyboard model (GET_KEYBOARD_INFO type_number)
  "SleepSetting":       6,                // sleep-timer index (see below)
  "Keymap": {
    "Normal":  [int, ...],                // 128 bytes, Standard layer
    "WithFn":  [int, ...]                 // 128 bytes, Fn layer
  },
  "KeyboardLayout":     0,                // 0 = the keyboard's native layout (JP here)
  "SettingFileVersion": "1.0.0.0"         // schema version of the file itself
}
```

### Keymap arrays

- Each array is **128 integers, one per key position**, in the **same order as the vendor
  protocol** keymap (`0x86` SetKeymap / `0x87` GetKeymap payload). Verified byte-for-byte against a
  live read: `WithFn` begins `[0, 228, 231, 76, 1, 230]` = `00 e4 e7 4c 01 e6`, matching the
  keyboard. Position 44 = `P`; index 0 = bottom-right, 69 = top-left Esc (see
  `../hhkb-hybrid-jis/`).
- Values are the raw keymap bytes as decimal (HID keyboard usages for normal keys; firmware
  internal codes like `232`=`0xE8`..`235`=`0xEB` for the volume/media keys — see
  `../firmware/hybrid-keycodes.md`).
- The file stores only the **two visible layers**. The firmware's per-mode *shortcut* layers
  (`mode|0x10`) are not in the file; the tool regenerates/preserves them when writing.

### Other fields

- **`DipSwitch`** — 6 booleans, matching the physical DIP block (`GET_DIP_STATE` `0x05`).
- **`SleepSetting`** — index into the tool's sleep-time menu, **not** minutes. Observed: `6` ⇒
  "In 60 minutes" in the UI. The protocol's `0x09` reply carried `0x3c` (60) at apply time, so the
  index→minutes table still needs confirming across values.
- **`TypeNumber`** — e.g. `PD-KB820BS` (HHKB Hybrid Type-S JP). Used to validate a file against the
  connected model before writing.

## Mapping to/from `openhhkb-json`

`openhhkb`'s native format carries the same two layers plus model/version, so conversion is a
direct field mapping. Writing a `.hks` back to a keyboard still uses the full per-profile apply
sequence (four layers + `0x08`/`0x04`/`0x07`); see `../../tools/keymap/` and `../../cli/`.

> The sample is one user's personal layout, shared (CC0) purely as a format reference.
