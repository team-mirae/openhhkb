# tools/

Tooling built while reverse-engineering the HHKB/Realforce configuration protocols. None of it writes to a real
keyboard by default; the work has stayed read-only / emulated (see the repo's ground rule).

| Directory | What it does |
|---|---|
| [`static-re/`](static-re/) | Scripts for static analysis of the official keymap-tool binaries (disassembly, string/literal extraction). Produced `analysis/keymap-tools/`. |
| [`vhhkb/`](vhhkb/) | Virtual HID keyboard: creates `IOHIDUserDevice`s inside a throwaway VM so an official tool talks to a fake keyboard. Driven over a line protocol. |
| [`responder/`](responder/) | Host-side driver for `vhhkb`: presents a device profile, logs every report, and answers with hot-reloaded per-device reply rules. |
| [`passthrough/`](passthrough/) | Logging HID passthrough: an official tool in the VM talks to the **real** keyboard on the host, every report logged, with writes/firmware-flash blocked by default. |

Typical setups:

- **Emulate a keyboard for an official tool** → `responder/` (which launches `vhhkb/` in the VM). Replies come from
  `responder/rules/<device>.py`.
- **Proxy the real keyboard to a tool, read-only** → `passthrough/` (which also launches `vhhkb/`), with
  `hidbridge` opening the physical device on the host.

The clean-room firmware (not a tool) lives in `../firmware-src/`; vendor firmware blobs in the git-ignored
`../firmware/`.
