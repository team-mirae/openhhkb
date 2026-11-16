# tools/keymap/

Read or write the HHKB Hybrid keymap over the vendor HID protocol (interface 2), through the
`tools/passthrough/hidbridge` line-protocol bridge.

```
# build the bridge once (see tools/passthrough/), then:
python3 tools/keymap/hhkb_keymap.py <path-to-hidbridge> read
python3 tools/keymap/hhkb_keymap.py <path-to-hidbridge> set fn 44 0x78   # Fn+P -> Stop
```

- **`read`** dumps the active keyboard-mode profile's Standard + Fn layers. Read-only.
- **`set <std|fn> <pos> <value>`** changes one key and applies it live. It prints a backup of
  the layer first.

## Why this exists / what it got right

Our early writes "succeeded" (read back correctly) but never changed live keys. Two reasons,
both fixed here and documented in `../../analysis/firmware/hybrid-keycodes.md`:

1. **Per-profile storage.** The keymap is stored per keyboard-mode profile. The active one is
   the mode byte from `0x06 GetKeyboardMode` (`0x01` on the tested unit), not `0x00`. This tool
   always targets the active profile.
2. **Full apply sequence.** The official tool writes *four* layers (keymap Std+Fn at `mode`,
   shortcut Std+Fn at `mode|0x10`) then `0x08`→`0x04`→`0x07` to commit. Partial sequences don't
   apply. This tool replicates it exactly.

## Safety

A `set` is a config write to a real keyboard — per the repo ground rule, only run it with the
user's explicit OK. It is reversible: note the printed backup, or restore the factory keymap.

Key positions: index 0 = bottom-right, 69 = top-left Esc, decreasing left-to-right per row.
`P = 44`. Media/system key values (hardware-verified): `0x78` Stop, `0xEA` Mute, `0xE8`/`0xE9`
Vol-/Vol+, `0xEC`/`0xED` Brightness-/+, `0x66` Power, `0xEB` Eject. Play/Pause is **not**
reachable via the keymap on this firmware — see the analysis doc.
