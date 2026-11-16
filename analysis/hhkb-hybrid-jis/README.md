# HHKB Professional Hybrid (JIS) — read-only USB scan

Scan date: 2026-11-16. Host: macOS 27 (Apple M6 Mac mini), connected over USB through a hub.

**Method:** Only passive sources were read: the IORegistry (`ioreg -l`) and `system_profiler SPUSBHostDataType`.
Both only show what macOS already cached when the device was enumerated. **The device was not opened, and no
reports, control requests or descriptor requests were sent to the keyboard.**

## Files

| File | Contents |
|---|---|
| `ioreg-usb-tree.txt` | `ioreg -w0 -l -r -n 'HHKB-Hybrid@00114000'`: the USB device, its 3 interfaces and the HID drivers on them |
| `system-profiler-usb.txt` | `system_profiler SPUSBHostDataType` entry for the keyboard |
| `report-descriptors/inputN.bin` | Raw HID report descriptor for interface N, taken from the `ReportDescriptor` IORegistry property |

Not captured (macOS does not cache these in the registry; getting them would mean opening the device):
endpoint descriptors (addresses, wMaxPacketSize, bInterval), the raw configuration descriptor, and power attributes.
The registry only gives `bNumEndpoints` per interface.

## Device

| Field | Value |
|---|---|
| VID:PID | `04fe:0022` (PFU / HHKB-Hybrid) |
| Manufacturer / Product | `PFU Limited` / `HHKB-Hybrid` |
| Serial string | none (`iSerialNumber = 0`) |
| bcdDevice | `0x0001` (unlike Studio's `2.11`, so probably not the firmware version here) |
| bcdUSB | `0x0110` (USB 1.1), negotiated **Full Speed (12 Mbps)**, EP0 max packet size 64 |
| Configurations | 1 |
| Interfaces | 3, all HID class |

**Layout is visible:** interface 0 reports HID `bCountryCode = 15`, which the HID spec defines as
**Japan (Katakana)**. The HHKB Studio (JIS) reported 0, so this is a way to tell layouts apart on the Hybrid only.

## Interfaces

| If | Name (iInterface) | EPs | Report descriptor (decoded) | Interpretation |
|---|---|---|---|---|
| 0 | `keyboard` | 1 | Boot keyboard (subclass 1, protocol 1). 8 modifier bits, 1 reserved byte, 5 LED out bits + 3 pad, 6 keycodes (0x00–0xFF). 8 B in, 1 B out | Standard **boot keyboard** (6KRO) |
| 1 | `Multi-Media` | 1 | **Report ID 1** — Consumer, 8 bits: Play/Pause `CD`, Stop `B7`, Prev `B6`, Next `B5`, Mute `E2`, Vol− `EA`, Vol+ `E9`, Eject `B8`. **Report ID 2** — Keyboard: 1 const byte + **232-bit bitmap** of usages 0x00–0xE7. **Report ID 3** — Consumer, 6 bits: AC Home `223`, AL Email `18A`, AL Calculator `192`, AL Consumer Control Config `183`, AL Local Machine Browser `194`, AC Bookmarks `22A` + 2 pad bits. Max input 31 B | Media keys + **NKRO keyboard** report + app-launch keys |
| 2 | *(none)* | 2 | Usage Page **0xFF00**, Usage **0x01**; input usage 0x02, output usage 0x03; **64** × 8-bit each way, no report ID | **Vendor channel.** Most likely path for the official HHKB Professional Keymap Tool |

### Raw report descriptors (hex)

```
input0  05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 01
        95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 26 ff 00 05 07
        19 00 2a ff 00 81 00 c0
input1  05 01 05 0c 09 01 a1 01 85 01 15 00 25 01 75 01 95 08 09 cd 09 b7 09 b6 09 b5 09 e2 09
        ea 09 e9 09 b8 81 02 95 01 75 01 81 01 c0 05 01 09 06 a1 01 85 02 05 07 95 01 75 08 81 03
        95 e8 75 01 15 00 25 01 05 07 19 00 29 e7 81 00 c0 05 01 05 0c 09 01 a1 01 85 03 15 00 25
        01 95 06 75 01 0a 23 02 0a 8a 01 0a 92 01 0a 83 01 0a 94 01 0a 2a 02 81 02 95 02 75 01 81
        01 c0
input2  06 00 ff 09 01 a1 01 09 02 15 00 26 ff 00 75 08 95 40 81 02 09 03 15 00 26 ff 00 75 08
        95 40 91 02 c0
```

Descriptor oddities (harmless, but fingerprints of the firmware's HID code):
- `input1` starts each top-level collection with a redundant `Usage Page (Generic Desktop)` immediately
  overridden by `Usage Page (Consumer)`.
- The NKRO bitmap in report ID 2 is declared `Input (Data, Array)` (`81 00`) with 1-bit fields, where a bitmap
  is normally `Input (Data, Variable)` (`81 02`). macOS accepts it.

## Comparison with HHKB Studio (JIS)

| | HHKB Studio | HHKB Hybrid |
|---|---|---|
| PID | `0x0015` | `0x0022` |
| bcdDevice | `2.11` | `0x0001` |
| Interfaces | 5 (kbd, raw HID, mouse, extrakey, console) | 3 (kbd, multimedia + NKRO, vendor) |
| Vendor channel | `0xFF60/0x61`, 32 B (**QMK RAW_HID**) | `0xFF00/0x01`, 64 B (generic vendor template) |
| Debug console | `0xFF31/0x74` (QMK CONSOLE) | none |
| Country code | 0 | 15 (Japan) |

**Finding:** the Hybrid's HID layout has **nothing in common with QMK**: no `0xFF60` raw HID, no `0xFF31` console,
report IDs 1/2/3 instead of QMK's 3/4, NKRO in the same interface as media keys. The two keyboards very likely run
unrelated firmware, so expect **two different configuration protocols**, consistent with PFU shipping two
separate keymap tools. `0xFF00`/usage 1/64-byte in+out is the stock vendor-HID layout from many MCU/BLE SDK
examples, so it does not identify the firmware base by itself.

**Update (same day):** the REALFORCE X1P JP TKL (`../realforce-x1p-jp-tkl/`) has **byte-for-byte identical**
interface 0 and interface 2 descriptors, and the same unusual NKRO bitmap construct on interface 1. The Hybrid most
likely runs Topre's firmware/USB stack, and its vendor protocol may match REALFORCE CONNECT's.

## Observations during the scan

- A `Google Chrome` (`AppleUSBHostDeviceUserClient`) user client was attached to the USB device at scan time.
  That is Chrome holding a handle on the device (e.g. a WebUSB/WebHID page), not something this scan created.
- A separate paired-but-disconnected Bluetooth device `HHKB-BT` (VID `0x04FE`, PID `0x0202`, firmware 1.1.6)
  is known to macOS. It was not checked whether it is this same unit.

## Next steps (proposed, not done)

1. Get endpoint descriptors without sending anything new, e.g. on Linux from sysfs (`descriptors` file), as done for
   the Studio.
2. Static look at the HHKB Professional Keymap Tool (handoff step A) for `0xFF00` / PID `0x0022` and command bytes.
3. Passive listen on interface 2 IN reports (opening the device read-only, sending nothing).
4. Capture the official tool's traffic on interface 2 while it only reads the keymap, or emulate the device as
   planned for the Studio.
