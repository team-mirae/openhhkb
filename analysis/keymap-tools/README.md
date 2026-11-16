# Official keymap tools — static analysis (pass 1)

Date: 2026-11-16. Read-only: the app binaries were only read, never run. No keyboard was involved.

| Tool | Bundle ID | Version | Binary SHA-256 (universal) |
|---|---|---|---|
| HHKB Studio Keymap Tool | `jp.co.pfu.hhkb-studio-keymap-tool` | 1.1.2 | `4862c024…df776d` |
| HHKB (Professional) Keymap Tool | `jp.co.pfu.hhkb-keymap-tool` | 2.0.1 | `9e8eef79…8395d7` |

Both are native Swift/AppKit apps (universal x86_64 + arm64), **not stripped**: full Swift symbol names are present.
They were also built with code-coverage counters (`___profc_…`), which leak the vendor's build paths
(`hhkb-KeymapTool-Mac-2.0.1`, `mocha-KeymapTool-Mac-Pit_Mocha_mac00053`). "Mocha" appears to be the internal name of
the Studio. Only the arm64 slice was analysed.

## Files

| File | Contents |
|---|---|
| `studio-driver-symbols.txt`, `pro-driver-symbols.txt` | Demangled `HHKBDriver` / `USBDriver` method names |
| `studio-packet-literals.txt`, `pro-packet-literals.txt` | Constant byte arrays used inside each driver method (`v0` = usually the request prefix, `v1+` = expected response prefix or chunk headers) |

Helper scripts are in `../../tools/static-re/` (`lits.py` dumps array literals, `glob.py` reads static `Constants`
arrays, `ann.py` annotates disassembly with import names and inline Swift strings, `dis.sh` disassembles one symbol).
They expect `<bin>.nm` (`nm` output as `addr<TAB>mangled`) and `<bin>.map` (`addr<TAB>demangled`) next to the binary.

## How the tools find the keyboard

Only `IOHIDManager` / `IOHIDDevice` APIs are imported: no IOUSB, IORegistry, or libusb. The matching dictionary
is built in `USBDriver.seekDevice` with exactly four keys:

```
VendorID, ProductID, DeviceUsagePage, DeviceUsage
```

`DeviceUsagePage`/`DeviceUsage` match any top-level collection of the device, so **one virtual HID device per interface
is enough** for an emulator. Interface numbers, USB strings, `Transport` and `LocationID` are not checked.

| Tool / mode | VID | PIDs (`Constants.hhkbProductIds`) | Usage page / usage | Report size |
|---|---|---|---|---|
| Studio, normal | `0x04FE` | `0x0015`, `0x0016` | **`0xFF60` / `0x61`** (= Studio interface 1, QMK raw HID) | 32 B output, report ID 0 |
| Studio, boot (`communicateInBoot`) | `0x04FE` | (passed in) | **`0xFF00` / `0x01`** | 64 B output |
| Professional | `0x04FE` | `0x0020`, `0x0021`, `0x0022`, `0x0025`, `0x0026` | **`0xFF00` / `0x01`** (= Hybrid interface 2) | 64 B output, report ID 0 |

All writes use `IOHIDDeviceSetReport(kIOHIDReportTypeOutput, reportID 0, buf, 32|64)`. Replies arrive through
`IOHIDDeviceRegisterInputReportCallback`. There is a timeout and `usleep` polling in `USBDriver`.

`PID 0x0022` (our HHKB Hybrid JIS) is in the Professional tool's list. Studio model numbers in `Constants.hhkbTypeNumbers`:
`PD-ID100B`, `PD-ID120B`, each also with `-EM` and `-PPM` suffixes.

## Studio protocol: VIA command IDs

The Studio tool's command numbers line up with the **VIA protocol** command IDs, which fits the QMK-style descriptors:

| Method (tool's own name) | Literal | VIA meaning of first byte |
|---|---|---|
| `command02GetKeyboardInformation` | `02 10 01 02 00`, `02 10 03 02 00`, `02 10 05 02 00`, `02 10 07 02 00`, `02 10 0b` | `0x02` id_get_keyboard_value |
| `command02GetSelectedProfile` | `02 11 01` | `0x02` get value |
| `command03GetDipswInformation` | `02 11 03` | `0x02` get value |
| `command02GetPointingStickInfomation` / `…CurrentInfo` | `02 11 04` | `0x02` get value |
| `command02GetGesturePadInformation` | `02 11 05 01` | `0x02` get value |
| `command03SetPoitingStickInformation` | `03 11 04` | `0x03` id_set_keyboard_value |
| `commad03SetGesturePadInformation` | `03 11 05 01` | `0x03` set value |
| `commandSetProfile` | `02 11 01 00` then `03 11 01` | get, then set |
| `commandSetAppFrimVersion` | `03 10 0b 00 …` | `0x03` set value |
| `commandFirmupEnterTouchpad` | `03 11 05 03 00 07 01 07` | `0x03` set value |
| `command12GetKeymap(profile:mode:)` | `12 …` | `0x12` id_dynamic_keymap_get_buffer |
| `command13SetProfileData` | `13 00 00 1b`, `13 00 f0 1b`, `13 01 e0 1b`, `13 02 d0 1b` | `0x13` id_dynamic_keymap_set_buffer: offset (BE16), size `0x1b` |
| `commandE0FirmupModeChange` | `0b 02` | `0x0B` id_bootloader_jump |

The second byte is a **value ID**. Standard VIA uses `0x01`–`0x05`; PFU uses `0x10` (keyboard info: type, firmware,
version, etc.) and `0x11` (settings: profile `01`, DIP switches `03`, pointing stick `04`, gesture pads `05`). The
`13` offsets step by `0xF0` (240 bytes), probably one profile/layer block each.

Boot/bootloader mode uses a different framing on `0xFF00`/64 B, with complement checksums:

```
commandGetBootFirmVersion   req  f7 01 fe 00 02        resp  f6 02 fd 00 02 00
commandGetBTVersion         req  f7 01 fe 01 02        resp  f6 02 fd 01 02 00
commandF7FirmupStart/Send/End, commandExitFirmup, commandGetTPVersion (touchpad), commandFirmupForBTAndTouchPad
```

So the Studio has separately updatable firmware for the main MCU, Bluetooth and touchpad (gesture pads).

## Professional (Hybrid) protocol: `AA AA` / `55 55` framing

Requests start `AA AA <cmd>`, replies start `55 55 <cmd>`. Observed literals:

| Command | Method | Request prefix | Expected reply prefix |
|---|---|---|---|
| `0x01` | `command01NotifyApplicationState(state:)` | `aa aa 01 00 01` (+ state) | `55 55 01 00 00 00` |
| `0x02` | `command02GetKeyboardInformation` | `aa aa 02 00 00` | `55 55 02 00 00` (reply must be ≥ 26 bytes) |
| `0x04` | `command04ConfirmKeymap` | `aa aa 04 00 00` | `55 55 04 00 00 00` |
| `0x05` | `command05GetDipswInformation` | `aa aa 05 00 00` | `55 55 05 00 00 0c` (12 data bytes) |
| `0x06` | `command06GetKeyboardMode` | `aa aa 06 00 00` | `55 55 06 00 00 01` (1 byte) |
| `0x07` | `command07ResetDIPSW(keyboardMode:)` | `aa aa 07 00 01` (+ mode) | `55 55 07 00 00 00` |
| `0x08` | `command08ResetSleepSetting` | `aa aa 08 00 01` (+ setting) | `55 55 08 00 00 00` |
| `0x09` | `command09GetSleepSetting` | `aa aa 09 00 00` | `55 55 09 00 00 01` |
| `0x86` | `command86SetKeymap(mode:fnKey:keymapData:isShortcut:)` | chunks `aa aa 86 41 3b`, `aa aa 86 82 3b`, `aa aa 86 c3 0c` | `55 55 86 00 00 00` |
| `0x87` | `command87GetKeymap(mode:fnKey:isShortcut:)` | `aa aa 87 00 02` (+ mode, fn) | chunks `55 55 87 00 41 3a`, `… 82 3a`, `… c3 0c` |
| `0xE0` | `commandE0FirmupModeChange` | `aa aa e0 00 00 00` | `55 55 e0 00 00 00` |
| `0xE1`–`0xE3` | firmware start / send / end | `aa aa e1 00 08`, `aa aa e2 00`, `aa aa e3` | `55 55 e1/e2/e3 …` |

Reading of the layout (to be confirmed): byte 3 is a chunk marker (`0x40|1`, `0x80|2`, `0xC0|3` = first/middle/last
of 3) and byte 4 a payload length. A keymap read returns 58 + 58 + 12 = **128 bytes** in three chunks. Byte 4 of a
reply looks like the data length (`0x0c` for DIP switches, `0x01` for mode).

## What this means for the emulator

- **Feasible with `IOHIDUserDevice`:** the tools only need VID, PID and the usage page/usage pair on a vendor HID
  collection. Studio: a device with the `0xFF60/0x61` 32-byte descriptor; Hybrid: `0xFF00/0x01` 64-byte.
- Replies need correct prefixes: VIA echo style for the Studio (VIA replies echo the request), and `55 55 <cmd> 00 00 <len>`
  for the Professional tool. The next step is to disassemble the reply parsers (`command02GetKeyboardInformation` and
  `checkKeyboardData`) to get the field offsets the tool needs to accept a device (model number, firmware version,
  keyboard mode).
- Firmware update is fully visible in both tools (Studio: VIA `0x0B` bootloader jump, then `F7` framing on `0xFF00`;
  Professional: `E0`–`E3`). An emulator can safely observe it.

## Still to do (pass 2)

1. Reply parsing offsets for `GetKeyboardInformation` in both tools, and `KeyboardDataEntity` field mapping
   (`firmVersion`, `bootFirmVersion`, `revision`, `serial`, `mode`, `runningFirmwareState`, `dipSwitch`, `keymap`…).
2. Exact order of calls during "read keymap" (`loadKeyboardDataFromPhysicalKeyboard`).
3. Byte layout of the 128-byte Professional keymap and the 240-byte Studio blocks (key index → HID usage).
