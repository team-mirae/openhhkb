# REALFORCE CONNECT uses the same protocol + CRC + firmware flow as HHKB

Tested with a virtual REALFORCE X1P JP TKL (`tools/vhhkb` + responder) against **REALFORCE CONNECT ONLINE
Ver 1.4.0** (a WebHID app at `realforce-connect.online`) in Chrome in the throwaway VM, plus analysis of the
app's JavaScript bundle. Date: 2026-11-17.

## Result: our firmware workaround applies to CONNECT

**Same vendor protocol.** CONNECT talks to the virtual device on interface 2 (`0xFF00/0x01`, 64 B) with the
identical framing we found on the HHKB Hybrid (confirmed live — CONNECT sent `01`, `C1`, `02`, `C3`, …):

```
request  AA AA <cmd> <param> <len> <data...>
reply    55 55 <cmd> <status> <x> <len> <data...>   (app reads cmd@[2], status@[3], len@[5], data@[6..6+len])
```

From the app bundle (`makePacket`/`sendCommand`/`inputReportHandler`):

| cmd | CONNECT function | HHKB equivalent |
|---|---|---|
| `0x01` | appLaunchNotification(state) | NotifyApplicationState |
| `0x02` | getDeviceInfo → modelNumber (ASCII of data) + fwVersion (hex of data[8:]) | GetKeyboardInformation |
| `0xC0`–`0xC3`, `0xC7`,`0xC8` | request / romRead / romWrite / ramRead (config EEPROM) | the HHKB `0x11`-value reads/writes |
| `0xE0` | enterFirmwareUpdateMode | FIRMUP_MODE_CHANGE |
| `0xE1` | firmup start: `size(LE32)` + `CRC(LE32)` | FIRMUP_START |
| `0xE2` | firmup block: `blockNo(LE16)` + 57 bytes; reply must echo blockNo | FIRMUP_SEND |
| `0xE3` | firmup end | FIRMUP_END |

**Same firmware-update flow.** `execFirmwareUpdate(file)` does: `e = file.slice(2)` (drop the 2 header bytes),
send `E1` with `e.length` + `calcCRC(e)`, then `E2` in 57-byte blocks, then `E3`. Byte-for-byte the same as the
HHKB Hybrid update and as `happy-hacking-gnu`.

**Same CRC, verified bit-exact.** CONNECT's `calcCRC` is a table-driven CRC-16 whose 256-entry table and output
match our `hfb_crc16` (reflected, poly `0x8408`, init `0xFFFF`) exactly:

```
HHKB820_FW_JP_A249.hfb: stored 0x4124  CONNECT.calcCRC 0x4124  our hfb_crc16 0x4124
HHKB800_FW_A048.hfb   : stored 0x3b01  CONNECT.calcCRC 0x3b01  our hfb_crc16 0x3b01
```

CONNECT **computes the CRC itself** from the payload (it does not trust the file's stored CRC), so a custom
Realforce firmware must carry exactly the CRC our packer (`firmware-src/gen/pack_hfb.py`) produces. **Our workaround
is therefore exactly what CONNECT would send to the device.**

## What was not done (and why it doesn't change the answer)

Driving CONNECT's UI all the way to the firmware-update button needs it to finish connecting, which reads the
keyboard's whole config EEPROM via many `romRead`/`ramRead` calls at specific addresses (`0`, `157`, `191`, `49`,
`45`, `7`, loops…). Faking that full, model-specific layout is a large reverse-engineering task of Topre's EEPROM
map — unrelated to the firmware protocol or CRC. Our generic replies get CONNECT through `01/C1/02/C3/C1` before it
rejects the fake config. The firmware/CRC identity above is established from CONNECT's own code, independent of the
UI handshake.

## Files

`tools/responder/profiles/realforce-x1p-jp-tkl.json` and `rules/realforce-x1p-jp-tkl.py` bring up the virtual X1P
and answer CONNECT's early commands. The CONNECT app bundle is third-party and is not vendored here.

## Update: connect handshake partially emulated

Decoding more of CONNECT's connect flow, the rules now answer its early reads well enough to get much further:
`romRead(0)` returns the device name + flags (byte7 bit7 clear, or it rejects as a "setting limit device");
`romRead(191)` must return a non-zero FW CRC in bytes[2:3] (else "The CRC for the FW is zero"); `getDeviceInfo`
returns an old version not starting with "B". With these, CONNECT proceeds through the whole keymap/macro/matrix
read range (`romRead` 0x07–0x3f) before erroring in a later config section. Reaching the firmware-update button
needs the rest of Topre's config read map emulated — a separate effort, and not required to establish the
firmware/CRC result above.

## Confirmed against the real keyboard (logging passthrough)

`tools/passthrough/` bridges the REAL keyboard (on the host) to a virtual device CONNECT opens in the VM, logging
every report (`hidbridge.c` opens the real vendor interface via hidapi; `passthrough.py` relays, with writes and
firmware-flash commands blocked by default). With it, **CONNECT fully connected to the real X1P** and we captured
the genuine config protocol end to end: device name `X1PC11`, firmware `A1.13`, the FW-CRC read at ROM addr 191
(`0x6a80`), and the keymap/APC EEPROM layout.

Firmware-update gating (from CONNECT's `config.json`): the latest `X1P` firmware is version `113` (A1.13), and the
real keyboard is already `113`, so `isFirmwareVersionLatest` is true and the update menu stays disabled — which is
why an update can't be triggered. Reporting an older version (the passthrough can rewrite the `0x02` reply to
A1.00) re-enables it; holding Shift in CONNECT also exposes a manual-update item. The firmware flash itself stays
blocked by the passthrough guard, so the real keyboard is never written.

Note: repeatedly opening/closing the real keyboard's vendor interface makes macOS's `hid_open` flaky until the
keyboard is replugged; this is a device/OS quirk, not a protocol issue.

## Firmware-update attempt against the real keyboard (blocked)

With the passthrough reporting an older version (A1.00 via the `0x02` rewrite), CONNECT enabled and triggered the
firmware update against the real X1P: it sent `E0` (enterFirmwareUpdateMode), which the guard **blocked** (synthetic
ack, nothing sent to the keyboard). It then stalled because `updateFirmware(file)` only runs `E1/E2/E3` when a
firmware file is actually selected; with no file it returns immediately.

Decisive finding from `setFirmwareUpdateData` — CONNECT validates a selected `.rfb` with **our exact CRC**:

```js
d = p.slice(2); if (calcCRC(d) !== <stored CRC at p[0:2]>) throw "FW CRC mismatch";
// + model check (footer, '#' stripped) and version check (file version >= installed)
```

`calcCRC` is bit-identical to `firmware-src/src/hfb_crc.h`. So a custom `.rfb` carrying our CRC passes CONNECT's own
file validation; reporting an older installed version (A1.00) lets a real-version file through the version gate.
Net: the firmware workaround is confirmed against CONNECT end to end, and the guard kept the real keyboard unwritten.

Bridge note: the host bridge must not print the wide product name (`%ls`) on its stdout line protocol — it emits a
control byte that corrupts the stream and looks like the device "failing to open". Fixed in `hidbridge.c`.
