# REALFORCE X1P JP TKL — read-only USB scan

Scan date: 2026-11-16. Host: macOS 27 (Apple M6 Mac mini), connected over USB through a hub.

**Method:** Same as `../hhkb-hybrid-jis/`: only the IORegistry (`ioreg -l`) and `system_profiler SPUSBHostDataType`
were read, i.e. what macOS cached at enumeration. **The device was not opened and nothing was sent to it.**

Why this is in an HHKB repo: Topre builds the HHKB Professional line for PFU, so a Topre keyboard is a candidate
for shared firmware lineage with the HHKB Professional Hybrid.

## Files

| File | Contents |
|---|---|
| `ioreg-usb-tree.txt` | `ioreg -w0 -l -r -n 'REALFORCE X1P JP TKL@00143000'` |
| `system-profiler-usb.txt` | `system_profiler SPUSBHostDataType` entry |
| `report-descriptors/inputN.bin` | Raw HID report descriptor for interface N (IORegistry `ReportDescriptor`) |

Not captured (not cached by macOS): endpoint descriptors and the raw configuration descriptor.

## Device

| Field | Value |
|---|---|
| VID:PID | `0853:0322` (Topre) |
| Manufacturer / Product | `Topre` / `REALFORCE X1P JP TKL` |
| Serial string | none |
| bcdDevice | `0x0001` |
| bcdUSB | `0x0200`, negotiated **High Speed (480 Mbps)**, EP0 max packet size 64 |
| Power | 500 mA allocated |
| Interfaces | 4, all HID class |

`bCountryCode = 15` (Japan) on **every** interface, consistent with the JP layout in the product name.

## Interfaces

| If | Name | EPs | Report descriptor (decoded) | Interpretation |
|---|---|---|---|---|
| 0 | `Keyboard` | 1 | Boot keyboard (subclass 1, protocol 1), 6KRO, 5 LEDs. 8 B in, 1 B out | Standard boot keyboard |
| 1 | `Multimedia` | 1 | **Report ID 1** — Keyboard: 1 const byte + **232-bit bitmap** (usages 0x00–0xE7), declared `Input (Data, Array)`. **Report ID 2** — Consumer, 20 bits: Brightness Up `6F` / Down `70`, Next `B5`, Prev `B6`, Stop `B7`, Eject `B8`, Play/Pause `CD`, Mute `E2`, Vol− `EA`, Vol+ `E9`, AC Home `223`, AC Bookmarks `22A`, AL Consumer Control Config `183`, AL Email `18A`, AL Calculator `192`, AL Local Machine Browser `194`, AC Back `224`, AC Forward `225`, AC Search `221`, AC Refresh `227` + 4 pad bits | NKRO keyboard + media/app keys |
| 2 | *(none)* | 2 | Usage Page **0xFF00**, Usage **0x01**; in usage 0x02, out usage 0x03; **64** × 8-bit each way, no report ID | **Vendor channel**, likely used by Topre's REALFORCE CONNECT software |
| 3 | *(none)* | 1 | Mouse: 8 buttons, X/Y, Wheel, Consumer AC Pan (all rel, −127..127), then **vendor page 0xFFC1 usage 0xF0, 3 bytes** | Mouse report (the X1 series has a mouse-emulation mode), plus 3 vendor bytes inside the mouse report |

### Raw report descriptors (hex)

```
input0  05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 01
        95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 03 95 06 75 08 15 00 26 ff 00 05
        07 19 00 2a ff 00 81 00 c0
input1  05 01 09 06 a1 01 85 01 05 07 15 00 25 01 95 01 75 08 81 03 95 e8 75 01 05 07 19 00
        29 e7 81 00 c0 05 0c 09 01 a1 01 85 02 15 00 25 01 75 01 95 14 09 6f 09 70 09 b5 09
        b6 09 b7 09 b8 09 cd 09 e2 09 ea 09 e9 0a 23 02 0a 2a 02 0a 83 01 0a 8a 01 0a 92 01
        0a 94 01 0a 24 02 0a 25 02 0a 21 02 0a 27 02 81 02 95 04 81 01 c0
input2  06 00 ff 09 01 a1 01 09 02 15 00 26 ff 00 75 08 95 40 81 02 09 03 15 00 26 ff 00 75
        08 95 40 91 02 c0
input3  05 01 09 02 a1 01 09 01 a1 00 05 09 19 01 29 08 15 00 25 01 75 01 95 08 81 02 05 01
        09 30 09 31 15 81 25 7f 75 08 95 02 81 06 09 38 15 81 25 7f 75 08 95 01 81 06 05 0c
        0a 38 02 15 81 25 7f 95 01 75 08 81 06 06 c1 ff 09 f0 15 00 26 ff 00 75 08 95 03 81
        02 c0 c0
```

## Key finding: shared HID stack with the HHKB Professional Hybrid

Compared with `../hhkb-hybrid-jis/`:

- **Interface 0 (boot keyboard): byte-for-byte identical** (65 bytes).
- **Interface 2 (vendor 0xFF00, 64 B): byte-for-byte identical** (34 bytes), and on the same interface number.
- Interface 1: report IDs and consumer usage lists are arranged differently, but the NKRO keyboard collection uses
  the **same unusual construct** in both: a constant pad byte (`81 03`), then 232 one-bit fields over usages
  0x00–0xE7 declared `Input (Data, Array)` (`81 00`) instead of the usual `Variable`. Both list the same six
  app-launch usages (`223 22A 183 18A 192 194`).
- Both: Interface names `Keyboard`/`keyboard` and `Multimedia`/`Multi-Media`, no string on If2, no serial.

**This strongly suggests the HHKB Professional Hybrid and the REALFORCE X1P share Topre's firmware/USB stack**,
and the vendor channel on If2 may speak the same or a closely related protocol. If so, REALFORCE CONNECT and the
HHKB Professional Keymap Tool are worth comparing side by side (handoff step A). Hypothesis only; nothing has been
sent to either device.

The HHKB Studio (`../hhkb-studio-jis/`) shares none of this; it looks QMK-based.
