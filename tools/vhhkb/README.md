# vhhkb — virtual HHKB for protocol capture

Goal: present a fake HHKB (HID only) to the official keymap tool inside a throwaway macOS VM and log what the tool
sends. The real keyboard is never involved. See `../../analysis/keymap-tools/` for what the tools match on.

## VM setup (tart, done 2026-11-16)

1. `tart clone jis-korean-vm hhkb-emu`. Use a throwaway clone; the Cirrus default login is `admin`/`admin`.
2. `tart run --recovery hhkb-emu` → Utilities → Terminal → `csrutil disable` → restart.
3. In the booted VM: `sudo nvram boot-args="amfi_get_out_of_my_way=1"` → reboot.
   Without this, AMFI SIGKILLs (exit 137) any ad-hoc-signed binary that claims
   `com.apple.developer.hid.virtual.device`, even with SIP off.
4. Remote Login (SSH) was already on in this image.

Never apply steps 2–3 to the host Mac.

## Proof of concept (`poc/`) — verified working in macOS 27.2 guest

- `poc.c` creates an `IOHIDUserDevice` with the HHKB Studio interface 1 descriptor (`04fe:0015`, `0xFF60`/`0x61`,
  32 B) and prints every output report. Build with `clang -framework IOKit -framework CoreFoundation -o poc poc.c`
  and sign with `codesign -f -s - --entitlements poc.entitlements poc`.
- `client.c` matches the device exactly like the official tools (`VendorID`, `ProductID`, `DeviceUsagePage`,
  `DeviceUsage` via `IOHIDManager`), opens it and sends one 32-byte output report.

Result:

```
matched devices: 1
open: 0x0
setReport: 0x0
SET type=1 id=0 len=32: 02 10 01 02 00 00 …
```

Note: macOS sets `Transport = "Virtual"` on user devices regardless of the property passed. The official tools
do not match on `Transport`, so this should not matter.

## Next

- `vhhkb` proper: load a device profile (VID/PID/strings/descriptors from `analysis/<device>/`), one
  `IOHIDUserDevice` per interface, forward every output report to a responder on the host, and send replies back
  with `IOHIDUserDeviceHandleReportWithTimeStamp`. Log as JSONL.
- `responder` (Python, host): request → reply rules, hot-reloaded.
