# tools/

Tooling built while reverse-engineering the HHKB/Realforce configuration protocols. Everything defaults to
read-only / emulated; the one tool that can write to a real keyboard (`keymap/ set`) does so only when invoked
explicitly, with an on-screen backup, per the repo's ground rule.

| Directory | What it does |
|---|---|
| [`static-re/`](static-re/) | Scripts for static analysis of the official keymap-tool binaries (disassembly, string/literal extraction). Produced `analysis/keymap-tools/`. |
| [`vhhkb/`](vhhkb/) | Virtual HID keyboard: creates `IOHIDUserDevice`s inside a throwaway VM so an official tool talks to a fake keyboard. Driven over a line protocol. |
| [`responder/`](responder/) | Host-side driver for `vhhkb`: presents a device profile, logs every report, and answers with hot-reloaded per-device reply rules. |
| [`passthrough/`](passthrough/) | Logging HID passthrough: an official tool in the VM talks to the **real** keyboard on the host, every report logged, with writes/firmware-flash blocked by default. |
| [`fw-emu/`](fw-emu/) | Emulate the Hybrid's STM32F0 main MCU under Unicorn and run the firmware image, for tracing/analysis (no USB or Topre models — not a working keyboard). |
| [`keymap/`](keymap/) | Read or write the Hybrid keymap over the vendor protocol (via `passthrough/hidbridge`), replicating the official tool's full per-profile apply sequence. `read` is safe; `set` is an explicit-OK config write. |

Typical setups:

- **Emulate a keyboard for an official tool** → `responder/` (which launches `vhhkb/` in the VM). Replies come from
  `responder/rules/<device>.py`.
- **Proxy the real keyboard to a tool, read-only** → `passthrough/` (which also launches `vhhkb/`), with
  `hidbridge` opening the physical device on the host.
- **Read or change the real keymap directly** → `keymap/` (drives the device through `passthrough/hidbridge`).

The clean-room firmware (not a tool) lives in `../firmware-src/`; vendor firmware blobs in the git-ignored
`../firmware/`.
