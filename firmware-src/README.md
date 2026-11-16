# openhhkb clean-room firmware (work in progress)

Open firmware for the HHKB Professional Hybrid, written from scratch so it can be distributed. Goal: a recovery
image that installs on a keyboard, reports an old version so the official tool offers an update, and accepts the
vendor `.hfb` as that update — with a default keymap where **A S D F type H H K B** (and Z `/` `\` are preserved so
macOS keyboard tools still work) to show it installed.

**Clean-room:** everything here is written from our own captures and analysis (`analysis/hhkb-hybrid-jis/`,
`analysis/keymap-tools/`, `analysis/firmware/`). No vendor code or firmware bytes are included. Vendor images stay
in the git-ignored `firmware/` directory and are only used as test fixtures.

## Status

| Piece | State |
|---|---|
| Config protocol core (`src/hhkb_proto.*`) | **done**, host-tested |
| Default keymap (`src/default_keymap.h`, generated) | done (A S D F → H H K B; Z `/` `\` kept) |
| Firmware-update receiver (reassembles an uploaded `.hfb`) | done in the core; self-flash to real flash: TODO |
| Host test suite (`test/`) | done — replays captures, round-trips keymaps, reassembles the vendor image |
| STM32F0 target build (startup, linker, image) | done — `make fw` builds `hhkb_fw.bin` at `0x08010000` |
| Core verified on real Cortex-M0 (QEMU) | done — `make qemu` runs the core under `qemu-system-arm` |
| STM32F0 USB FS device stack + HID | written + builds; descriptors validated vs our scan. **NOT hardware-tested** (no F0 USB model in QEMU, no board) |
| Matrix scanning (so it can type) | not required for recovery — the ASDF→HHKB marker shows in the tool's keymap view without typing |
| `.hfb` header checksum (so the stock bootloader accepts our image) | TODO (open item) |
| Studio (different MCU + `MAIN` container + boot-mode) | not started |

## Layout

```
src/hhkb_proto.{h,c}   portable protocol core: no hardware deps, no I/O
src/default_keymap.h   generated built-in keymap
gen/make_default_keymap.py   regenerates it from analysis/hhkb-hybrid-jis/factory-keymap.json
test/hhkb_cli.c        thin CLI over the core for the test harness
test/run_tests.py      host tests (see below)
```

## Build & test

```
make test     # host: build the CLI and run the protocol suite
make fw        # cross-build the STM32F0 image (build/hhkb_fw.bin at 0x08010000)
make qemu      # run the core on a Cortex-M0 under QEMU (microbit), semihosting output
make gen       # regenerate default_keymap.h
```

Toolchain: `arm-none-eabi-gcc` + `qemu-system-arm` (`brew install arm-none-eabi-gcc qemu`). The core is
freestanding (no libc), so it links into the firmware with no runtime.

The suite (`test/run_tests.py`) checks:
1. **structural replay** — every captured tool→device report produces the reply header the real tool accepted;
2. **keymap round-trip** — SetKeymap then GetKeymap;
3. **default marker** — A S D F → H H K B, Z `/` `\` preserved;
4. **firmware receiver** — the real vendor `.hfb` fed as `E1/E2/E3` reassembles byte-exact (skipped if the
   image is not present in `firmware/`).

## Target MCU (from `analysis/firmware/hardware-id.md`)

STM32F0 (Cortex-M0), best guess **STM32F072CB / F070CB**: 128 KB flash (64 KB bootloader at `0x08000000`,
application at `0x08010000`), 16 KB RAM, USB FS. Not yet confirmed against the physical board — must be before
anything is flashed to real hardware.

## Safety

Nothing here has been flashed to a real keyboard. A wrong image is exactly how "recovery firmware" bricks a device,
so the target build will be validated under QEMU and against these captures before any hardware step, and the
`.hfb` header checksum must be understood first.
