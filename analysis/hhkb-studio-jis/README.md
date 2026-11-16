# HHKB Studio (JIS) — read-only USB scan

Scan date: 2026-11-16. Host: Linux (Arch), connected via USB through a hub.

**Method:** Only passive sources were read: `lsusb -v` (unprivileged, so the device was not opened)
and kernel sysfs (`/sys/bus/usb/devices/.../descriptors`, `/sys/class/hidraw/*/device/report_descriptor`).
**No reports were sent to the keyboard.** No `/dev/hidraw*` node was opened.

## Files

| File | Contents |
|---|---|
| `lsusb-verbose.txt` | `lsusb -v -d 04fe:0015` output (report descriptors show as UNAVAILABLE because the device was not opened) |
| `usb-descriptors-raw.bin` | Raw device + configuration descriptor bytes from sysfs |
| `report-descriptors/inputN.bin` | Raw HID report descriptor for interface N, from sysfs |

## Device

| Field | Value |
|---|---|
| VID:PID | `04fe:0015` (PFU, Ltd / HHKB-Studio) |
| Manufacturer / Product | `PFU Limited` / `HHKB-Studio` |
| Serial string | none (`iSerial = 0`) |
| bcdDevice | `2.11` (possibly the firmware version; not yet confirmed) |
| USB | 2.0 descriptor, negotiated **Full Speed (12 Mbps)**, EP0 max packet size 64 |
| Power | Bus-powered, remote wakeup, 100 mA |
| Interfaces | 5, all HID class |

`bCountryCode` is 0 on every interface, so the descriptors do **not** reveal JIS vs. US layout.

## Interfaces

| If | EPs | Report descriptor (decoded) | Interpretation |
|---|---|---|---|
| 0 | 0x81 IN (8 B) | Generic Desktop / Keyboard. 8 modifier bits, 1 reserved byte, 6 keycodes (0x00–0xFF), 5 LED output bits + 3 pad bits | Standard **boot keyboard** (6KRO) |
| 1 | 0x83 IN, 0x04 OUT (32 B) | Usage Page **0xFF60**, Usage **0x61**; input usage 0x62, output usage 0x63; 32 × 8-bit each way, no report ID | **Vendor channel, identical to the QMK `RAW_HID` descriptor** (QMK defaults `RAW_USAGE_PAGE 0xFF60`, `RAW_USAGE_ID 0x61`). VIA/Vial use this interface. This is the most likely path the official keymap tool uses for configuration. |
| 2 | 0x82 IN (8 B) | Mouse: 8 buttons, X/Y (rel, −127..127), Wheel (rel), Consumer AC Pan 0x238 (rel) | Pointing stick + gesture pads (vertical and horizontal scroll) |
| 3 | 0x85 IN (64 B) | Report ID 3: System Control (usage 0x01–0xB7, 16-bit). Report ID 4: Consumer (usage 0x01–0x2A0, 16-bit) | **Same layout as QMK's `EXTRAKEY` descriptor** (QMK uses `REPORT_ID_SYSTEM = 3`, `REPORT_ID_CONSUMER = 4`) |
| 4 | 0x86 IN, 0x07 OUT (32 B) | Usage Page **0xFF31**, Usage **0x74**; input usage 0x75, output usage 0x76; 32 × 8-bit | **Same as the QMK `CONSOLE` descriptor** (the one `hid_listen` / `qmk console` reads). Debug text output may be available here. |

### Raw report descriptors (hex)

```
input0  05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 95 08 75 01 81 02 95 01 75 08 81 01
        05 07 19 00 29 ff 15 00 26 ff 00 95 06 75 08 81 00 05 08 19 01 29 05 95 05 75 01 91 02
        95 01 75 03 91 01 c0
input1  06 60 ff 09 61 a1 01 09 62 15 00 26 ff 00 95 20 75 08 81 02 09 63 15 00 26 ff 00 95 20
        75 08 91 02 c0
input2  05 01 09 02 a1 01 09 01 a1 00 05 09 19 01 29 08 15 00 25 01 95 08 75 01 81 02 05 01 09 30
        09 31 15 81 25 7f 95 02 75 08 81 06 09 38 15 81 25 7f 95 01 75 08 81 06 05 0c 0a 38 02 15 81
        25 7f 95 01 75 08 81 06 c0 c0
input3  05 01 09 80 a1 01 85 03 19 01 2a b7 00 15 01 26 b7 00 95 01 75 10 81 00 c0 05 0c 09 01 a1
        01 85 04 19 01 2a a0 02 15 01 26 a0 02 95 01 75 10 81 00 c0
input4  06 31 ff 09 74 a1 01 09 75 15 00 26 ff 00 95 20 75 08 81 02 09 76 15 00 26 ff 00 95 20 75
        08 91 02 c0
```

## Key finding

Interfaces 1, 3 and 4 match QMK's raw HID, extrakey and console descriptors byte for byte in
usage page, usage and report ID. **This strongly suggests the HHKB Studio firmware is QMK-based or
QMK-derived**, or at least copies its USB/HID layer. If so, the configuration protocol on interface 1
may follow the **VIA protocol**, or something close to it: 32-byte packets, first byte = command ID.

This is a hypothesis only. It has **not** been checked by talking to the device.

## Linux host notes

- `/dev/hidraw0`–`hidraw4` correspond to interfaces 0–4. They are `root:root 0600` by default.
  Reading or writing them needs sudo or a udev rule.
- Input nodes: `event16` (keyboard), `event17` (mouse), `event18` (System Control), `event19` (Consumer Control).

## Next steps (proposed, not done)

1. **Passive console listen (low risk):** open `hidraw4` read-only and print incoming 32-byte packets.
   This sends nothing to the device. Needs root or a udev rule.
2. **USB capture of the official HHKB keymap tool** (e.g. `usbmon` + Wireshark on Linux, or USBPcap in a
   Windows VM), while it only *reads* the keymap. Record the request/response format on interface 1
   without sending our own packets.
3. Compare the captured packets with the VIA protocol (`id_get_protocol_version = 0x01`,
   `id_dynamic_keymap_get_keycode = 0x04`, ...). Only then think about sending a single *read-only*
   query ourselves.
