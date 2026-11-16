# tools/responder/

Host-side driver for the virtual keyboard. It launches `../vhhkb/vhhkb` inside the throwaway VM over SSH, presents
a device profile to an official tool, logs every report, and answers with reply rules you can edit live.

```
python3 tools/responder/responder.py <device>      # e.g. hhkb-hybrid-jis, hhkb-studio-jis, realforce-x1p-jp-tkl
```

## How it works

```
official tool (VM)  ──►  vhhkb virtual device (VM)  ──SSH──►  responder.py (host)  ──►  rules/<device>.py
```

1. Reads `profiles/<device>.json`, sends a `DEV` line per interface + `GO` to `vhhkb` (which creates the
   `IOHIDUserDevice`s in the VM).
2. For each output report the tool sends, logs it and calls `rules/<device>.py:handle(iface, data, state)`.
3. Sends the rule's reply reports back to the virtual device.

Captures are written to `analysis/<device>/captures/<timestamp>.jsonl` (`out` = tool→device, `in` = our reply).
Firmware-block payloads are redacted from the log (vendor binary).

## Layout

| Path | Contents |
|---|---|
| `responder.py` | the driver (SSH + relay + logging + rule hot-reload) |
| `profiles/<device>.json` | device identity: VID/PID, version, strings, and the report-descriptor `.bin` paths (from `analysis/<device>/`) |
| `rules/<device>.py` | `handle(iface, data, state) -> [(iface, bytes), …]`; reloaded on every change so you can iterate while a tool is connected |

Current devices: `hhkb-hybrid-jis` (fully mapped), `hhkb-studio-jis` (connects; VIA-style), `realforce-x1p-jp-tkl`
(early handshake; REALFORCE CONNECT uses the same framing).

## Notes

- Requires the VM set up as in `../vhhkb/README.md` (SIP off + AMFI relaxed, so the self-signed `vhhkb` can create
  virtual HID devices). Default VM is `admin@192.168.64.3`.
- To talk to a **real** keyboard instead of generating replies, use `../passthrough/` (which reuses these profiles).
