# Topre RealForce Compact — read-only USB scan

Scan date: 2026-11-16. Host: macOS 27 (Apple M6 Mac mini), connected over USB through a hub.

**Method:** Same as `../hhkb-hybrid-jis/`: only the IORegistry (`ioreg -l`) and `system_profiler SPUSBHostDataType`
were read. **The device was not opened and nothing was sent to it.**

## Files

| File | Contents |
|---|---|
| `ioreg-usb-tree.txt` | `ioreg -w0 -l -r -n 'RealForce Compact@00113200'` |
| `system-profiler-usb.txt` | `system_profiler SPUSBHostDataType` entry |
| `report-descriptors/input0.bin` | Raw HID report descriptor for interface 0 |

## Device

| Field | Value |
|---|---|
| VID:PID | `0853:0200` (Topre) |
| Manufacturer / Product | `Topre Corporation` / `RealForce Compact` |
| Serial string | none |
| bcdDevice | `1.02` (also reported as the HID `VersionNumber`) |
| bcdUSB | `0x0110` (USB 1.1), **Full Speed (12 Mbps)**, EP0 max packet size **8** |
| Interfaces | **1**: HID boot keyboard (subclass 1, protocol 1), 1 endpoint, no interface string |

`bCountryCode = 15` (Japan).

## Report descriptor

```
input0  05 01 09 06 a1 01 05 07 19 e0 29 e7 15 00 25 01 75 01 95 08 81 02 95 01 75 08 81 01
        95 05 75 01 05 08 19 01 29 05 91 02 95 01 75 03 91 01 95 06 75 08 15 00 26 ff 00 05
        07 19 00 2a ff 00 81 00 c0
```

Standard boot keyboard: 8 modifier bits, 1 reserved byte, 5 LED bits, 6 keycodes. It differs from the HHKB Hybrid /
REALFORCE X1P interface 0 in exactly **one byte** (offset 45): the LED padding is `Output (Const, Array)` (`91 01`)
here versus `Output (Const, Variable)` (`91 03`) there. Same template, older revision.

## Finding

This is an older, single-interface keyboard: **no vendor HID channel, no media interface, no NKRO report**.
There is no USB path for configuration software here, so it is of **little value for the remapper** beyond
showing that Topre's boot keyboard descriptor template predates the current HHKB Hybrid / X1P firmware.
