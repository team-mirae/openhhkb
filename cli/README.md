# openhhkb CLI

An open remapper / updater for HHKB and Realforce (Topre) keyboards, built from this repo's
protocol reverse-engineering. Rust, talks the vendor HID protocol directly (no official tool).

```
cargo build --release    # -> target/release/openhhkb
```

## Design

- **Stateless.** Every command carries its own `--device` and all options; there is no config file
  or remembered selection.
- **Multi-device aware.** Several keyboards (different or similar models) can be connected at once.
  `list` shows them; `--device` selects one by index, `vid:pid`, or `serial:<serial>`.
- **Model support.** Only the **HHKB Hybrid** (`04fe:0022`) is fully supported for configuration and
  firmware. HHKB Studio and Realforce are **detect-only** in this version (they appear in `list`;
  config/firmware commands refuse them).

## Commands

| Command | What it does |
|---|---|
| `list` | List connected recognised keyboards and their selectors. |
| `firmware-info --device <sel>` | Model, revision, serial, app/boot firmware, running bank, keyboard mode. |
| `remap --device <sel> --layer <normal\|fn> --position <0-127> --code <byte> [--confirm]` | Remap one key on the active profile. Without `--confirm`: dry run. |
| `load --device <sel> --input <file> [--format auto\|openhhkb-json\|hks] [--confirm]` | Write a keymap file's two layers. Without `--confirm`: validate + dry run. |
| `export --device <sel> --output <file> [--format openhhkb-json\|hks]` | Read the active keymap to a file. |
| `firmware-info` / `firmware-flash` / `firmware-recovery` | See below. |

Selectors and bytes: `--code` accepts decimal or `0x`-hex. Key position `44` = `P`; index `0` =
bottom-right, `69` = top-left Esc (see `../analysis/hhkb-hybrid-jis/`).

### Writes and safety

Per the repo ground rule, anything that writes to the keyboard needs an explicit flag:

- `remap` / `load` require `--confirm`; otherwise they dry-run.
- `load` writes the **keymap layers only** (not DIP/sleep) via the official full apply sequence
  (four layers to the active mode profile, then commit). It refuses a file whose model doesn't
  match the connected keyboard.
- `firmware-flash` validates the `.hfb` (CRC-16 over the body, model-ID footer vs the connected
  model) and dry-runs without `--confirm`. With `--confirm` it performs the `E0`-`E3` update. This
  framing matches REALFORCE CONNECT and `happy-hacking-gnu` byte-for-byte, but **openhhkb has not
  itself completed a verified hardware flash** — flashing can brick the keyboard. It also enforces
  the model-ID match the official tool does (a wrong-model image is refused).
- `firmware-recovery` is **not implemented yet**.

## Formats

- **openhhkb-json** — native. `model`, `dip_switch` (6 bools), `sleep_setting` (raw minutes),
  `keyboard_layout`, and `keymap.normal` / `keymap.fn` (128 bytes each).
- **hks** — the official HHKB Keymap Tool profile (`analysis/keymap-tools/hks-format.md`). Fully
  interoperable: exported `.hks` matches a real tool export field-for-field. Two notes: the tool's
  `SleepSetting` is a menu index (we convert, assuming 10-minute steps); and the tool may store a
  few keys as 16-bit values whose high byte is tool metadata — the low byte is the device keymap
  byte, which is what we read/write.

## Status

Verified read-only against a real HHKB Hybrid JIS (`list`, `firmware-info`, `export` to both
formats, `load` dry-run of a real `.hks`, flash dry-run + wrong-model refusal). Device writes
(`remap`/`load --confirm`) use the same sequence proven in `tools/keymap/`. Firmware flash is
implemented but unproven on hardware.
