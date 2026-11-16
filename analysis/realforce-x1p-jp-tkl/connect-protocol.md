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
