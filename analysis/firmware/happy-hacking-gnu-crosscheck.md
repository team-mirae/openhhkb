# Cross-check: `happy-hacking-gnu` accepts our custom `.hfb`

An independent, open-source HHKB tool — [`happy-hacking-gnu`](https://gitlab.com/dom/happy-hacking-gnu)
(fork `github.com/minhanghuang/happy-hacking-gnu`) — was used to verify our firmware workaround against a
second implementation of the protocol. Date: 2026-11-17.

## Setup (all inside the throwaway VM)

- The virtual HHKB Hybrid (`tools/vhhkb` + responder, VID/PID `04fe:0022`) ran in the VM.
- `happy-hacking-gnu` was built in the VM with hidapi (macOS backend) and run against the virtual device.
- **The real Hybrid is on the host, not the VM**, so the tool could only ever see the virtual device.
- One `vhhkb` improvement was needed: the tool (via hidapi) selects the device by USB **interface number 2**.
  Our `IOHIDUserDevice`s had none, so `vhhkb` now sets `bInterfaceClass=3` and `bInterfaceNumber` per interface.

## Result

`./hhg -i` read the device correctly: `PFU Limited HHKB-Hybrid`, `PD-KB820BS`, `AppFirmVersion A2.48` — so an
independent tool speaks our emulated protocol.

`./hhg --flash-firmware HHKB820_modified_goodcrc.hfb` (our custom image: vendor A2.49 payload with one byte
changed and a **CRC computed by our algorithm**, `0x9500`) ran the full update:

```
NOTIFY_APPLICATION_STATE → FIRMUP_MODE_CHANGE (E0) → FIRMUP_START (E1) →
FIRMUP_SEND ×4960 (E2) → FIRMUP_END (E3) → Success
```

- The tool read our CRC straight from the file and sent it in `FIRMUP_START`; the responder saw
  `aa aa e1 00 08  30 50 04 00  00 95` = size `0x45030` + CRC **`0x9500`** (our value).
- The device (responder) received all 4960 packets and reassembled the payload **bit-exact** equal to our
  file's `[2:]` (282670 bytes).
- `happy-hacking-gnu` printed **`Success`**.

## What this confirms

1. Our reverse-engineered protocol is correct: an independently written tool drives our virtual device with no
   changes to the protocol, framing, command IDs (`E0–E3`), packet size (57 B), or per-block ack.
2. Our `.hfb` CRC workaround generalizes beyond the official keymap tool: `happy-hacking-gnu` loads and flashes a
   custom image carrying a CRC that only our algorithm produced.

Evidence: `../hhkb-hybrid-jis/captures/20261117-happy-hacking-gnu-flash.log`. `happy-hacking-gnu` is third-party
GPL code and is not vendored here; it was cloned and built only as a test harness.
