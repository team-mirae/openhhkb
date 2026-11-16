# Captures: HHKB Keymap Tool 2.0.1 ↔ virtual HHKB Hybrid (JIS)

Date: 2026-11-16. The official tool ran in the throwaway `hhkb-emu` tart VM against `tools/vhhkb` driven by
`tools/responder` with `rules/hhkb-hybrid-jis.py`. **No real keyboard was involved.** Each `.jsonl` holds one
session: `out` = tool → device (64 B output report on interface 2), `in` = our reply.

## Session 1 (`20261116-223133.jsonl`): the tool accepts the virtual keyboard

Read sequence on launch, all on interface 2:

| # | Request | Meaning |
|---|---|---|
| 1 | `aa aa 01 00 01 00` | NotifyApplicationState(0), app starting |
| 2 | `aa aa 02 00 00` | GetKeyboardInformation |
| 3 | `aa aa 05 00 00` | GetDipswInformation |
| 4 | `aa aa 87 00 02 00 00` | GetKeymap(mode 0, Standard layer) → 3 reply chunks |
| 5 | `aa aa 87 00 02 00 01` | GetKeymap(mode 0, Fn layer) → 3 reply chunks |
| 6 | `aa aa 06 00 00` | GetKeyboardMode |
| 7 | `aa aa 01 00 01 01` | NotifyApplicationState(1), read finished |

Confirmed request framing: `AA AA <cmd> <chunk> <len> <payload>`. Reply framing: `55 55 <cmd> <status> <chunk>
<len> <payload>`.

The tool's own log (`20261116-keymap-tool.log`) shows how it parsed our GetKeyboardInformation reply. This confirms
the offsets from static analysis:

```
TypeNumber: PD-KB820BS   (bytes 6..26)
Revision: A              (26..30)
Serial: VHHKB0000000001  (30..46)
AppVersion: 10.00        (46..50 = 01 00 00 00 → digits joined as "10.00")
BootVersion: 10.00       (54..58)
RunningFirmwareState: 0  (byte 62)
```

With type number `PD-KB820BS` the tool shows "HHKB Professional HYBRID Type-S Japanese Layout", the DIP switch panel,
"Sleep Time: Not configurable" and a 69-key JIS keyboard (`20261116-keymap-tool-connected.png`; every key ⊠
because the keymap was all zeros).

After connecting, the tool starts an update check over the network (`UpdateChecker`, sends the type number).

## Session 2 (`20261116-223229.jsonl`): keymap encoding probe

Keymap reply filled with `byte[i] = i + 1` (`20261116-keymap-tool-probe-sequential.png`). Result:

- **Key codes are USB HID keyboard usage IDs**: `0x04`=A … `0x1D`=Z, `0x1E`–`0x27`=1…0, `0x28` Enter, `0x29` Esc,
  `0x2A` BS, `0x2B` Tab, `0x2C` Space (blank label), `0x2D`–`0x38` punctuation (JIS legends), `0x39` Caps,
  `0x3A`–`0x45` F1–F12, `0x46` PrintScreen. `0x00` and `0x03` show as ⊠ (none).
- **Position order is reversed**: index 0 is at the bottom-right of the drawn keyboard, and indices run right-to-left,
  bottom row to top row. The top-left key (Esc position) is index 69 (shows `0x46` PS).
- The bottom-left Fn key keeps its "Fn" label, so it is likely a fixed position. Whether code `0x01`/`0x02` means Fn
  still needs a cleaner probe (one key at a time).

## Next

- Cleaner probes: one non-zero key per run, the Fn layer, and the remaining 128 − 70 bytes (spare? other mode?).
- Click "Change the Keymap" and apply a change, to capture the `0x86` SetKeymap write and `0x04` ConfirmKeymap.

## Session 2, continued: keymap write (user remapped a few keys to their correct values)

Write sequence after "Change the Keymap" → apply:

```
01 (state 0) → 02 → 05 → 06 → 86 ×3 (Standard) → 86 ×3 (Fn) → 04 ConfirmKeymap → 07 (payload 00) → 01 (state 1)
```

SetKeymap chunking: `aa aa 86 41 3b <mode> <fn> <positions 0..56>`, `aa aa 86 82 3b <positions 57..115>`,
`aa aa 86 c3 0c <positions 116..127>`, so 2 + 57, 59 and 12 bytes = mode/fn + 128 positions. Each chunk is acked
with `55 55 86 00 00 00`. Fn layer = `mode 00, fn 01`.

Changes relative to the probe (`pos: probe → written`):

| Layer | Pos | Written | Meaning |
|---|---|---|---|
| Standard | 68 | `0x1E` 1 | top row, 2nd key from left ("1") |
| Standard | 67 | `0x1F` 2 | top row, "2" |
| Standard | 55 | `0x2A` Backspace | top row, rightmost |
| Standard | 53 | `0x14` Q | Q (the tool warned that this position is "reserved" but allowed it) |
| Standard | 52 | `0x1A` W | |
| Standard | 51 | `0x08` E | |
| Standard | 50 | `0x15` R | |
| Standard | 41 | `0x28` Enter | Tab row, rightmost |
| Standard | 2 | `0x51` Down arrow | bottom row |
| Fn | 68 | `0x3A` F1 | Fn+1 |
| Fn | 67 | `0x3B` F2 | Fn+2 |
| Fn | 53 | `0x00` | Fn+Q is not remappable in the tool (fixed, like on the real keyboard; Fn+Q is the Bluetooth pairing key). The tool writes `0x00` there |

This confirms the position order. Index 69 is the top-left key, and indices decrease left-to-right along each row:
top row 69…55, Tab row 54…41, then down to the bottom-right at 0. Codes are HID usage IDs.

## Session 2, continued: full-board manual reset (t≈665 s) and factory reset (t≈741 s)

Both are written with the same sequence as above (6 × `86`, `04`, `07 00`, `01`). The factory reset differs from
the manual one only in positions the UI cannot edit, and in Fn-layer position 4:

| Position | Manual | Factory | Meaning |
|---|---|---|---|
| 0 | (probe leftover) | `0x00` | not drawn, unused |
| 13 | (probe leftover) | `0x02` | fixed left Fn key: **`0x02` = fixed Fn**, while **`0x01` = assignable Fn** |
| 4 (Fn layer) | `0x00` | `0x01` | right Fn key stays Fn on the Fn layer |
| 70..127 | (probe leftover) | all `0x00` | unused |

Fn-layer keys not used for a Fn function default to the Standard-layer code (e.g. Z, X, C), not `0x00`.

The complete factory keymap is in `../factory-keymap.json`. The responder now serves it as the default.

## Session 3: reporting firmware A2.48 (one below the latest A2.49)

Version bytes print as `%X%x.%x%x`, so `0A 02 04 08` = "A2.48". PFU's update list
(`https://origin.pfultd.com/downloads/hhkb/HHKBVersion.json`, fetched 2026-11-16) gives A2.49 for PD-KB820BS.

With A2.48 the tool reads more than with "10.00":

```
87 00 02 10 00   GetKeymap mode 0x10 (shortcut / modifier map), Standard
87 00 02 10 01   GetKeymap mode 0x10, Fn
09               GetSleepSetting
```

So newer Hybrid firmware supports modifier+key shortcut assignments (the `isShortcut` flag in `command87GetKeymap`).
Answering mode `0x10` with the normal keymap made every key show a modifier badge
(`20261116-keymap-tool-A2.48-shortcut-badges.png`). An all-zero shortcut map clears them
(`20261116-keymap-tool-A2.48-empty-shortcuts.png`). With A2.48 the keys are drawn dark instead of blue. The meaning
of the colours is not confirmed yet.

All screenshots in this folder have PNG metadata chunks (eXIf, iTXt, iCCP) removed.
