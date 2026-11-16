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
